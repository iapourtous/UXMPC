"""
Cache Service

Provides caching capabilities using Redis for improved performance.
This module handles caching of frequently accessed data like LLM profiles,
active services, tool results, etc.
"""

import json
import logging
from typing import Optional, Any, Dict
from datetime import timedelta, datetime
import redis.asyncio as redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class CacheService:
    """Redis-based cache service for UXMCP"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self.enabled = False
        
    async def connect(self):
        """Connect to Redis server"""
        try:
            # Try to connect to Redis if URL is configured
            redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379')
            if redis_url:
                self.client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=50
                )
                # Test connection
                await self.client.ping()
                self.enabled = True
                logger.info("Connected to Redis cache")
        except Exception as e:
            logger.warning(f"Redis not available, caching disabled: {e}")
            self.enabled = False
            self.client = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis cache")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.enabled or not self.client:
            return None
            
        try:
            value = await self.client.get(key)
            if value:
                # Try to parse the JSON
                data = json.loads(value)
                # Convert ISO datetime strings back to datetime objects
                return self._convert_iso_to_datetime(data)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set value in cache
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            expire: Expiration time in seconds
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.client:
            return False
            
        try:
            json_value = json.dumps(value, cls=DateTimeEncoder)
            if expire:
                await self.client.setex(key, expire, json_value)
            else:
                await self.client.set(key, json_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.enabled or not self.client:
            return False
            
        try:
            result = await self.client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.enabled or not self.client:
            return False
            
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        if not self.enabled or not self.client:
            return 0
            
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0
    
    # Specific cache methods for common data
    
    async def get_llm_profile(self, name: str) -> Optional[Dict]:
        """Get cached LLM profile"""
        return await self.get(f"llm_profile:{name}")
    
    async def set_llm_profile(self, name: str, profile: Dict) -> bool:
        """Cache LLM profile for 5 minutes"""
        return await self.set(f"llm_profile:{name}", profile, expire=300)
    
    async def get_active_services(self) -> Optional[list]:
        """Get cached list of active services"""
        return await self.get("active_services")
    
    async def set_active_services(self, services: list) -> bool:
        """Cache active services for 1 minute"""
        return await self.set("active_services", services, expire=60)
    
    async def get_tool_result(self, tool_name: str, params_hash: str) -> Optional[Any]:
        """Get cached tool result"""
        return await self.get(f"tool_result:{tool_name}:{params_hash}")
    
    async def set_tool_result(
        self,
        tool_name: str,
        params_hash: str,
        result: Any,
        expire: int = 300
    ) -> bool:
        """Cache tool result"""
        return await self.set(
            f"tool_result:{tool_name}:{params_hash}",
            result,
            expire=expire
        )
    
    async def get_agent_config(self, agent_id: str) -> Optional[Dict]:
        """Get cached agent configuration"""
        return await self.get(f"agent:{agent_id}")
    
    async def set_agent_config(self, agent_id: str, config: Dict) -> bool:
        """Cache agent configuration for 5 minutes"""
        return await self.set(f"agent:{agent_id}", config, expire=300)
    
    async def invalidate_agent(self, agent_id: str) -> bool:
        """Invalidate agent cache"""
        return await self.delete(f"agent:{agent_id}")
    
    async def invalidate_llm_profile(self, name: str) -> bool:
        """Invalidate LLM profile cache"""
        return await self.delete(f"llm_profile:{name}")
    
    def _convert_iso_to_datetime(self, obj):
        """Recursively convert ISO datetime strings back to datetime objects"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    # Try to parse ISO datetime strings
                    if 'T' in value and (value.endswith('Z') or '+' in value or value.count(':') >= 2):
                        try:
                            # Try parsing with timezone info
                            if value.endswith('Z'):
                                obj[key] = datetime.fromisoformat(value[:-1] + '+00:00')
                            else:
                                obj[key] = datetime.fromisoformat(value)
                        except (ValueError, AttributeError):
                            # Not a datetime string, keep as is
                            pass
                elif isinstance(value, (dict, list)):
                    obj[key] = self._convert_iso_to_datetime(value)
        elif isinstance(obj, list):
            return [self._convert_iso_to_datetime(item) for item in obj]
        return obj


# Global cache instance
cache_service = CacheService()


async def get_cache() -> CacheService:
    """Get the global cache service instance"""
    return cache_service