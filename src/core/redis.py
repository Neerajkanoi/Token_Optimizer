from redis.asyncio import Redis
from src.core.config import settings

class RedisClient:
    _instance: Redis | None = None

    @classmethod
    def get_instance(cls) -> Redis:
        if cls._instance is None:
            cls._instance = Redis.from_url(
                settings.redis_url, 
                decode_responses=True
            )
        return cls._instance

async def get_redis() -> Redis:
    """
    FastAPI dependency for Redis connection.
    """
    return RedisClient.get_instance()
