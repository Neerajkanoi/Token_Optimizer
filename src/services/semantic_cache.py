import json
import uuid
import numpy as np
import litellm
from redis.asyncio import Redis

INDEX_NAME = "idx:semantic_cache"

async def init_redis_index(redis: Redis):
    """
    Initialize the Redis Vector index if it doesn't exist.
    We are using Redis Stack for vector search.
    """
    try:
        # Check if index exists
        await redis.ft(INDEX_NAME).info()
    except Exception:
        # Create index if it does not exist (HNSW index for cosine similarity)
        schema = (
            "FT.CREATE", INDEX_NAME, "ON", "HASH", "PREFIX", "1", "cache:",
            "SCHEMA", "embedding", "VECTOR", "HNSW", "6", 
            "TYPE", "FLOAT32", "DIM", "1536", "DISTANCE_METRIC", "COSINE",
            "response", "TEXT"
        )
        try:
            await redis.execute_command(*schema)
        except Exception as e:
            print(f"Warning: Failed to create Redis vector index: {e}")

async def get_semantic_cache(redis: Redis, prompt: str, threshold: float = 0.95) -> str | None:
    """
    Embed the prompt and search for a semantically similar cached response.
    """
    try:
        # Get embedding using LiteLLM
        emb_res = await litellm.aembedding(model="text-embedding-ada-002", input=prompt)
        vector = emb_res.data[0]['embedding']
        vector_bytes = np.array(vector, dtype=np.float32).tobytes()
        
        # Redis Vector Search: we want 1 result. Distance metric is cosine distance (1 - cosine_similarity)
        # So a similarity threshold of 0.95 means a distance threshold of 0.05
        query = (
            "FT.SEARCH", INDEX_NAME, "*=>[KNN 1 @embedding $vec AS distance]",
            "PARAMS", "2", "vec", vector_bytes,
            "DIALECT", "2",
            "LIMIT", "0", "1",
            "RETURN", "2", "distance", "response"
        )
        
        result = await redis.execute_command(*query)
        if result and len(result) > 1:
            # result[0] is total count
            # result[1] is the key
            # result[2] is a list of [b'distance', b'0.03', b'response', b'cached_text']
            # We parse the flat list
            fields = result[2]
            distance = float(fields[1])
            if distance <= (1.0 - threshold):
                return fields[3].decode('utf-8')
    except Exception as e:
        print(f"Semantic Cache Error: {e}")
    return None

async def set_semantic_cache(redis: Redis, prompt: str, response: str):
    """
    Cache the response with its prompt embedding.
    """
    try:
        emb_res = await litellm.aembedding(model="text-embedding-ada-002", input=prompt)
        vector = emb_res.data[0]['embedding']
        vector_bytes = np.array(vector, dtype=np.float32).tobytes()
        
        key = f"cache:{uuid.uuid4()}"
        await redis.hset(key, mapping={
            "embedding": vector_bytes,
            "response": response
        })
        # Optional: Expire after 24h
        await redis.expire(key, 86400)
    except Exception as e:
        print(f"Failed to set semantic cache: {e}")
