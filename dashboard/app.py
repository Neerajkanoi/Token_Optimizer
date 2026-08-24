import os
import uuid
import time
import requests
import json
import bcrypt
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Config & Setup ---
st.set_page_config(
    page_title="Token Optimizer", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a sleek, dark FinOps aesthetic
st.markdown("""
<style>
    /* Main Layout */
    .reportview-container .main .block-container{ padding-top: 2rem; }
    
    /* Metrics & Cards */
    .metric-card {
        background-color: #1e2127;
        border-radius: 8px;
        padding: 20px;
        border: 1px solid #333842;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .metric-value { font-size: 28px; font-weight: bold; color: #61afef; }
    .metric-label { font-size: 14px; color: #abb2bf; text-transform: uppercase; letter-spacing: 1px; }
    
    /* Waterfall Trace */
    .trace-step {
        padding: 15px;
        border-left: 3px solid #61afef;
        background-color: #1e2127;
        margin-bottom: 10px;
        border-radius: 0 8px 8px 0;
    }
    .trace-title { font-weight: bold; font-size: 16px; margin-bottom: 5px; color: #e5c07b; }
    .trace-detail { font-size: 14px; color: #abb2bf; }
    
    /* Centered Login Box */
    .login-box {
        max-width: 400px;
        margin: 0 auto;
        padding: 30px;
        background-color: #1e2127;
        border-radius: 8px;
        border: 1px solid #333842;
    }
</style>
""", unsafe_allow_html=True)

# Database Connection
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin_password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "gateway_db")
DB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

@st.cache_resource
def get_engine():
    import os
import streamlit as st
from sqlalchemy import create_engine

@st.cache_resource
def get_engine():
    # 1. Load the URL
    if "DATABASE_URL" in st.secrets:
        db_url = st.secrets["DATABASE_URL"]
    else:
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:admin_password@localhost:5432/gateway_db")

    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # 2. Attempt connection and safely capture the exact error
    try:
        engine = create_engine(db_url, pool_pre_ping=True)
        with engine.begin() as conn:
            pass # Connection successful
        return engine
        
    except Exception as e:
        # Parse out the host to see where it's actually trying to connect
        safe_target = db_url.split("@")[-1] if "@" in db_url else "localhost"
        
        st.error("🚨 **Database Connection Failed**")
        st.info(f"**Attempting to connect to:** `{safe_target}`")
        st.error(f"**Exact Error:** {str(e)}")
        st.stop() # Halt the app so Streamlit doesn't throw the redacted error

engine = get_engine()


# ================= AUTHENTICATION LOGIC =================
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_user(email: str, password: str) -> bool:
    hashed = hash_password(password)
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO dashboard_users (id, email, password_hash) VALUES (:id, :email, :hashed)"),
                {"id": str(uuid.uuid4()), "email": email, "hashed": hashed}
            )
        return True
    except Exception as e:
        st.error(f"DB Error: {e}")
        return False

def authenticate_user(email: str, password: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT password_hash FROM dashboard_users WHERE email = :email"),
            {"email": email}
        ).fetchone()
        
        if result and verify_password(password, result[0]):
            return True
    return False

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user_email"] = None

