from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager
import mlflow
from src.api.gateway import router as gateway_router
from src.core.redis import get_redis
from src.services.semantic_cache import init_redis_index
from src.core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    redis = await get_redis()
    await init_redis_index(redis)
    
    # Configure MLflow
    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    mlflow.set_experiment("llm_gateway_traces")
    yield
    # Shutdown logic if needed

app = FastAPI(
    title="Multi-Tenant LLM Gateway",
    description="High-performance async API Gateway for LLM routing and rate limiting.",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(gateway_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Multi-Tenant LLM Gateway. Documentation is available at /docs"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
