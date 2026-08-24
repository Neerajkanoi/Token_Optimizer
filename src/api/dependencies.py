import time
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.core.database import get_db
from src.core.redis import get_redis
from src.models.tenant import Tenant

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

# Rate limiting Lua Script: Fixed window (per minute)
# KEYS[1]: rate limit key, ARGV[1]: max requests, ARGV[2]: window size in seconds
RATE_LIMIT_LUA = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[2])
end
if current > tonumber(ARGV[1]) then
    return 1
end
return 0
"""

async def verify_tenant(
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> Tenant:
    # 1. Fetch Tenant from Postgres
    stmt = select(Tenant).where(Tenant.api_key == api_key)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API Key")

    # 2. Check Budget
    if tenant.current_spend_usd >= tenant.budget_limit_usd:
        raise HTTPException(status_code=402, detail="Budget limit exceeded")

    # 3. Redis Rate Limiting (Atomic Lua)
    # E.g., limit to 100 requests per 60 seconds per tenant
    limit_key = f"rate_limit:{tenant.id}"
    max_requests = 100
    window_seconds = 60

    is_limited = await redis.eval(
        RATE_LIMIT_LUA, 
        1, 
        limit_key, 
        max_requests, 
        window_seconds
    )
    
    if is_limited == 1:
        raise HTTPException(status_code=429, detail="Too Many Requests")

    return tenant
