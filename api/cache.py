"""Redis caching utilities for API."""

import functools
import hashlib
import json
from typing import Any, Callable

import redis.asyncio as redis
from db.session import settings


# Initialize Redis client
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def get_cache(key: str) -> Any | None:
    """Get value from cache.

    Args:
        key: Cache key

    Returns:
        Cached value or None
    """
    try:
        value = await redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception:
        # If cache fails, return None
        return None


async def set_cache(key: str, value: Any, ttl: int = 300) -> None:
    """Set value in cache with TTL.

    Args:
        key: Cache key
        value: Value to cache
        ttl: Time to live in seconds
    """
    try:
        await redis_client.setex(key, ttl, json.dumps(value))
    except Exception:
        # If cache fails, silently continue
        pass


async def invalidate_cache(pattern: str = "*") -> None:
    """Invalidate cache keys matching pattern.

    Args:
        pattern: Key pattern to match
    """
    try:
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
    except Exception:
        pass


def cache_response(ttl: int = 300, key_prefix: str = "") -> Callable:
    """Decorator to cache API responses.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key from function name and arguments
            # Exclude database session from key
            cache_args = {k: v for k, v in kwargs.items() if k != "db"}

            key_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": cache_args,
            }
            key_hash = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{key_hash}"

            # Try to get from cache
            cached = await get_cache(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            await set_cache(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


async def close_redis() -> None:
    """Close Redis connection."""
    await redis_client.close()
