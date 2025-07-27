"""
Agent to Tool Converter Service

Converts agents into MCP tools that can be used by other agents,
avoiding HTTP timeouts by using direct async execution.
"""

import logging
from typing import Dict, Any, List, Optional
from app.models.service import ServiceCreate, ServiceParam
from app.models.agent import Agent
from app.services.service_crud import service_crud
from app.services.agent_crud import agent_crud

logger = logging.getLogger(__name__)


class AgentToToolConverter:
    """Service to convert agents into callable MCP tools"""
    
    async def convert_agent_to_tool(self, agent_id: str) -> Dict[str, Any]:
        """
        Convert an agent into a MCP tool service
        
        Args:
            agent_id: ID of the agent to convert
            
        Returns:
            Dict with success status and service details
        """
        try:
            # Get the agent
            agent = await agent_crud.get(agent_id)
            if not agent:
                return {
                    "success": False,
                    "error": f"Agent with ID {agent_id} not found"
                }
            
            # Check if agent is active
            if not agent.active:
                return {
                    "success": False,
                    "error": f"Agent '{agent.name}' must be active to convert to tool"
                }
            
            # Check if service already exists
            existing_services = await service_crud.list()
            service_name = f"{agent.name}_as_tool"
            
            for service in existing_services:
                if service.name == service_name:
                    return {
                        "success": False,
                        "error": f"Service '{service_name}' already exists",
                        "service_id": service.id
                    }
            
            # Create service parameters based on agent input schema
            params = []
            
            if agent.input_schema == "text":
                # Simple text input
                params.append(ServiceParam(
                    name="input",
                    type="string",
                    required=True,
                    description=f"Input for {agent.name} agent"
                ))
            else:
                # Structured input - add parameters based on schema
                if isinstance(agent.input_schema, dict) and "properties" in agent.input_schema:
                    for prop_name, prop_def in agent.input_schema["properties"].items():
                        param_type = prop_def.get("type", "string")
                        if param_type == "integer":
                            param_type = "int"
                        elif param_type == "number":
                            param_type = "float"
                        elif param_type == "boolean":
                            param_type = "bool"
                        elif param_type == "array":
                            param_type = "list"
                        elif param_type == "object":
                            param_type = "dict"
                            
                        params.append(ServiceParam(
                            name=prop_name,
                            type=param_type,
                            required=prop_name in agent.input_schema.get("required", []),
                            description=prop_def.get("description", f"Parameter {prop_name}")
                        ))
                else:
                    # Fallback to generic dict input
                    params.append(ServiceParam(
                        name="input",
                        type="dict",
                        required=True,
                        description=f"Structured input for {agent.name} agent"
                    ))
            
            # Add optional parameters for advanced usage
            params.extend([
                ServiceParam(
                    name="conversation_history",
                    type="array",
                    required=False,
                    description="Optional conversation history"
                ),
                ServiceParam(
                    name="execution_options",
                    type="object",
                    required=False,
                    description="Optional execution options"
                )
            ])
            
            # Generate the handler code that directly calls the agent executor
            handler_code = self._generate_handler_code(agent_id, agent.name)
            
            # Create the service
            service_data = ServiceCreate(
                name=service_name,
                service_type="tool",
                route=f"/api/tools/{service_name}",
                method="POST",
                code=handler_code,
                params=params,
                dependencies=[],  # No external dependencies needed
                output_schema=agent.output_schema if agent.output_schema != "text" else None,
                description=f"Tool interface for {agent.name} agent: {agent.description or 'No description'}",
                documentation=self._generate_documentation(agent),
                llm_profile=agent.llm_profile,
                active=False
            )
            
            # Create the service
            service = await service_crud.create(service_data)
            
            logger.info(f"Successfully created tool service '{service_name}' for agent '{agent.name}'")
            
            return {
                "success": True,
                "service_id": service.id,
                "service_name": service_name,
                "message": f"Agent '{agent.name}' converted to tool service '{service_name}'",
                "activate_command": f"Activate the service to make it available as a tool"
            }
            
        except Exception as e:
            logger.error(f"Failed to convert agent to tool: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_handler_code(self, agent_id: str, agent_name: str) -> str:
        """Generate the handler code for the tool service"""
        return f'''async def handler(**params):
    """
    Tool interface for {agent_name} agent
    This handler directly executes the agent without HTTP calls to avoid timeouts.
    """
    # Import necessary modules inside the handler
    import asyncio
    from bson import ObjectId
    
    # Import from the app context
    import sys
    sys.path.append('/app')
    
    from app.services.agent_crud import agent_crud
    from app.models.agent import AgentExecution
    from app.services.agent_executor import agent_executor
    
    # Agent ID injected during service creation
    agent_id = "{agent_id}"
    
    try:
        # Get the agent
        agent = await agent_crud.get(agent_id)
        if not agent:
            return {{"success": False, "error": f"Agent with ID {{agent_id}} not found"}}
        
        # Check if agent is active
        if not agent.active:
            return {{"success": False, "error": f"Agent '{{agent.name}}' is not active"}}
        
        # Create execution request based on agent's input schema
        if agent.input_schema == "text":
            # For text input agents, get the 'input' parameter
            input_data = params.get("input", "")
        else:
            # For structured input, pass all params except special ones
            special_params = {{"conversation_history", "execution_options"}}
            input_data = {{k: v for k, v in params.items() if k not in special_params}}
        
        execution_request = AgentExecution(
            input=input_data,
            conversation_history=params.get("conversation_history"),
            execution_options=params.get("execution_options", {{}})
        )
        
        # Execute the agent directly (no HTTP call)
        result = await agent_executor.execute(agent, execution_request)
        
        # Return the result in a format suitable for tool usage
        if result.success:
            return {{
                "success": True,
                "output": result.output,
                "execution_id": result.execution_id,
                "tool_calls_made": len(result.tool_calls) if result.tool_calls else 0
            }}
        else:
            return {{
                "success": False,
                "error": result.error,
                "execution_id": result.execution_id
            }}
            
    except Exception as e:
        import traceback
        return {{
            "success": False,
            "error": f"Agent execution failed: {{str(e)}}",
            "traceback": traceback.format_exc()
        }}
'''
    
    def _generate_documentation(self, agent: Agent) -> str:
        """Generate documentation for the tool service"""
        doc = f"""# {agent.name} as Tool

This tool provides access to the {agent.name} agent.

## Description
{agent.description or 'No description provided'}

## Agent Configuration
- **LLM Profile**: {agent.llm_profile}
- **Max Iterations**: {agent.max_iterations}
- **Input Schema**: {'Plain text' if agent.input_schema == 'text' else 'Structured JSON'}
- **Output Schema**: {'Plain text' if agent.output_schema == 'text' else 'Structured JSON'}
"""

        if agent.objectives:
            doc += "\n## Objectives\n"
            for obj in agent.objectives:
                doc += f"- {obj}\n"
        
        if agent.mcp_services:
            doc += "\n## Available Tools\n"
            for service in agent.mcp_services:
                doc += f"- {service}\n"
        
        if agent.backstory:
            doc += f"\n## Backstory\n{agent.backstory}\n"
        
        doc += """
## Usage
Call this tool with the appropriate input based on the agent's input schema.
The agent will process your request using its configured LLM and tools.

## Response
The tool returns a JSON object with:
- `success`: Boolean indicating if execution was successful
- `output`: The agent's response (format depends on output schema)
- `error`: Error message if execution failed
- `execution_id`: ID for tracking this execution in logs
"""
        
        return doc


# Singleton instance
agent_to_tool_converter = AgentToToolConverter()