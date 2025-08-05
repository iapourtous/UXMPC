"""
MCP Agent Tools for External MCP Server Integration

This module provides tools that agents can use to interact with external MCP servers,
combining local services with external MCP capabilities.
"""

from typing import Dict, Any, List, Optional, Union
from app.services.mcp_connection_service import mcp_connection_service
from app.services.mcp_client_service import mcp_client_service
from app.services.mcp_auth_service import mcp_auth_service
from app.core.agent_tools import AgentTools
from app.models.mcp_connection import MCPToolCall, MCPToolResult
import logging

logger = logging.getLogger(__name__)


class MCPAgentTools:
    """Tools for agents to interact with external MCP servers"""
    
    def __init__(self, agent_tools: AgentTools):
        self.agent_tools = agent_tools
    
    async def get_local_tools(self) -> List[Dict[str, Any]]:
        """Get all local MCP tools (internal services)"""
        try:
            # Get all active services from the local system
            from app.services.service_crud import service_crud
            services = await service_crud.get_all(active_only=True)
            
            tools = []
            for service in services:
                if service.service_type == "tool":
                    tool_info = {
                        "name": service.name,
                        "description": service.description or f"Local service: {service.name}",
                        "source": "local",
                        "service_id": service.id,
                        "route": service.route,
                        "method": service.method,
                        "parameters": {
                            param.name: {
                                "type": param.type,
                                "description": param.description,
                                "required": param.required,
                                "default": param.default
                            }
                            for param in service.params
                        }
                    }
                    tools.append(tool_info)
            
            return tools
            
        except Exception as e:
            logger.error(f"Failed to get local tools: {e}")
            return []
    
    async def get_mcp_tools_for_agent(self, agent_mcp_connections: List[str]) -> List[Dict[str, Any]]:
        """Get all MCP tools available to an agent"""
        if not agent_mcp_connections:
            return []
        
        all_tools = []
        
        for connection_id in agent_mcp_connections:
            try:
                # Get connection info
                connection = await mcp_connection_service.get_connection(connection_id)
                if not connection or connection.status != "active":
                    continue
                
                # Get tools from the MCP server
                tools = await mcp_client_service.get_available_tools(connection_id)
                
                # Enhance tools with connection info
                for tool in tools:
                    enhanced_tool = {
                        **tool,
                        "source": "mcp_external",
                        "connection_id": connection_id,
                        "connection_name": connection.name,
                        "server_url": connection.server_url
                    }
                    all_tools.append(enhanced_tool)
                    
            except Exception as e:
                logger.error(f"Failed to get tools from connection {connection_id}: {e}")
                continue
        
        return all_tools
    
    async def get_all_tools_for_agent(self, agent_mcp_connections: List[str]) -> List[Dict[str, Any]]:
        """Get combined local and external MCP tools for an agent"""
        local_tools = await self.get_local_tools()
        mcp_tools = await self.get_mcp_tools_for_agent(agent_mcp_connections)
        
        return local_tools + mcp_tools
    
    async def execute_tool_for_agent(
        self, 
        agent_mcp_connections: List[str], 
        tool_name: str, 
        parameters: Dict[str, Any],
        mcp_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a tool (local or external MCP) for an agent"""
        
        # First, try to find the tool among available ones
        all_tools = await self.get_all_tools_for_agent(agent_mcp_connections)
        
        target_tool = None
        for tool in all_tools:
            if tool["name"] == tool_name:
                target_tool = tool
                break
        
        if not target_tool:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found in available tools",
                "available_tools": [tool["name"] for tool in all_tools]
            }
        
        # Execute based on tool source
        if target_tool["source"] == "local":
            return await self._execute_local_tool(target_tool, parameters)
        elif target_tool["source"] == "mcp_external":
            return await self._execute_mcp_tool(target_tool, parameters, mcp_config or {})
        else:
            return {
                "success": False,
                "error": f"Unknown tool source: {target_tool['source']}"
            }
    
    async def _execute_local_tool(self, tool: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a local service tool"""
        try:
            # Use the existing agent tools to test the service
            service_id = tool["service_id"]
            
            # Test the service with the provided parameters
            result = await self.agent_tools.test_service(service_id, parameters)
            
            return {
                "success": result.get("success", False),
                "result": result.get("response"),
                "error": result.get("error"),
                "source": "local",
                "tool_name": tool["name"],
                "execution_time": result.get("response_time")
            }
            
        except Exception as e:
            logger.error(f"Failed to execute local tool {tool['name']}: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "local",
                "tool_name": tool["name"]
            }
    
    async def _execute_mcp_tool(
        self, 
        tool: Dict[str, Any], 
        parameters: Dict[str, Any],
        mcp_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an external MCP tool"""
        try:
            connection_id = tool["connection_id"]
            tool_name = tool["name"]
            
            # Apply tool filtering if configured
            allowed_tools = mcp_config.get("allowed_tools", [])
            blocked_tools = mcp_config.get("blocked_tools", [])
            
            if allowed_tools and tool_name not in allowed_tools:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not in allowed tools list",
                    "source": "mcp_external"
                }
            
            if tool_name in blocked_tools:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' is blocked",
                    "source": "mcp_external"
                }
            
            # Execute the tool
            result = await mcp_client_service.execute_tool(connection_id, tool_name, parameters)
            
            # Convert MCPToolResult to standard format
            return {
                "success": result.success,
                "result": result.result,
                "error": result.error,
                "source": "mcp_external",
                "tool_name": tool_name,
                "connection_name": tool["connection_name"],
                "execution_time": result.execution_time,
                "server_info": result.server_info
            }
            
        except Exception as e:
            logger.error(f"Failed to execute MCP tool {tool['name']}: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "mcp_external",
                "tool_name": tool["name"]
            }
    
    async def get_tool_info(self, agent_mcp_connections: List[str], tool_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific tool"""
        all_tools = await self.get_all_tools_for_agent(agent_mcp_connections)
        
        for tool in all_tools:
            if tool["name"] == tool_name:
                return tool
        
        return None
    
    async def list_connections_for_agent(self, agent_mcp_connections: List[str]) -> List[Dict[str, Any]]:
        """List all MCP connections available to an agent"""
        if not agent_mcp_connections:
            return []
        
        connections_info = []
        
        for connection_id in agent_mcp_connections:
            try:
                connection = await mcp_connection_service.get_connection(connection_id)
                if connection:
                    # Get cached server info
                    server_cache = await mcp_client_service.get_cached_server_info(connection_id)
                    
                    connection_info = {
                        "id": connection.id,
                        "name": connection.name,
                        "description": connection.description,
                        "status": connection.status,
                        "server_url": connection.server_url,
                        "transport_type": connection.transport_type,
                        "auth_type": connection.auth_type,
                        "last_sync": connection.last_sync.isoformat() if connection.last_sync else None,
                        "tools_count": len(server_cache.tools) if server_cache else 0,
                        "resources_count": len(server_cache.resources) if server_cache else 0
                    }
                    connections_info.append(connection_info)
                    
            except Exception as e:
                logger.error(f"Failed to get connection info for {connection_id}: {e}")
                continue
        
        return connections_info
    
    async def test_mcp_connection(self, connection_id: str) -> Dict[str, Any]:
        """Test an MCP connection"""
        try:
            test_result = await mcp_client_service.test_connection(connection_id)
            
            return {
                "success": test_result.success,
                "response_time": test_result.response_time,
                "server_info": test_result.server_info,
                "tools_count": test_result.tools_count,
                "resources_count": test_result.resources_count,
                "prompts_count": test_result.prompts_count,
                "error": test_result.error,
                "tested_at": test_result.tested_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to test MCP connection {connection_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def sync_mcp_connection(self, connection_id: str) -> Dict[str, Any]:
        """Synchronize tools and capabilities from an MCP server"""
        try:
            cache = await mcp_client_service.sync_server_info(connection_id)
            
            if cache:
                return {
                    "success": True,
                    "tools_count": len(cache.tools),
                    "resources_count": len(cache.resources),
                    "prompts_count": len(cache.prompts),
                    "cached_at": cache.cached_at.isoformat(),
                    "expires_at": cache.expires_at.isoformat() if cache.expires_at else None
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to sync server information"
                }
                
        except Exception as e:
            logger.error(f"Failed to sync MCP connection {connection_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_mcp_resources(self, agent_mcp_connections: List[str]) -> List[Dict[str, Any]]:
        """Get all MCP resources available to an agent"""
        if not agent_mcp_connections:
            return []
        
        all_resources = []
        
        for connection_id in agent_mcp_connections:
            try:
                connection = await mcp_connection_service.get_connection(connection_id)
                if not connection or connection.status != "active":
                    continue
                
                resources = await mcp_client_service.get_resources(connection_id)
                
                for resource in resources:
                    enhanced_resource = {
                        **resource,
                        "source": "mcp_external",
                        "connection_id": connection_id,
                        "connection_name": connection.name
                    }
                    all_resources.append(enhanced_resource)
                    
            except Exception as e:
                logger.error(f"Failed to get resources from connection {connection_id}: {e}")
                continue
        
        return all_resources
    
    async def get_mcp_prompts(self, agent_mcp_connections: List[str]) -> List[Dict[str, Any]]:
        """Get all MCP prompts available to an agent"""
        if not agent_mcp_connections:
            return []
        
        all_prompts = []
        
        for connection_id in agent_mcp_connections:
            try:
                connection = await mcp_connection_service.get_connection(connection_id)
                if not connection or connection.status != "active":
                    continue
                
                prompts = await mcp_client_service.get_prompts(connection_id)
                
                for prompt in prompts:
                    enhanced_prompt = {
                        **prompt,
                        "source": "mcp_external",
                        "connection_id": connection_id,
                        "connection_name": connection.name
                    }
                    all_prompts.append(enhanced_prompt)
                    
            except Exception as e:
                logger.error(f"Failed to get prompts from connection {connection_id}: {e}")
                continue
        
        return all_prompts


class MCPAgentToolsSingleton:
    _instance = None
    
    def __new__(cls, agent_tools=None):
        if cls._instance is None:
            if agent_tools is None:
                raise ValueError("agent_tools required for first initialization")
            cls._instance = MCPAgentTools(agent_tools)
        return cls._instance


# Function to get tools for an agent
async def get_all_tools_for_agent(agent_mcp_connections: List[str], agent_tools: AgentTools) -> List[Dict[str, Any]]:
    """Convenience function to get all tools for an agent"""
    mcp_tools = MCPAgentTools(agent_tools)
    return await mcp_tools.get_all_tools_for_agent(agent_mcp_connections)


async def execute_tool_for_agent(
    agent_mcp_connections: List[str],
    tool_name: str,
    parameters: Dict[str, Any],
    agent_tools: AgentTools,
    mcp_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function to execute a tool for an agent"""
    mcp_tools = MCPAgentTools(agent_tools)
    return await mcp_tools.execute_tool_for_agent(
        agent_mcp_connections, 
        tool_name, 
        parameters, 
        mcp_config
    )