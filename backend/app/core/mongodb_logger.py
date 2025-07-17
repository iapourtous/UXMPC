import logging
from datetime import datetime
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.log import AppLog, ServiceLog, LogLevel
import asyncio
from contextlib import contextmanager
import traceback


class MongoDBHandler(logging.Handler):
    """Custom logging handler that writes to MongoDB"""
    
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str = "app_logs"):
        super().__init__()
        self.db = db
        self.collection_name = collection_name
        self._queue = asyncio.Queue()
        self._task = None
        
    def emit(self, record: logging.LogRecord):
        """Handle a log record"""
        try:
            # Map Python log levels to our LogLevel enum
            level_map = {
                logging.DEBUG: LogLevel.DEBUG,
                logging.INFO: LogLevel.INFO,
                logging.WARNING: LogLevel.WARNING,
                logging.ERROR: LogLevel.ERROR,
                logging.CRITICAL: LogLevel.CRITICAL
            }
            
            log_entry = {
                "timestamp": datetime.utcnow(),
                "level": level_map.get(record.levelno, LogLevel.INFO),
                "module": record.module,
                "message": self.format(record),
                "extra": {
                    "pathname": record.pathname,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                    "process": record.process,
                    "thread": record.thread
                }
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry["extra"]["exception"] = traceback.format_exception(*record.exc_info)
            
            # Queue the log entry for async writing
            asyncio.create_task(self._queue.put(log_entry))
            
        except Exception:
            self.handleError(record)
    
    async def start(self):
        """Start the async worker"""
        if self._task is None:
            self._task = asyncio.create_task(self._worker())
    
    async def stop(self):
        """Stop the async worker"""
        if self._task:
            await self._queue.put(None)  # Sentinel value
            await self._task
            self._task = None
    
    async def _worker(self):
        """Async worker to write logs to MongoDB"""
        collection = self.db[self.collection_name]
        
        while True:
            try:
                log_entry = await self._queue.get()
                if log_entry is None:  # Sentinel value
                    break
                
                await collection.insert_one(log_entry)
                
            except Exception as e:
                # Can't use logging here as it would create infinite loop
                print(f"Error writing log to MongoDB: {e}")


class ServiceLogger:
    """Logger for dynamic service execution"""
    
    def __init__(self, db: AsyncIOMotorDatabase, service_id: str, service_name: str, execution_id: str):
        self.db = db
        self.service_id = service_id
        self.service_name = service_name
        self.execution_id = execution_id
        self.collection = db["service_logs"]
        self._request_data = None
    
    def set_request_data(self, data: Dict[str, Any]):
        """Set request data for this execution"""
        self._request_data = data
    
    async def _log(self, level: LogLevel, message: str, details: Optional[Dict[str, Any]] = None):
        """Write a log entry to MongoDB"""
        log_entry = {
            "timestamp": datetime.utcnow(),
            "service_id": self.service_id,
            "service_name": self.service_name,
            "level": level,
            "message": message,
            "details": details or {},
            "execution_id": self.execution_id,
            "request_data": self._request_data
        }
        
        try:
            await self.collection.insert_one(log_entry)
        except Exception as e:
            # Fallback to print if MongoDB write fails
            print(f"Failed to write service log: {e}")
            print(f"Log entry: {log_entry}")
    
    async def debug(self, message: str, **kwargs):
        """Log debug message"""
        await self._log(LogLevel.DEBUG, message, kwargs if kwargs else None)
    
    async def info(self, message: str, **kwargs):
        """Log info message"""
        await self._log(LogLevel.INFO, message, kwargs if kwargs else None)
    
    async def warning(self, message: str, **kwargs):
        """Log warning message"""
        await self._log(LogLevel.WARNING, message, kwargs if kwargs else None)
    
    async def error(self, message: str, **kwargs):
        """Log error message"""
        # If there's an exception, capture the traceback
        if "exception" not in kwargs and hasattr(kwargs.get("error"), "__traceback__"):
            kwargs["exception"] = traceback.format_exc()
        await self._log(LogLevel.ERROR, message, kwargs if kwargs else None)
    
    async def critical(self, message: str, **kwargs):
        """Log critical message"""
        await self._log(LogLevel.CRITICAL, message, kwargs if kwargs else None)
    
    # Synchronous versions for convenience in dynamic code
    def debug_sync(self, message: str, **kwargs):
        """Synchronous debug log"""
        asyncio.create_task(self.debug(message, **kwargs))
    
    def info_sync(self, message: str, **kwargs):
        """Synchronous info log"""
        asyncio.create_task(self.info(message, **kwargs))
    
    def warning_sync(self, message: str, **kwargs):
        """Synchronous warning log"""
        asyncio.create_task(self.warning(message, **kwargs))
    
    def error_sync(self, message: str, **kwargs):
        """Synchronous error log"""
        asyncio.create_task(self.error(message, **kwargs))
    
    def critical_sync(self, message: str, **kwargs):
        """Synchronous critical log"""
        asyncio.create_task(self.critical(message, **kwargs))


# Global MongoDB handler instance
_mongodb_handler: Optional[MongoDBHandler] = None


def setup_mongodb_logging(db: AsyncIOMotorDatabase) -> MongoDBHandler:
    """Setup MongoDB logging handler"""
    global _mongodb_handler
    
    if _mongodb_handler is None:
        _mongodb_handler = MongoDBHandler(db)
        _mongodb_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        _mongodb_handler.setFormatter(formatter)
        
        # Add to root logger
        logging.getLogger().addHandler(_mongodb_handler)
        
        # Start the async worker
        asyncio.create_task(_mongodb_handler.start())
    
    return _mongodb_handler


async def cleanup_mongodb_logging():
    """Cleanup MongoDB logging handler"""
    global _mongodb_handler
    
    if _mongodb_handler:
        logging.getLogger().removeHandler(_mongodb_handler)
        await _mongodb_handler.stop()
        _mongodb_handler = None