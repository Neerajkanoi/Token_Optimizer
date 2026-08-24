#!/bin/bash

echo "🚀 Starting Multi-Tenant LLM Gateway..."

# Start FastAPI in the background
echo "🟢 Starting FastAPI server (Port 8000)..."
./venv/bin/uvicorn src.main:app --reload &
FASTAPI_PID=$!

# Start Streamlit in the background
echo "🔵 Starting Streamlit Dashboard (Port 8501)..."
./venv/bin/streamlit run dashboard/app.py &
STREAMLIT_PID=$!

echo "✅ Both services are running!"
echo "   - API Gateway: http://127.0.0.1:8000"
echo "   - Dashboard: http://localhost:8501"
echo "Press [CTRL+C] to stop both services."

# Trap SIGINT (Ctrl+C) and terminate the background processes
trap "echo '🛑 Shutting down services...'; kill $FASTAPI_PID $STREAMLIT_PID; exit" SIGINT SIGTERM

# Wait to keep the script running
wait $FASTAPI_PID $STREAMLIT_PID