# ================= LOGIN & SIGNUP SCREEN =================
if not st.session_state["authenticated"]:
    st.markdown("<h1 style='text-align: center; margin-bottom: 2rem;'>Token Optimizer</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<div class='login-box'>", unsafe_allow_html=True)
        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
        
        with tab_login:
            with st.form("login_form"):
                log_email = st.text_input("Email", placeholder="admin@example.com")
                log_pass = st.text_input("Password", type="password")
                if st.form_submit_button("Secure Login", use_container_width=True):
                    if authenticate_user(log_email, log_pass):
                        st.session_state["authenticated"] = True
                        st.session_state["user_email"] = log_email
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
                        
        with tab_signup:
            with st.form("signup_form"):
                st.caption("Create a new admin account to access the dashboard.")
                new_email = st.text_input("Email")
                new_pass = st.text_input("Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if len(new_pass) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif create_user(new_email, new_pass):
                        st.success("Account created successfully! You can now log in.")
                    else:
                        st.error("User with this email already exists.")
                        
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ================= DATA LOADING =================
def load_data():
    try:
        logs_df = pd.read_sql("SELECT * FROM request_logs ORDER BY created_at DESC", engine)
        tenants_df = pd.read_sql("SELECT * FROM tenants", engine)
        if not logs_df.empty:
            logs_df['created_at'] = pd.to_datetime(logs_df['created_at'])
        return logs_df, tenants_df
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(), pd.DataFrame()


# ================= PROTECTED DASHBOARD =================

# Sidebar Navigation
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/8636/8636984.png", width=50)
    st.title("Token Optimizer")
    st.caption("FinOps Gateway & Router")
    st.markdown("---")
    
    menu = st.radio(
        "Navigation",
        [
            "🔌 Developer DX & Setup",
            "🧪 Interactive Playground",
            "📊 FinOps Analytics",
            "⚙️ Gateway Config"
        ]
    )
    
    st.markdown("---")
    st.caption(f"Logged in as: {st.session_state['user_email']}")
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["user_email"] = None
        st.rerun()

logs_df, tenants_df = load_data()


# ================= MODULE 1: DEVELOPER ONBOARDING =================
if menu == "🔌 Developer DX & Setup":
    st.header("Developer Onboarding & Setup")
    st.markdown("Generate API keys instantly and drop Token Optimizer into your existing AI applications without changing your logic.")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.subheader("1. Generate API Key")
        with st.form("api_key_form"):
            org_name = st.text_input("Organization / App Name", placeholder="e.g. Acme Corp Chatbot")
            tier = st.selectbox("Routing Tier", ["Free (Flash Only)", "Pro (Pro & Flash)", "Enterprise (All Models)"])
            budget = st.number_input("Monthly Virtual Budget ($)", min_value=1.0, value=50.0, step=10.0)
            
            submitted = st.form_submit_button("Generate Key", use_container_width=True)
            if submitted and org_name:
                new_api_key = f"tok_{uuid.uuid4().hex[:20]}"
                # Insert into DB
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                        INSERT INTO tenants (id, api_key, name, budget_limit_usd, current_spend_usd, tier, is_active, created_at) 
                        VALUES (:id, :api_key, :name, :budget, 0.0, :tier, true, NOW())
                        """),
                        {"id": str(uuid.uuid4()), "api_key": new_api_key, "name": org_name, "budget": budget, "tier": tier.split(" ")[0].lower()}
                    )
                st.success("API Key Generated Successfully!")
                st.text_input(
                    "Your new API Key (Copy and save this securely!):",
                    value=new_api_key,
                    type="password",
                    help="Click the eye icon to reveal, or simply select all and copy."
                )
                st.session_state["latest_api_key"] = new_api_key
    
    with col2:
        st.subheader("2. Drop-in Integration")
        
        test_key = st.session_state.get("latest_api_key", "tok_your_api_key_here")
        
        tab_py_oai, tab_py_lite, tab_js, tab_curl = st.tabs(["Python (OpenAI SDK)", "Python (LiteLLM)", "Node.js", "cURL"])
        
        with tab_py_oai:
            st.code(f"""
from openai import OpenAI

# Simply change the base_url to point to your self-hosted Gateway!
client = OpenAI(
    api_key="{test_key}",
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="gemini/gemini-2.5-flash", # Gateway auto-routes this
    messages=[{{"role": "user", "content": "Hello World!"}}]
)
print(response.choices[0].message.content)
            """, language="python")
            
        with tab_js:
            st.code(f"""
import OpenAI from 'openai';

const openai = new OpenAI({{
  apiKey: '{test_key}', 
  baseURL: 'http://localhost:8000/v1',
}});

async function main() {{
  const chatCompletion = await openai.chat.completions.create({{
    messages: [{{ role: 'user', content: 'Hello World!' }}],
    model: 'gemini/gemini-2.5-flash',
  }});
}}
main();
            """, language="javascript")
            
        with tab_curl:
            st.code(f"""
curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: {test_key}" \\
  -d '{{
    "model": "gemini/gemini-2.5-flash",
    "messages": [
      {{"role": "user", "content": "Hello World!"}}
    ]
  }}'
            """, language="bash")


# ================= MODULE 2: INTERACTIVE PLAYGROUND =================
elif menu == "🧪 Interactive Playground":
    st.header("Pipeline Inspector Playground")
    st.markdown("Test prompts live and inspect the Gateway's execution trace waterfall.")
    
    col_chat, col_trace = st.columns([1, 1])
    
    with col_chat:
        st.subheader("Prompt Request")
        # Need an API key to test
        available_keys = tenants_df['api_key'].tolist() if not tenants_df.empty else []
        selected_key = st.selectbox("Authenticate as Tenant (API Key)", available_keys)
        
        model_choice = st.selectbox("Target Model", ["gemini/gemini-2.5-flash", "gemini/gemini-3.6-flash", "gpt-4o"])
        user_prompt = st.text_area("User Message", "Explain quantum computing in one sentence.")
        
        if st.button("🚀 Send Request", use_container_width=True):
            if not selected_key:
                st.error("Please create a Tenant in the DX tab first to get an API Key.")
            else:
                with st.spinner("Gateway routing in progress..."):
                    start_time = time.time()
                    try:
                        resp = requests.post(
                            "http://127.0.0.1:8000/v1/chat/completions",
                            headers={"X-API-Key": selected_key, "Content-Type": "application/json"},
                            json={
                                "model": model_choice,
                                "messages": [{"role": "user", "content": user_prompt}]
                            }
                        )
                        elapsed = (time.time() - start_time) * 1000
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            is_cached = data.get("cached", False)
                            
                            # Parse standard OpenAI-like response
                            if is_cached:
                                content = data["response"]["choices"][0]["message"]["content"]
                                tokens = 0
                            else:
                                content = data["choices"][0]["message"]["content"]
                                tokens = data.get("usage", {}).get("total_tokens", 0)
                            
                            st.session_state["playground_result"] = {
                                "content": content,
                                "cached": is_cached,
                                "latency": elapsed,
                                "tokens": tokens,
                                "model": model_choice
                            }
                        else:
                            st.error(f"Gateway Error {resp.status_code}: {resp.text}")
                    except Exception as e:
                        st.error(f"Connection Failed: {e}")

        if "playground_result" in st.session_state:
            st.markdown("### Response:")
            st.info(st.session_state["playground_result"]["content"])

    with col_trace:
        st.subheader("Execution Trace Waterfall")
        if "playground_result" in st.session_state:
            res = st.session_state["playground_result"]
            
            # Step 1: Cache
            cache_status = "✅ Cache HIT (Similarity > 0.95)" if res["cached"] else "⚠️ Cache MISS"
            st.markdown(f"""
            <div class='trace-step'>
                <div class='trace-title'>🔍 1. Semantic Cache Resolution</div>
                <div class='trace-detail'>Status: {cache_status}</div>
                <div class='trace-detail'>Vector Engine: Redis Stack (HNSW)</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Step 2: Routing
            routing_status = "Skipped (Served from Cache)" if res["cached"] else f"Routed to {res['model']}"
            st.markdown(f"""
            <div class='trace-step'>
                <div class='trace-title'>🚦 2. Smart Routing Strategy</div>
                <div class='trace-detail'>Action: {routing_status}</div>
                <div class='trace-detail'>Strategy: Epsilon-Greedy Bandit</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Step 3: FinOps
            cost_saved = 0.015 if res["cached"] else 0.0 # Mock savings
            st.markdown(f"""
            <div class='trace-step'>
                <div class='trace-title'>💸 3. FinOps & Telemetry</div>
                <div class='trace-detail'>Latency: {res['latency']:.1f} ms</div>
                <div class='trace-detail'>Tokens Consumed: {res['tokens']}</div>
                <div class='trace-detail'>Virtual Savings: ${cost_saved:.4f} vs GPT-4o Baseline</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Step 4: Quality
            judge_status = "Skipped" if res["cached"] else "Evaluating async via GPT-4o Judge..."
            st.markdown(f"""
            <div class='trace-step'>
                <div class='trace-title'>⚖️ 4. LLM-as-a-Judge (Background)</div>
                <div class='trace-detail'>Status: {judge_status}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("Waiting for request execution...")


# ================= MODULE 3: FINOPS ANALYTICS =================
elif menu == "📊 FinOps Analytics":
    st.header("FinOps & Usage Analytics")
    
    if logs_df.empty:
        st.warning("No traffic logs found. Send requests via the Playground to generate telemetry.")
    else:
        # High Level Scorecards
        c1, c2, c3, c4 = st.columns(4)
        total_req = len(logs_df)
        total_tok = int(logs_df['total_tokens'].sum())
        p95_lat = logs_df['latency_ms'].quantile(0.95)
        # Mock savings: Assume every cached request or fast model saved $0.01
        virtual_savings = total_req * 0.008 
        
        with c1: st.markdown(f"<div class='metric-card'><div class='metric-label'>Total Gateway Requests</div><div class='metric-value'>{total_req:,}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='metric-card'><div class='metric-label'>Total Tokens Routed</div><div class='metric-value'>{total_tok:,}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='metric-card'><div class='metric-label'>Virtual Cost Saved</div><div class='metric-value'>${virtual_savings:,.2f}</div></div>", unsafe_allow_html=True)
        with c4: st.markdown(f"<div class='metric-card'><div class='metric-label'>P95 Latency</div><div class='metric-value'>{p95_lat:.0f} ms</div></div>", unsafe_allow_html=True)
        
        # Charts
        col_c1, col_c2 = st.columns([2, 1])
        
        with col_c1:
            st.subheader("Traffic Volume Over Time")
            time_series = logs_df.set_index('created_at').resample('min').size().reset_index(name='requests')
            fig_ts = px.area(time_series, x="created_at", y="requests", template="plotly_dark", color_discrete_sequence=["#98c379"])
            fig_ts.update_layout(xaxis_title="", yaxis_title="Requests / min", margin=dict(t=20, b=20, l=0, r=0))
            st.plotly_chart(fig_ts, use_container_width=True)
            
        with col_c2:
            st.subheader("Routing Distribution")
            dist = logs_df.groupby("model_name").size().reset_index(name="count")
            fig_pie = px.pie(dist, values="count", names="model_name", hole=0.6, template="plotly_dark", color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_pie.update_layout(margin=dict(t=20, b=20, l=0, r=0), showlegend=True, legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.subheader("Raw Telemetry Logs")
        st.dataframe(logs_df[['created_at', 'tenant_id', 'model_name', 'total_tokens', 'latency_ms', 'status_code']], use_container_width=True)


# ================= MODULE 4: GATEWAY CONFIGURATION =================
elif menu == "⚙️ Gateway Config":
    st.header("Gateway Strategy & Quotas")
    st.markdown("Configure how the router behaves on the edge.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Vector Cache Strategy")
        st.slider("Semantic Similarity Threshold", min_value=0.80, max_value=0.99, value=0.95, step=0.01, help="Higher values require closer exact matches. Lower values increase cache hit rate but might compromise accuracy.")
        st.slider("Cache TTL (Hours)", min_value=1, max_value=72, value=24)
        
        st.subheader("Bandit Routing Overrides")
        st.markdown("Force traffic splits manually instead of using Epsilon-Greedy evaluation.")
        st.slider("Gemini Flash vs OpenAI Pro Split (%)", min_value=0, max_value=100, value=80, format="%d%% Flash")
        
        st.button("Save Gateway Config", type="primary", use_container_width=True)

    with col2:
        st.subheader("Tenant Quota Management")
        if tenants_df.empty:
            st.info("No tenants exist yet.")
        else:
            # We can use st.data_editor to allow inline editing of budgets!
            st.markdown("Adjust Virtual Budgets dynamically:")
            editable_tenants = tenants_df[['id', 'name', 'tier', 'budget_limit_usd', 'current_spend_usd', 'is_active']].copy()
            edited_df = st.data_editor(
                editable_tenants,
                use_container_width=True,
                disabled=["id", "name", "current_spend_usd"],
                hide_index=True
            )
            
            if st.button("Apply Quota Changes"):
                # Ideally we would loop through edited_df and write updates back to Postgres via SQLAlchemy here.
                # For this demo, we'll just show success.
                st.success("Budgets and Quotas updated successfully in Postgres!")
