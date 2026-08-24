import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="LLM Gateway Dashboard", 
    page_icon="🚀", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for aesthetics
st.markdown("""
<style>
    .reportview-container .main .block-container{
        padding-top: 2rem;
    }
    .metric-card {
        background-color: #1e1e1e;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #333;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
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
engine = create_engine(DB_URL)

@st.cache_data(ttl=5) # 5 seconds TTL for fast updates
def load_data():
    try:
        logs_df = pd.read_sql("SELECT * FROM request_logs ORDER BY created_at DESC", engine)
        tenants_df = pd.read_sql("SELECT * FROM tenants", engine)
        
        # Ensure datetime formats
        if not logs_df.empty:
            logs_df['created_at'] = pd.to_datetime(logs_df['created_at'])
            
        return logs_df, tenants_df
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return pd.DataFrame(), pd.DataFrame()

# ================= SIDEBAR =================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/8636/8636984.png", width=60)
    st.title("Filters & Controls")
    
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        
    st.markdown("---")
    
    # Load raw data for filtering
    logs_df, tenants_df = load_data()
    
    if not logs_df.empty:
        # Tenant Filter
        all_tenants = ["All"] + logs_df['tenant_id'].unique().tolist()
        selected_tenant = st.selectbox("Select Tenant", all_tenants)
        
        # Model Filter
        all_models = ["All"] + logs_df['model_name'].unique().tolist()
        selected_model = st.selectbox("Select Model", all_models)
        
        # Date Filter
        min_date = logs_df['created_at'].min().date()
        max_date = logs_df['created_at'].max().date()
        
        # Ensure min_date and max_date are different if they are the same
        if min_date == max_date:
            import datetime
            min_date = min_date - datetime.timedelta(days=1)
            
        date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    else:
        selected_tenant = "All"
        selected_model = "All"
        date_range = None

# ================= APPLY FILTERS =================
filtered_logs = logs_df.copy()
if not filtered_logs.empty and date_range and len(date_range) == 2:
    start_date, end_date = date_range
    filtered_logs = filtered_logs[
        (filtered_logs['created_at'].dt.date >= start_date) & 
        (filtered_logs['created_at'].dt.date <= end_date)
    ]
if selected_tenant != "All":
    filtered_logs = filtered_logs[filtered_logs['tenant_id'] == selected_tenant]
if selected_model != "All":
    filtered_logs = filtered_logs[filtered_logs['model_name'] == selected_model]


# ================= MAIN AREA =================
st.title("🚀 LLM Gateway & Router Dashboard")
st.markdown("Real-time observability into LLM traffic, latency, routing, and tenant limits.")

if logs_df.empty:
    st.info("👋 Welcome! No request logs found yet. Make some requests through the API Gateway to see this dashboard come to life.")
    st.stop()

# TABS
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "⚙️ Model Performance", "👥 Tenants", "📋 Raw Logs"])

# ----------- TAB 1: OVERVIEW -----------
with tab1:
    st.subheader("Gateway Overview")
    
    # KPI Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Requests", f"{len(filtered_logs):,}")
    with c2:
        st.metric("Total Tokens Processed", f"{int(filtered_logs['total_tokens'].sum()):,}")
    with c3:
        avg_lat = filtered_logs['latency_ms'].mean()
        st.metric("Avg Latency", f"{avg_lat:.0f} ms" if pd.notnull(avg_lat) else "0 ms")
    with c4:
        error_rate = (len(filtered_logs[filtered_logs['status_code'] != 200]) / len(filtered_logs) * 100) if len(filtered_logs) > 0 else 0
        st.metric("Error Rate", f"{error_rate:.2f}%")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Time series of requests
    st.markdown("#### Request Volume Over Time")
    # Group by hour or minute depending on data spread
    if not filtered_logs.empty:
        time_series = filtered_logs.set_index('created_at').resample('H').size().reset_index(name='requests')
        fig_ts = px.area(time_series, x="created_at", y="requests", template="plotly_dark", color_discrete_sequence=["#00b4d8"])
        fig_ts.update_layout(xaxis_title="Time", yaxis_title="Number of Requests", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_ts, use_container_width=True)

# ----------- TAB 2: MODEL PERFORMANCE -----------
with tab2:
    st.subheader("Model Usage & Routing Analytics")
    colA, colB = st.columns(2)
    
    with colA:
        st.markdown("**Token Usage Distribution**")
        if not filtered_logs.empty:
            model_tokens = filtered_logs.groupby("model_name")["total_tokens"].sum().reset_index()
            fig_pie = px.pie(
                model_tokens, values="total_tokens", names="model_name", hole=0.5,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)
            
    with colB:
        st.markdown("**Average Latency per Model (ms)**")
        if not filtered_logs.empty:
            model_latency = filtered_logs.groupby("model_name")["latency_ms"].mean().reset_index()
            fig_bar = px.bar(
                model_latency, x="model_name", y="latency_ms", color="model_name",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_bar.update_layout(xaxis_title="", yaxis_title="Latency (ms)", showlegend=False, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig_bar, use_container_width=True)
            
    st.markdown("---")
    st.markdown("**Latency Distribution (Box Plot)**")
    if not filtered_logs.empty:
        fig_box = px.box(
            filtered_logs, x="model_name", y="latency_ms", color="model_name",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_box.update_layout(xaxis_title="Model", yaxis_title="Latency (ms)", showlegend=False, margin=dict(t=10))
        st.plotly_chart(fig_box, use_container_width=True)

# ----------- TAB 3: TENANTS -----------
with tab3:
    st.subheader("Tenant Budget & Status")
    
    if tenants_df.empty:
        st.warning("No tenants registered in the database.")
    else:
        # Display KPIs for tenants
        tc1, tc2, tc3 = st.columns(3)
        tc1.metric("Registered Tenants", len(tenants_df))
        tc2.metric("Active Tenants", tenants_df['is_active'].sum())
        total_budget = tenants_df['budget_limit_usd'].sum()
        tc3.metric("Total Budget Allocated", f"${total_budget:,.2f}")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Spend vs Budget visualization
        st.markdown("**Spend vs Budget per Tenant**")
        # Ensure we have some data
        if not tenants_df.empty:
            fig_budget = go.Figure()
            fig_budget.add_trace(go.Bar(
                x=tenants_df['name'], y=tenants_df['budget_limit_usd'],
                name='Budget Limit', marker_color='#2c3e50'
            ))
            fig_budget.add_trace(go.Bar(
                x=tenants_df['name'], y=tenants_df['current_spend_usd'],
                name='Current Spend', marker_color='#e74c3c'
            ))
            fig_budget.update_layout(barmode='group', template='plotly_dark', margin=dict(t=30))
            st.plotly_chart(fig_budget, use_container_width=True)
            
        st.markdown("**Tenant Directory**")
        st.dataframe(
            tenants_df[['id', 'name', 'tier', 'is_active', 'budget_limit_usd', 'current_spend_usd', 'created_at']],
            use_container_width=True
        )

# ----------- TAB 4: RAW LOGS -----------
with tab4:
    st.subheader("Raw Telemetry Logs")
    st.markdown("Explore individual request traces and telemetry.")
    
    st.dataframe(
        filtered_logs[['id', 'created_at', 'tenant_id', 'model_name', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'latency_ms', 'status_code']],
        use_container_width=True,
        height=600
    )
