import json
import logging
from typing import Optional, Any
from redis import Redis
from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None

def get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        logger.info(f"Connecting to Redis at: {settings.REDIS_URL}")
        _redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

def push_to_queue(queue_name: str, data: Any) -> int:
    try:
        r = get_redis_client()
        serialized = json.dumps(data)
        return r.rpush(queue_name, serialized)
    except Exception as e:
        logger.error(f"Failed to push to Redis queue '{queue_name}': {e}")
        return 0

def pop_from_queue(queue_name: str, timeout: int = 1) -> Optional[Any]:
    try:
        r = get_redis_client()
        res = r.blpop(queue_name, timeout=timeout)
        if res:
            _, val = res
            return json.loads(val)
        return None
    except Exception as e:
        if "timeout" not in str(e).lower():
            logger.error(f"Failed to pop from Redis queue '{queue_name}': {e}")
        return None
