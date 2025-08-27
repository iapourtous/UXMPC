"""
Tool Manager for Agent Executor
Handles preparation, execution, and management of tools for agents
"""
import json
import httpx
from typing import List, Dict, Any, Optional, Union
from app.models.agent import Agent
from app.services.service_crud import service_crud
from app.services.unified_logger import UnifiedLogger
import logging

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool preparation and execution for agents"""
    
    def __init__(self):
        """Initialize the tool manager"""
        pass
    
    async def prepare_tools(
        self, 
        service_names: List[str], 
        agent: Agent,
        logger: UnifiedLogger
    ) -> List[Dict[str, Any]]:
        """Prepare tool definitions from MCP services and memory tools
        
        Args:
            service_names: List of MCP service names to prepare
            agent: Agent configuration
            logger: Logger instance
            
        Returns:
            List of tool definitions in OpenAI format
        """
        tools = []
        
        # Prepare MCP service tools
        for service_name in service_names:
            service = await service_crud.get_by_name(service_name)
            if not service:
                await logger.warning(f"Service '{service_name}' not found")
                continue
            
            if not service.active:
                await logger.warning(f"Service '{service_name}' is not active")
                continue
            
            # Convert service to OpenAI tool format
            tool = {
                "type": "function",
                "function": {
                    "name": service.name,
                    "description": service.description or f"MCP service: {service.name}",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters
            for param in service.params:
                tool["function"]["parameters"]["properties"][param.name] = {
                    "type": param.type,
                    "description": param.description or param.name
                }
                if param.required:
                    tool["function"]["parameters"]["required"].append(param.name)
            
            tools.append(tool)
            await logger.debug(f"Prepared tool: {service.name}")
        
        # Add memory tools if memory is enabled
        if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
            memory_config = getattr(agent, 'memory_config', {})
            if memory_config.get('active_memory', True):
                await logger.debug("Adding memory tools")
                memory_tools = await self.create_memory_tools(agent)
                tools.extend(memory_tools)
        
        # Add external MCP tools from connections
        if hasattr(agent, 'mcp_connections') and agent.mcp_connections:
            external_tools = await self._prepare_external_mcp_tools(
                agent.mcp_connections, 
                logger
            )
            tools.extend(external_tools)
        
        return tools
    
    async def _prepare_external_mcp_tools(
        self, 
        mcp_connections: List[str], 
        logger: UnifiedLogger
    ) -> List[Dict[str, Any]]:
        """Prepare external MCP tools from connections
        
        Args:
            mcp_connections: List of MCP connection IDs
            logger: Logger instance
            
        Returns:
            List of external MCP tool definitions
        """
        from app.services.mcp_client_service import mcp_client_service
        
        tools = []
        await logger.debug(f"External MCP tools: {len(mcp_connections)} connections")
        
        for connection_id in mcp_connections:
            try:
                # Get tools from MCP connection
                mcp_tools = await mcp_client_service.get_available_tools(connection_id)
                await logger.debug(f"Retrieved {len(mcp_tools)} tools from connection {connection_id}")
                
                # Convert MCP tools to OpenAI function format
                for mcp_tool in mcp_tools:
                    tool = {
                        "type": "function",
                        "function": {
                            "name": f"mcp_{connection_id}_{mcp_tool['name']}",  # Prefix to avoid conflicts
                            "description": mcp_tool.get('description', f"MCP tool: {mcp_tool['name']}"),
                            "parameters": mcp_tool.get('inputSchema', {
                                "type": "object",
                                "properties": {},
                                "required": []
                            })
                        }
                    }
                    tools.append(tool)
                    await logger.debug(f"Prepared external MCP tool: {mcp_tool['name']} from connection {connection_id}")
                    
            except Exception as e:
                await logger.error(f"Failed to load tools from MCP connection {connection_id}: {e}")
        
        return tools
    
    async def create_memory_tools(self, agent: Agent) -> List[Dict[str, Any]]:
        """Create memory management tools for the agent
        
        Args:
            agent: Agent configuration
            
        Returns:
            List of memory tool definitions
        """
        from app.core.agent_memory_tools import MEMORY_TOOLS
        
        tools = []
        for tool_def in MEMORY_TOOLS:
            tool = {
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters (skip agent_id as it will be injected)
            for param_name, param_config in tool_def["parameters"].items():
                if param_name != "agent_id":
                    prop = {
                        "type": param_config["type"],
                        "description": param_config.get("description", "")
                    }
                    
                    # Add enum if specified
                    if "enum" in param_config:
                        prop["enum"] = param_config["enum"]
                    
                    # Add default if specified
                    if "default" in param_config:
                        prop["default"] = param_config["default"]
                    
                    tool["function"]["parameters"]["properties"][param_name] = prop
                    
                    # Add to required if needed
                    if param_config.get("required", False):
                        tool["function"]["parameters"]["required"].append(param_name)
            
            tools.append(tool)
        
        return tools
    
    async def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        logger: UnifiedLogger,
        agent: Optional[Agent] = None
    ) -> List[Dict[str, Any]]:
        """Execute tool calls by calling MCP services or memory tools
        
        Args:
            tool_calls: List of tool call dictionaries
            logger: Logger instance
            agent: Optional agent for memory tools
            
        Returns:
            List of results from tool executions
        """
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            
            # Log tool execution
            await logger.log_tool_execution(
                tool_name=tool_name,
                arguments=tool_args,
                result=None,  # Will be updated
                success=True,
                error=None
            )
            
            try:
                # Check if it's a memory tool
                if tool_name in ["memory_search", "memory_store", "memory_analyze"] and agent:
                    result = await self._execute_memory_tool(tool_name, tool_args, agent)
                    results.append(result)
                    continue
                
                # Check if it's an external MCP tool
                if tool_name.startswith("mcp_") and agent and hasattr(agent, 'mcp_connections'):
                    result = await self._execute_external_mcp_tool(tool_name, tool_args)
                    results.append(result)
                    continue
                
                # Otherwise, call the internal MCP service
                result = await self._execute_internal_service(tool_name, tool_args)
                results.append(result)
                
            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                await logger.error(error_msg, tool=tool_name)
                result = {"error": error_msg}
                results.append(result)
        
        return results
    
    async def _execute_memory_tool(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        agent: Agent
    ) -> Dict[str, Any]:
        """Execute a memory tool
        
        Args:
            tool_name: Name of the memory tool
            tool_args: Arguments for the tool
            agent: Agent instance
            
        Returns:
            Tool execution result
        """
        from app.core.agent_memory_tools import memory_search, memory_store, memory_analyze
        
        # Inject agent_id
        tool_args["agent_id"] = agent.id
        
        # Call the appropriate memory tool
        if tool_name == "memory_search":
            return await memory_search(**tool_args)
        elif tool_name == "memory_store":
            return await memory_store(**tool_args)
        elif tool_name == "memory_analyze":
            return await memory_analyze(**tool_args)
        
        return {"error": f"Unknown memory tool: {tool_name}"}
    
    async def _execute_external_mcp_tool(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an external MCP tool
        
        Args:
            tool_name: Prefixed tool name (mcp_connectionId_toolName)
            tool_args: Arguments for the tool
            
        Returns:
            Tool execution result
        """
        from app.services.mcp_client_service import mcp_client_service
        
        # Parse connection_id and tool name from prefixed name
        # Format: mcp_{connection_id}_{tool_name}
        parts = tool_name.split("_", 2)  # Split into mcp, connection_id, tool_name
        if len(parts) >= 3:
            connection_id = parts[1]
            actual_tool_name = parts[2]
            
            # Execute external MCP tool
            mcp_result = await mcp_client_service.execute_tool(connection_id, actual_tool_name, tool_args)
            
            if mcp_result.success:
                return mcp_result.result
            else:
                return {"error": f"MCP tool execution failed: {mcp_result.error}"}
        
        return {"error": f"Invalid MCP tool name format: {tool_name}"}
    
    async def _execute_internal_service(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an internal MCP service
        
        Args:
            tool_name: Service name
            tool_args: Arguments for the service
            
        Returns:
            Service execution result
        """
        service = await service_crud.get_by_name(tool_name)
        if not service:
            return {"error": f"Service '{tool_name}' not found"}
        
        # Build URL
        url = f"http://localhost:8000{service.route}"
        
        # Replace path parameters
        for param_name, param_value in tool_args.items():
            url = url.replace(f"{{{param_name}}}", str(param_value))
        
        # Make HTTP request with extended timeout for agent tools
        async with httpx.AsyncClient(timeout=180.0) as client:  # 3 minutes timeout
            if service.method == "GET":
                query_params = {k: v for k, v in tool_args.items() if f"{{{k}}}" not in service.route}
                response = await client.get(url, params=query_params)
            elif service.method == "POST":
                response = await client.post(url, json=tool_args)
            else:
                response = await client.request(service.method, url, json=tool_args)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Service returned {response.status_code}: {response.text}"}