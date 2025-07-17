from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AppLogBase(BaseModel):
    """General application log model"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: LogLevel
    module: str
    message: str
    extra: Optional[Dict[str, Any]] = None


class AppLog(AppLogBase):
    id: Optional[str] = Field(default=None)
    
    model_config = {
        "arbitrary_types_allowed": True
    }


class ServiceLogBase(BaseModel):
    """Service-specific log model for dynamic code execution"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service_id: str
    service_name: str
    level: LogLevel
    message: str
    details: Optional[Dict[str, Any]] = None
    execution_id: str
    request_data: Optional[Dict[str, Any]] = None


class ServiceLog(ServiceLogBase):
    id: Optional[str] = Field(default=None)
    
    model_config = {
        "arbitrary_types_allowed": True
    }


class LogQuery(BaseModel):
    """Query parameters for filtering logs"""
    level: Optional[LogLevel] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    skip: int = Field(default=0, ge=0)
    search: Optional[str] = None


class ServiceLogQuery(LogQuery):
    """Query parameters specific to service logs"""
    service_id: Optional[str] = None
    execution_id: Optional[str] = None