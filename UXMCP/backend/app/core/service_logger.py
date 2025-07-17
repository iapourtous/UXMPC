"""
Simple logger interface for dynamic services
This provides a simple, synchronous API that dynamic services can use
"""

import asyncio
from typing import Dict, Any, Optional
from app.core.mongodb_logger import ServiceLogger as AsyncServiceLogger


class SimpleServiceLogger:
    """Simple synchronous logger for dynamic services"""
    
    def __init__(self, async_logger: AsyncServiceLogger):
        self._async_logger = async_logger
        
    def _ensure_event_loop(self):
        """Ensure we have an event loop"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
    
    def _run_async(self, coro):
        """Run async coroutine in sync context"""
        try:
            # Try to create a task if we're in an async context
            task = asyncio.create_task(coro)
            return task
        except RuntimeError:
            # We're in a sync context, use run_until_complete
            loop = self._ensure_event_loop()
            return loop.run_until_complete(coro)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._run_async(self._async_logger.debug(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._run_async(self._async_logger.info(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._run_async(self._async_logger.warning(message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._run_async(self._async_logger.error(message, **kwargs))
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._run_async(self._async_logger.critical(message, **kwargs))
    
    # Convenience methods for common logging patterns
    def log_api_call(self, url: str, method: str = "GET", **kwargs):
        """Log an API call"""
        self.info(f"API call: {method} {url}", url=url, method=method, **kwargs)
    
    def log_api_response(self, url: str, status_code: int, **kwargs):
        """Log an API response"""
        level = "info" if 200 <= status_code < 400 else "error"
        getattr(self, level)(f"API response: {status_code} from {url}", 
                            url=url, status_code=status_code, **kwargs)
    
    def log_exception(self, message: str, exception: Exception):
        """Log an exception with traceback"""
        self.error(message, error=str(exception), exception_type=type(exception).__name__)
    
    def log_data_processing(self, message: str, data: Any, **kwargs):
        """Log data processing steps"""
        self.debug(message, data=data, **kwargs)


def create_service_logger_class():
    """Create a logger class that can be instantiated in dynamic code"""
    
    class DynamicServiceLogger:
        """Logger class for use in dynamic service code"""
        
        def __init__(self):
            # These will be injected by the dynamic router
            self._logger = None
        
        def _log(self, level: str, message: str, **kwargs):
            """Internal log method"""
            if self._logger:
                getattr(self._logger, level)(message, **kwargs)
            else:
                # Fallback to print if logger not injected
                print(f"[{level.upper()}] {message} {kwargs if kwargs else ''}")
        
        def debug(self, message: str, **kwargs):
            """Log debug message"""
            self._log("debug", message, **kwargs)
        
        def info(self, message: str, **kwargs):
            """Log info message"""
            self._log("info", message, **kwargs)
        
        def warning(self, message: str, **kwargs):
            """Log warning message"""
            self._log("warning", message, **kwargs)
        
        def error(self, message: str, **kwargs):
            """Log error message"""
            self._log("error", message, **kwargs)
        
        def critical(self, message: str, **kwargs):
            """Log critical message"""
            self._log("critical", message, **kwargs)
    
    return DynamicServiceLogger