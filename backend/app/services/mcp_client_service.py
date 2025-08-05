from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import asyncio
import httpx
import json
import logging
from app.core.database import get_database
from app.models.mcp_connection import (
    MCPConnection, 
    MCPServerCache, 
    MCPToolCall, 
    MCPToolResult,
    MCPConnectionTest
)
from app.services.mcp_connection_service import mcp_connection_service
from app.services.mcp_auth_service import mcp_auth_service

logger = logging.getLogger(__name__)


class MCPClientSession:
    """Represents an active session with an MCP server"""
    
    def __init__(self, connection: MCPConnection):
        self.connection = connection
        self.client: Optional[httpx.AsyncClient] = None
        self.connected = False
        self.last_activity = datetime.utcnow()
        self.tools_cache: List[Dict[str, Any]] = []
        self.resources_cache: List[Dict[str, Any]] = []
        self.prompts_cache: List[Dict[str, Any]] = []
    
    async def connect(self) -> bool:
        """Establish connection to MCP server"""
        try:
            # Create HTTP client with appropriate headers
            headers = await self._get_auth_headers()
            timeout = self.connection.config.get("timeout", 30)
            
            self.client = httpx.AsyncClient(
                headers=headers,
                timeout=timeout
            )
            
            # Test connection with server info request
            server_info = await self._get_server_info()
            if server_info:
                self.connected = True
                self.last_activity = datetime.utcnow()
                logger.info(f"Connected to MCP server: {self.connection.name}")
                return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.connection.name}: {e}")
            await self.disconnect()
        
        return False
    
    async def disconnect(self):
        """Close connection to MCP server"""
        if self.client:
            await self.client.aclose()
            self.client = None
        
        self.connected = False
        logger.info(f"Disconnected from MCP server: {self.connection.name}")
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests"""
        headers = {"Content-Type": "application/json"}
        
        if self.connection.auth_type == "none":
            return headers
        
        # Get valid token
        token = await mcp_auth_service.get_valid_token(self.connection.id)
        if not token:
            logger.warning(f"No valid token for connection {self.connection.name}")
            return headers
        
        if self.connection.auth_type == "oauth":
            headers["Authorization"] = f"Bearer {token}"
        elif self.connection.auth_type == "api_key":
            # Check config for API key header name
            api_key_header = self.connection.config.get("api_key_header", "X-API-Key")
            headers[api_key_header] = token
        elif self.connection.auth_type == "basic":
            headers["Authorization"] = f"Basic {token}"
        
        return headers
    
    async def _send_mcp_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Send MCP protocol request to server"""
        if not self.client:
            return None
        
        try:
            # MCP protocol message
            message = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method
            }
            
            if params:
                message["params"] = params
            
            headers = await self._get_auth_headers()
            headers.update({
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json"
            })
            
            response = await self.client.post(
                self.connection.server_url.rstrip('/'),
                json=message,
                headers=headers
            )
            
            if response.status_code == 200:
                # Handle SSE response format
                response_text = response.text
                if response_text.startswith("event: message\ndata: "):
                    # Parse SSE format
                    data_line = response_text.split("data: ", 1)[1].strip()
                    result = json.loads(data_line)
                else:
                    # Parse regular JSON
                    result = response.json()
                
                if "error" in result:
                    logger.error(f"MCP error: {result['error']}")
                    return None
                return result.get("result")
            else:
                logger.warning(f"MCP request failed: {response.status_code} - {response.text}")
                return None
                    
        except Exception as e:
            logger.error(f"Failed to send MCP request: {e}")
            return None
    
    async def _get_server_info(self) -> Optional[Dict[str, Any]]:
        """Get server information using MCP protocol"""
        return await self._send_mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "UXMCP",
                "version": "1.0.0"
            }
        })
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from MCP server using MCP protocol"""
        if not self.connected or not self.client:
            return []
        
        try:
            result = await self._send_mcp_request("tools/list")
            if result and "tools" in result:
                self.tools_cache = result["tools"]
                self.last_activity = datetime.utcnow()
                logger.info(f"Retrieved {len(self.tools_cache)} tools from {self.connection.name}")
                return self.tools_cache
            else:
                logger.warning(f"No tools found in response from {self.connection.name}")
                    
        except Exception as e:
            logger.error(f"Failed to get tools from {self.connection.name}: {e}")
        
        return self.tools_cache
    
    async def get_resources(self) -> List[Dict[str, Any]]:
        """Get available resources from MCP server using MCP protocol"""
        if not self.connected or not self.client:
            return []
        
        try:
            result = await self._send_mcp_request("resources/list")
            if result and "resources" in result:
                self.resources_cache = result["resources"]
                self.last_activity = datetime.utcnow()
                logger.info(f"Retrieved {len(self.resources_cache)} resources from {self.connection.name}")
                return self.resources_cache
            else:
                logger.warning(f"No resources found in response from {self.connection.name}")
                    
        except Exception as e:
            logger.error(f"Failed to get resources from {self.connection.name}: {e}")
        
        return self.resources_cache
    
    async def get_prompts(self) -> List[Dict[str, Any]]:
        """Get available prompts from MCP server using MCP protocol"""
        if not self.connected or not self.client:
            return []
        
        try:
            result = await self._send_mcp_request("prompts/list")
            if result and "prompts" in result:
                self.prompts_cache = result["prompts"]
                self.last_activity = datetime.utcnow()
                logger.info(f"Retrieved {len(self.prompts_cache)} prompts from {self.connection.name}")
                return self.prompts_cache
            else:
                logger.warning(f"No prompts found in response from {self.connection.name}")
                    
        except Exception as e:
            logger.error(f"Failed to get prompts from {self.connection.name}: {e}")
        
        return self.prompts_cache
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> MCPToolResult:
        """Execute a tool on the MCP server using MCP protocol"""
        start_time = datetime.utcnow()
        
        if not self.connected or not self.client:
            return MCPToolResult(
                success=False,
                error="Not connected to MCP server",
                execution_time=0
            )
        
        try:
            result = await self._send_mcp_request("tools/call", {
                "name": tool_name,
                "arguments": parameters
            })
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            self.last_activity = datetime.utcnow()
            
            if result:
                return MCPToolResult(
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    server_info={"server_name": self.connection.name}
                )
            else:
                return MCPToolResult(
                    success=False,
                    error="No result returned from MCP server",
                    execution_time=execution_time
                )
                    
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Tool execution failed: {e}")
            return MCPToolResult(
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def ping(self) -> bool:
        """Ping the MCP server to check connectivity"""
        try:
            result = await self._send_mcp_request("ping")
            return result is not None
        except Exception:
            return False


class MCPClientService:
    """Service for managing MCP client connections"""
    
    def __init__(self):
        self.sessions: Dict[str, MCPClientSession] = {}
        self.cache_collection_name = "mcp_server_cache"
    
    async def connect_to_server(self, connection_id: str) -> Optional[MCPClientSession]:
        """Connect to an MCP server and return session"""
        # Get connection info
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            logger.error(f"Connection not found: {connection_id}")
            return None
        
        # Check if already connected
        if connection_id in self.sessions and self.sessions[connection_id].connected:
            return self.sessions[connection_id]
        
        # Create new session
        session = MCPClientSession(connection)
        
        # Attempt connection
        if await session.connect():
            self.sessions[connection_id] = session
            await mcp_connection_service.update_connection_status(connection_id, "active")
            return session
        else:
            await mcp_connection_service.update_connection_status(
                connection_id, 
                "error", 
                "Failed to connect to server"
            )
            return None
    
    async def disconnect(self, connection_id: str) -> None:
        """Disconnect from an MCP server"""
        if connection_id in self.sessions:
            await self.sessions[connection_id].disconnect()
            del self.sessions[connection_id]
        
        await mcp_connection_service.update_connection_status(connection_id, "inactive")
    
    async def get_available_tools(self, connection_id: str) -> List[Dict[str, Any]]:
        """Get available tools from an MCP server"""
        session = await self.connect_to_server(connection_id)
        if not session:
            return []
        
        return await session.get_tools()
    
    async def get_resources(self, connection_id: str) -> List[Dict[str, Any]]:
        """Get available resources from an MCP server"""
        session = await self.connect_to_server(connection_id)
        if not session:
            return []
        
        return await session.get_resources()
    
    async def get_prompts(self, connection_id: str) -> List[Dict[str, Any]]:
        """Get available prompts from an MCP server"""
        session = await self.connect_to_server(connection_id)
        if not session:
            return []
        
        return await session.get_prompts()
    
    async def execute_tool(self, connection_id: str, tool_name: str, params: Dict[str, Any]) -> MCPToolResult:
        """Execute a tool on an MCP server"""
        session = await self.connect_to_server(connection_id)
        if not session:
            return MCPToolResult(
                success=False,
                error=f"Could not connect to server: {connection_id}"
            )
        
        return await session.execute_tool(tool_name, params)
    
    async def test_connection(self, connection_id: str) -> MCPConnectionTest:
        """Test connection to an MCP server"""
        start_time = datetime.utcnow()
        
        session = await self.connect_to_server(connection_id)
        if not session:
            return MCPConnectionTest(
                success=False,
                error="Failed to establish connection"
            )
        
        try:
            # Get server capabilities
            tools = await session.get_tools()
            resources = await session.get_resources()
            prompts = await session.get_prompts()
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            return MCPConnectionTest(
                success=True,
                response_time=response_time,
                server_info={"name": session.connection.name},
                tools_count=len(tools),
                resources_count=len(resources),
                prompts_count=len(prompts)
            )
            
        except Exception as e:
            return MCPConnectionTest(
                success=False,
                error=str(e)
            )
    
    async def sync_server_info(self, connection_id: str) -> Optional[MCPServerCache]:
        """Synchronize and cache server information"""
        session = await self.connect_to_server(connection_id)
        if not session:
            return None
        
        try:
            # Get all server capabilities
            tools = await session.get_tools()
            resources = await session.get_resources()
            prompts = await session.get_prompts()
            server_info = await session._get_server_info()
            
            # Create cache entry
            cache = MCPServerCache(
                connection_id=connection_id,
                tools=tools,
                resources=resources,
                prompts=prompts,
                server_info=server_info or {},
                expires_at=datetime.utcnow() + timedelta(minutes=5)  # 5 minute cache
            )
            
            # Save to database
            db = get_database()
            await db[self.cache_collection_name].replace_one(
                {"connection_id": connection_id},
                cache.model_dump(),
                upsert=True
            )
            
            # Update connection sync time
            await mcp_connection_service.update_connection_status(connection_id, "active")
            
            return cache
            
        except Exception as e:
            logger.error(f"Failed to sync server info: {e}")
            return None
    
    async def get_cached_server_info(self, connection_id: str) -> Optional[MCPServerCache]:
        """Get cached server information"""
        db = get_database()
        cache_doc = await db[self.cache_collection_name].find_one({"connection_id": connection_id})
        
        if not cache_doc:
            return None
        
        # Prepare document
        if "_id" in cache_doc:
            cache_doc["id"] = str(cache_doc["_id"])
            del cache_doc["_id"]
        
        cache = MCPServerCache(**cache_doc)
        
        # Check if cache is expired
        if cache.expires_at and datetime.utcnow() > cache.expires_at:
            # Try to refresh cache
            return await self.sync_server_info(connection_id)
        
        return cache
    
    async def cleanup_inactive_sessions(self, max_idle_minutes: int = 30) -> int:
        """Clean up inactive sessions"""
        cleaned = 0
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_idle_minutes)
        
        for connection_id, session in list(self.sessions.items()):
            if session.last_activity < cutoff_time:
                await session.disconnect()
                del self.sessions[connection_id]
                cleaned += 1
        
        return cleaned
    
    async def get_session_info(self) -> Dict[str, Any]:
        """Get information about active sessions"""
        return {
            "active_sessions": len(self.sessions),
            "connections": [
                {
                    "connection_id": conn_id,
                    "connection_name": session.connection.name,
                    "connected": session.connected,
                    "last_activity": session.last_activity.isoformat(),
                    "tools_cached": len(session.tools_cache),
                    "resources_cached": len(session.resources_cache)
                }
                for conn_id, session in self.sessions.items()
            ]
        }


class MCPClientServiceSingleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = MCPClientService()
        return cls._instance


# Global instance
mcp_client_service = MCPClientServiceSingleton()