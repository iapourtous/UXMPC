"""
HTTP Client Pool

Singleton HTTP client with connection pooling for better performance.
This module provides a reusable async HTTP client to avoid creating
new connections for each request.
"""

import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class HTTPClientPool:
    """Singleton HTTP client pool manager"""
    
    _instance: Optional['HTTPClientPool'] = None
    _client: Optional[httpx.AsyncClient] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self._client = None
            self.config = {
                "limits": httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30
                ),
                "timeout": httpx.Timeout(
                    connect=5.0,
                    read=30.0,
                    write=30.0,
                    pool=5.0
                ),
                "follow_redirects": True,
                "http2": False  # Disabled until h2 package is installed
            }
    
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the singleton HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(**self.config)
            logger.info("Created new HTTP client with connection pooling")
        return self._client
    
    async def close(self):
        """Close the HTTP client and cleanup connections"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Closed HTTP client pool")
    
    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Make an HTTP request using the pooled client
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Target URL
            **kwargs: Additional arguments for httpx request
        
        Returns:
            httpx.Response object
        """
        client = await self.get_client()
        
        # Override timeout if provided in kwargs
        if "timeout" in kwargs:
            timeout_value = kwargs.pop("timeout")
            if isinstance(timeout_value, (int, float)):
                kwargs["timeout"] = httpx.Timeout(timeout_value)
        
        return await client.request(method, url, **kwargs)
    
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Convenience method for GET requests"""
        return await self.request("GET", url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Convenience method for POST requests"""
        return await self.request("POST", url, **kwargs)
    
    async def put(self, url: str, **kwargs) -> httpx.Response:
        """Convenience method for PUT requests"""
        return await self.request("PUT", url, **kwargs)
    
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """Convenience method for DELETE requests"""
        return await self.request("DELETE", url, **kwargs)
    
    async def stream(
        self,
        method: str,
        url: str,
        **kwargs
    ):
        """
        Stream response using the pooled client
        
        Args:
            method: HTTP method
            url: Target URL
            **kwargs: Additional arguments
        
        Yields:
            Response chunks
        """
        client = await self.get_client()
        
        async with client.stream(method, url, **kwargs) as response:
            async for chunk in response.aiter_bytes():
                yield chunk


# Global singleton instance
http_client_pool = HTTPClientPool()


async def get_http_client() -> httpx.AsyncClient:
    """
    Get the global HTTP client instance
    
    Returns:
        Shared httpx.AsyncClient instance with connection pooling
    """
    return await http_client_pool.get_client()


async def cleanup_http_client():
    """Cleanup the global HTTP client on shutdown"""
    await http_client_pool.close()