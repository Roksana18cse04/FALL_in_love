import redis.asyncio as redis
import json
import os
from typing import Optional, Dict
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client for caching
redis_client: Optional[redis.Redis] = None

async def get_redis_client() -> redis.Redis:
    """Get or create Redis client"""
    global redis_client
    if redis_client is None:
        try:
            redis_client = await redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379"),
                encoding="utf-8",
                decode_responses=True
            )
            await redis_client.ping()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.warning(f"⚠️ Redis unavailable: {e}. Continuing without cache.")
            redis_client = None
    return redis_client

async def get_cached_context(cache_key: str) -> Optional[Dict]:
    """Get cached context from Redis"""
    try:
        redis_conn = await get_redis_client()
        if redis_conn is None:
            return None
        
        cached_data = await redis_conn.get(cache_key)
        if cached_data:
            logger.info(f"✅ Cache hit: {cache_key[:20]}...")
            return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"⚠️ Cache read failed: {e}")
    return None


async def set_cached_context(cache_key: str, data: Dict, ttl: int = 3600):
    """Set cached context in Redis"""
    try:
        redis_conn = await get_redis_client()
        if redis_conn is None:
            return
        
        await redis_conn.setex(
            cache_key,
            ttl,
            json.dumps(data)
        )
        logger.info(f"✅ Cached: {cache_key[:20]}...")
    except Exception as e:
        logger.warning(f"⚠️ Cache write failed: {e}")