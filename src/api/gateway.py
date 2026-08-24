import time
import json
import mlflow
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import litellm
from pydantic import BaseModel
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.api.dependencies import verify_tenant
from src.core.database import get_db
from src.core.redis import get_redis
from src.models.tenant import Tenant
from src.models.request_log import RequestLog
from src.services.semantic_cache import get_semantic_cache, set_semantic_cache
from src.services.routing import main_router
from src.services.llm_judge import judge_response

router = APIRouter(prefix="/v1", tags=["Gateway"])

class ChatCompletionRequest(BaseModel):
    model: str | None = None  # Allow missing model so we can auto-route
    messages: list[dict[str, Any]]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False

async def log_request_to_db(db: AsyncSession, log_data: dict):
    req_log = RequestLog(**log_data)
    db.add(req_log)
    await db.commit()

@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(verify_tenant),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db)
):
    # Flatten prompt for cache
    prompt_text = "\n".join([m.get("content", "") for m in request.messages])
    
    # 1. Semantic Cache Check
    cached_resp = await get_semantic_cache(redis, prompt_text)
    if cached_resp:
        return {"cached": True, "response": json.loads(cached_resp)}

    # 2. A/B Routing
    model_to_use = request.model or main_router.select_route()
    
    start_time = time.time()
    try:
        # 3. Tracing with MLflow and Provider Call
        with mlflow.start_run(run_name=f"Gateway-{tenant.id}") as run:
            mlflow.log_param("model", model_to_use)
            mlflow.log_param("tenant_id", tenant.id)
            
            response = await litellm.acompletion(
                model=model_to_use,
                messages=request.messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                user=tenant.id
            )
            
            latency = (time.time() - start_time) * 1000
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            mlflow.log_metric("latency_ms", latency)
            mlflow.log_metric("total_tokens", prompt_tokens + completion_tokens)
            
            resp_text = response.choices[0].message.content
            
            # 4. LLM-as-a-Judge (Background Task)
            # Evaluate quality and update bandit route score
            async def evaluate_and_cache(p, r, r_json, m):
                score = await judge_response(p, r)
                main_router.update_score(m, score)
                # Cache if score is decent
                if score >= 0.7:
                    await set_semantic_cache(redis, p, json.dumps(r_json))
            
            background_tasks.add_task(
                evaluate_and_cache, 
                prompt_text, 
                resp_text, 
                response.model_dump(), 
                model_to_use
            )
            
            # 5. Log to DB
            log_data = {
                "tenant_id": tenant.id,
                "model_name": model_to_use,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": latency,
                "route_used": model_to_use,
                "status_code": 200
            }
            background_tasks.add_task(log_request_to_db, db, log_data)
            
            return response

    except litellm.exceptions.RateLimitError as e:
        raise HTTPException(status_code=429, detail=f"Provider Rate Limit: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gateway Error: {str(e)}")
