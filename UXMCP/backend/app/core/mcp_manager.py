from fastmcp import FastMCP
from typing import Dict, Any, Optional
from app.models.service import Service
from app.models.llm import LLMProfile
from app.services.llm_crud import llm_crud
from app.core.dynamic_tool_builder import create_dynamic_tool_function
from app.core.dynamic_prompt_builder import create_dynamic_prompt_function
import logging
import json
import importlib
import sys
import asyncio
import inspect

logger = logging.getLogger(__name__)


class MCPManager:
    def __init__(self):
        self.mcp = FastMCP("UXMCP Dynamic Services")
        self.tools = {}
        self.resources = {}
        self.prompts = {}
        
    async def register_service(self, service: Service):
        """Register a service as MCP tool, resource, or prompt"""
        try:
            if service.service_type == "tool":
                await self._register_tool(service)
            elif service.service_type == "resource":
                await self._register_resource(service)
            elif service.service_type == "prompt":
                await self._register_prompt(service)
            else:
                raise ValueError(f"Unknown service type: {service.service_type}")
                
        except Exception as e:
            logger.error(f"Failed to register MCP service {service.name}: {str(e)}")
            raise
    
    async def _register_tool(self, service: Service):
        """Register a service as an MCP tool"""
        
        # Create a dynamic function with proper type annotations
        dynamic_func = create_dynamic_tool_function(service)
        
        # Create the actual handler that will execute the service
        async def tool_implementation(**kwargs):
            return await self._execute_service(service, kwargs)
        
        # Copy the signature and metadata from dynamic function
        tool_implementation.__signature__ = dynamic_func.__signature__
        tool_implementation.__annotations__ = dynamic_func.__annotations__
        tool_implementation.__name__ = dynamic_func.__name__
        tool_implementation.__doc__ = dynamic_func.__doc__
        
        # Register with FastMCP using the properly typed function
        self.mcp.tool(
            name=service.name,
            description=service.description or f"Dynamic tool: {service.name}"
        )(tool_implementation)
        
        self.tools[service.name] = tool_implementation
        logger.info(f"Registered MCP tool: {service.name} with typed parameters")
    
    async def _register_resource(self, service: Service):
        """Register a service as an MCP resource"""
        @self.mcp.resource(
            name=service.name,
            uri=f"resource://{service.name}",
            description=service.description or f"Dynamic resource: {service.name}",
            mime_type=service.mime_type or "text/plain"
        )
        async def resource_handler():
            # For resources, we call the service without parameters
            result = await self._execute_service(service, {})
            if isinstance(result, dict) and "content" in result:
                return result["content"]
            return str(result)
        
        self.resources[service.name] = resource_handler
        logger.info(f"Registered MCP resource: {service.name}")
    
    async def _register_prompt(self, service: Service):
        """Register a service as an MCP prompt"""
        
        # Create a dynamic function with proper parameters
        dynamic_func = create_dynamic_prompt_function(service)
        
        # Create the actual handler that will execute the service
        async def prompt_implementation(**kwargs):
            # For prompts, we use the template and fill it with provided arguments
            template = service.prompt_template or "Default prompt template"
            
            # Execute the service code to potentially modify the template
            service_result = await self._execute_service(service, kwargs)
            
            if isinstance(service_result, dict) and "template" in service_result:
                template = service_result["template"]
            elif isinstance(service_result, str):
                template = service_result
            
            # Fill template with arguments
            try:
                filled_template = template.format(**kwargs)
            except KeyError as e:
                filled_template = template  # Use template as-is if formatting fails
            
            return [
                {
                    "type": "text",
                    "text": filled_template
                }
            ]
        
        # Copy the signature and metadata from dynamic function
        prompt_implementation.__signature__ = dynamic_func.__signature__
        prompt_implementation.__annotations__ = dynamic_func.__annotations__
        prompt_implementation.__name__ = dynamic_func.__name__
        prompt_implementation.__doc__ = dynamic_func.__doc__
        
        # Register with FastMCP using the properly typed function
        self.mcp.prompt(
            name=service.name,
            description=service.description or f"Dynamic prompt: {service.name}"
        )(prompt_implementation)
        
        self.prompts[service.name] = prompt_implementation
        logger.info(f"Registered MCP prompt: {service.name}")
    
    async def unregister_service(self, service_name: str):
        """Unregister an MCP service (tool, resource, or prompt)"""
        try:
            if service_name in self.tools:
                # Remove from FastMCP (tools, resources, prompts)
                for attr_name in ['_tools', '_resources', '_prompts']:
                    if hasattr(self.mcp, attr_name):
                        attr_dict = getattr(self.mcp, attr_name)
                        if service_name in attr_dict:
                            del attr_dict[service_name]
                
                # Remove from appropriate collection
                if service_name in self.tools:
                    del self.tools[service_name]
                elif service_name in self.resources:
                    del self.resources[service_name]
                elif service_name in self.prompts:
                    del self.prompts[service_name]
                logger.info(f"Unregistered MCP service: {service_name}")
                
        except Exception as e:
            logger.error(f"Failed to unregister MCP service {service_name}: {str(e)}")
            raise
    
    async def _execute_service(self, service: Service, params: Dict[str, Any]) -> Any:
        """Execute a service with given parameters"""
        try:
            # Create execution environment
            local_vars = {"params": params}
            global_vars = {
                "__builtins__": __builtins__,
                "json": json,
            }
            
            # Import dependencies
            for dep in service.dependencies:
                try:
                    if dep in sys.modules:
                        module = sys.modules[dep]
                    else:
                        module = importlib.import_module(dep)
                    global_vars[dep] = module
                except ImportError as e:
                    logger.error(f"Failed to import dependency {dep}: {e}")
                    return {"error": f"Missing dependency: {dep}"}
            
            # If service uses LLM, inject the client
            if service.llm_profile:
                llm_profile = await llm_crud.get_by_name(service.llm_profile)
                if llm_profile and llm_profile.active:
                    # Here you would inject the actual LLM client
                    # For now, we'll add a placeholder
                    local_vars["llm"] = {"profile": llm_profile.dict()}
            
            # Execute the service code
            exec(service.code, global_vars, local_vars)
            
            # The service code should define a handler function
            if "handler" not in local_vars:
                return {"error": "Service code must define a 'handler' function"}
            
            handler = local_vars["handler"]
            
            # Call the handler
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**params)
            else:
                result = handler(**params)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing MCP service {service.name}: {str(e)}")
            return {"error": f"Service execution error: {str(e)}"}
    
    def get_mcp_server(self):
        """Get the FastMCP server instance"""
        return self.mcp


# Global instance
mcp_manager = MCPManager()