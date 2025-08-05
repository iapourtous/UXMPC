from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from bson import ObjectId
import uuid


class MCPConnection(BaseModel):
    """Model for external MCP server connections"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Human-readable name for the connection (e.g., 'GitHub API', 'Google Drive')")
    description: Optional[str] = Field(None, description="Description of what this MCP server provides")
    server_url: str = Field(..., description="URL or command to connect to the MCP server")
    transport_type: Literal["stdio", "sse", "http"] = Field(default="sse", description="MCP transport protocol")
    auth_type: Literal["none", "oauth", "api_key", "basic"] = Field(default="none", description="Authentication method")
    status: Literal["active", "inactive", "auth_required", "error"] = Field(default="inactive", description="Connection status")
    config: Dict[str, Any] = Field(default={}, description="Server-specific configuration")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync: Optional[datetime] = Field(None, description="Last successful synchronization")
    last_error: Optional[str] = Field(None, description="Last error message if any")
    
    # Connection health
    last_ping: Optional[datetime] = Field(None, description="Last successful ping")
    ping_interval: int = Field(default=300, description="Ping interval in seconds")
    retry_count: int = Field(default=0, description="Current retry count for failed connections")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class MCPConnectionCreate(BaseModel):
    """Model for creating MCP connections"""
    name: str
    description: Optional[str] = None
    server_url: str
    transport_type: Literal["stdio", "sse", "http"] = "sse"
    auth_type: Literal["none", "oauth", "api_key", "basic"] = "none"
    config: Dict[str, Any] = {}


class MCPConnectionUpdate(BaseModel):
    """Model for updating MCP connections"""
    name: Optional[str] = None
    description: Optional[str] = None
    server_url: Optional[str] = None
    transport_type: Optional[Literal["stdio", "sse", "http"]] = None
    auth_type: Optional[Literal["none", "oauth", "api_key", "basic"]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[Literal["active", "inactive", "auth_required", "error"]] = None


class MCPAuth(BaseModel):
    """Model for MCP server authentication data"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connection_id: str = Field(..., description="ID of the associated MCP connection")
    access_token: str = Field(..., description="Access token for authentication")
    refresh_token: Optional[str] = Field(None, description="Refresh token if available")
    expires_at: Optional[datetime] = Field(None, description="Token expiration time")
    scopes: List[str] = Field(default=[], description="Granted OAuth scopes")
    auth_data: Dict[str, Any] = Field(default={}, description="Additional authentication data")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class MCPServerCache(BaseModel):
    """Model for caching MCP server capabilities"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    connection_id: str = Field(..., description="ID of the associated MCP connection")
    tools: List[Dict[str, Any]] = Field(default=[], description="Available tools from the server")
    resources: List[Dict[str, Any]] = Field(default=[], description="Available resources from the server")
    prompts: List[Dict[str, Any]] = Field(default=[], description="Available prompts from the server")
    server_info: Dict[str, Any] = Field(default={}, description="Server information and capabilities")
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="Cache expiration time")
    
    model_config = {
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }


class MCPAgentConfig(BaseModel):
    """Configuration for MCP integration in agents"""
    auto_sync_tools: bool = Field(default=True, description="Automatically sync tools from connected servers")
    connection_timeout: int = Field(default=30, description="Connection timeout in seconds")
    retry_attempts: int = Field(default=3, description="Number of retry attempts for failed calls")
    cache_duration: int = Field(default=300, description="Cache duration in seconds")
    max_concurrent_calls: int = Field(default=5, description="Maximum concurrent tool calls to MCP servers")
    
    # Tool filtering
    allowed_tools: List[str] = Field(default=[], description="Whitelist of allowed tools (empty = all allowed)")
    blocked_tools: List[str] = Field(default=[], description="Blacklist of blocked tools")
    
    # Error handling
    fail_on_error: bool = Field(default=False, description="Fail agent execution on MCP tool errors")
    log_all_calls: bool = Field(default=True, description="Log all MCP tool calls for debugging")


class MCPConnectionTest(BaseModel):
    """Model for connection test results"""
    success: bool
    response_time: Optional[float] = None
    server_info: Optional[Dict[str, Any]] = None
    tools_count: Optional[int] = None
    resources_count: Optional[int] = None
    prompts_count: Optional[int] = None
    error: Optional[str] = None
    tested_at: datetime = Field(default_factory=datetime.utcnow)


class MCPToolCall(BaseModel):
    """Model for MCP tool execution"""
    connection_id: str
    tool_name: str
    parameters: Dict[str, Any] = {}
    timeout: int = 30


class MCPToolResult(BaseModel):
    """Model for MCP tool execution results"""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    server_info: Optional[Dict[str, Any]] = None