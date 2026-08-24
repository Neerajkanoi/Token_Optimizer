import os
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

st.set_page_config(page_title="LLM Gateway Dashboard", layout="wide")

# Synchronous connection for Pandas
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin_password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "gateway_db")

DB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
engine = create_engine(DB_URL)

st.title("🚀 LLM Gateway & Router Dashboard")
st.markdown("Monitor tenant usage, rate limits, latency, and model routing decisions in real-time.")

@st.cache_data(ttl=10)
def load_data():
    try:
        logs_df = pd.read_sql("SELECT * FROM request_logs", engine)
        tenants_df = pd.read_sql("SELECT * FROM tenants", engine)
        return logs_df, tenants_df
    except Exception as e:
        st.error(f"Database connection failed. Ensure PostgreSQL is running. Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

logs_df, tenants_df = load_data()

if logs_df.empty:
    st.info("No request logs found. Make some requests through the gateway to populate the dashboard.")
else:
    # Key Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Requests", len(logs_df))
    col2.metric("Total Tokens", int(logs_df["total_tokens"].sum()))
    col3.metric("Avg Latency (ms)", f"{logs_df['latency_ms'].mean():.2f}")
    col4.metric("Active Tenants", tenants_df["is_active"].sum() if not tenants_df.empty else 0)

    st.markdown("---")

    # Layout for charts
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Tokens by Model")
        model_tokens = logs_df.groupby("model_name")["total_tokens"].sum().reset_index()
        fig1 = px.pie(model_tokens, values="total_tokens", names="model_name", hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        st.subheader("Average Latency per Model")
        model_latency = logs_df.groupby("model_name")["latency_ms"].mean().reset_index()
        fig2 = px.bar(model_latency, x="model_name", y="latency_ms", color="model_name")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    st.subheader("Recent Request Logs")
    # Show most recent 100 requests sorted by created_at descending
    recent_logs = logs_df.sort_values(by="created_at", ascending=False).head(100)
    st.dataframe(
        recent_logs[["created_at", "tenant_id", "model_name", "total_tokens", "latency_ms", "status_code"]],
        use_container_width=True
    )
