from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncGenerator, Dict, Any
import json
import asyncio
from app.models.agent import (
    Agent, AgentCreate, AgentUpdate, 
    AgentExecution, AgentExecutionResponse,
    AgentExecutionProgress, ExecutionStep
)
from app.services.agent_crud import agent_crud
from app.services.agent_executor import agent_executor
from app.core.agent_router import mount_agent, unmount_agent
from app.services.agent_to_tool_converter import agent_to_tool_converter
from app.services.agent_prompt_improver import agent_prompt_improver
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=Agent)
async def create_agent(agent: AgentCreate):
    """Create a new agent"""
    try:
        return await agent_crud.create(agent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create agent")


@router.get("/", response_model=List[Agent])
async def list_agents(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False
):
    """List all agents"""
    return await agent_crud.list(skip=skip, limit=limit, active_only=active_only)


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    """Get a specific agent"""
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, agent_update: AgentUpdate):
    """Update an agent"""
    try:
        agent = await agent_crud.update(agent_id, agent_update)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update agent")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, request: Request):
    """Delete an agent"""
    # Get the agent first
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # If active, unmount it first
    if agent.active:
        try:
            await unmount_agent(request.app, agent)
        except Exception as e:
            logger.error(f"Failed to unmount agent before deletion: {str(e)}")
    
    # Delete the agent
    success = await agent_crud.delete(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"message": "Agent deleted successfully"}


@router.post("/{agent_id}/activate", response_model=Agent)
async def activate_agent(agent_id: str, request: Request):
    """Activate an agent and mount its endpoint"""
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Validate dependencies
    validation = await agent_crud.validate_dependencies(agent)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Agent has invalid dependencies",
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }
        )
    
    # Activate in database
    agent = await agent_crud.activate(agent_id)
    if not agent:
        raise HTTPException(status_code=500, detail="Failed to activate agent")
    
    # Mount the agent endpoint
    try:
        await mount_agent(request.app, agent)
    except Exception as e:
        # Rollback activation
        await agent_crud.deactivate(agent_id)
        logger.error(f"Failed to mount agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to mount agent: {str(e)}")
    
    return agent


@router.post("/{agent_id}/deactivate", response_model=Agent)
async def deactivate_agent(agent_id: str, request: Request):
    """Deactivate an agent and unmount its endpoint"""
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Unmount the agent endpoint
    try:
        await unmount_agent(request.app, agent)
    except Exception as e:
        logger.error(f"Failed to unmount agent: {str(e)}")
        # Continue with deactivation even if unmounting fails
    
    # Deactivate in database
    agent = await agent_crud.deactivate(agent_id)
    if not agent:
        raise HTTPException(status_code=500, detail="Failed to deactivate agent")
    
    return agent


@router.post("/{agent_id}/execute", response_model=AgentExecutionResponse)
async def execute_agent(agent_id: str, execution_request: AgentExecution):
    """Execute an agent directly (for testing)"""
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.active:
        raise HTTPException(status_code=400, detail="Agent is not active")
    
    # Execute the agent
    try:
        result = await agent_executor.execute(agent, execution_request)
        return result
    except Exception as e:
        logger.error(f"Failed to execute agent: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to execute agent: {str(e)}")


@router.get("/{agent_id}/validate")
async def validate_agent(agent_id: str):
    """Validate agent dependencies"""
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    validation = await agent_crud.validate_dependencies(agent)
    return validation


@router.post("/{agent_id}/execute-stream")
async def execute_agent_stream(agent_id: str, execution_request: AgentExecution):
    """Execute an agent with SSE streaming progress"""
    agent = await agent_crud.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.active:
        raise HTTPException(status_code=400, detail="Agent is not active")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE event stream"""
        try:
            # Send initial progress
            progress = AgentExecutionProgress(
                step=ExecutionStep.STARTING,
                message=f"Starting execution of agent '{agent.name}'",
                progress=0
            )
            yield f"data: {progress.json()}\n\n"
            
            # Execute agent with progress updates
            async for update in agent_executor.execute_with_progress(agent, execution_request):
                # Send progress update
                yield f"data: {update.json()}\n\n"
                
                # Send heartbeat every few updates to keep connection alive
                if update.step == ExecutionStep.HEARTBEAT:
                    yield ": heartbeat\n\n"
            
            # Ensure we send a complete event
            if update.step != ExecutionStep.COMPLETE and update.step != ExecutionStep.ERROR:
                final_progress = AgentExecutionProgress(
                    step=ExecutionStep.COMPLETE,
                    message="Execution completed",
                    progress=100
                )
                yield f"data: {final_progress.json()}\n\n"
                
        except Exception as e:
            logger.error(f"Error in SSE stream: {str(e)}")
            error_progress = AgentExecutionProgress(
                step=ExecutionStep.ERROR,
                message="Execution failed",
                progress=0,
                error_detail=str(e)
            )
            yield f"data: {error_progress.json()}\n\n"
        
        finally:
            # Send stream close event
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable Nginx buffering
        }
    )


@router.post("/{agent_id}/convert-to-tool")
async def convert_agent_to_tool(agent_id: str):
    """Convert an agent into a callable MCP tool service"""
    result = await agent_to_tool_converter.convert_agent_to_tool(agent_id)
    
    if result["success"]:
        return {
            "success": True,
            "service_id": result["service_id"],
            "service_name": result["service_name"],
            "message": result["message"],
            "next_step": "Activate the service at POST /services/{service_id}/activate"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=result["error"]
        )


@router.get("/{agent_id}/improve-prompt")
async def improve_agent_prompt(agent_id: str):
    """
    Generate an improved system prompt for the agent based on its tools and configuration.
    Streams progress updates via SSE.
    """
    async def generate_stream():
        try:
            async for update in agent_prompt_improver.improve_system_prompt(agent_id, stream=True):
                yield f"data: {json.dumps(update)}\n\n"
                
                # Send heartbeat for long-running operations
                if update.get("step") == "generating":
                    yield ": heartbeat\n\n"
                    
        except Exception as e:
            logger.error(f"Error improving prompt: {str(e)}")
            error_update = {
                "step": "error",
                "message": f"Failed to improve prompt: {str(e)}",
                "error": True
            }
            yield f"data: {json.dumps(error_update)}\n\n"
        
        finally:
            # Send stream close event
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable Nginx buffering
        }
    )


@router.get("/{agent_id}/improve-from-feedback")
async def improve_agent_prompt_from_feedback(
    agent_id: str,
    feedback: str = "",
    last_response: str = "",
    context: Optional[str] = None
):
    """
    Improve agent's system prompt based on negative user feedback.
    Focuses on general improvements, not case-specific adjustments.
    Streams progress updates via SSE.
    """
    # Parse context if provided
    conversation_context = None
    if context:
        try:
            conversation_context = json.loads(context)
        except:
            conversation_context = None
    
    async def generate_stream():
        try:
            async for update in agent_prompt_improver.improve_prompt_from_feedback(
                agent_id=agent_id,
                user_feedback=feedback,
                last_response=last_response,
                conversation_context=conversation_context,
                stream=True
            ):
                yield f"data: {json.dumps(update)}\n\n"
                
                # Send heartbeat for long-running operations
                if update.get("step") in ["generating", "analyzing_patterns"]:
                    yield ": heartbeat\n\n"
                    
        except Exception as e:
            logger.error(f"Error improving prompt from feedback: {str(e)}")
            error_update = {
                "step": "error",
                "message": f"Failed to improve prompt: {str(e)}",
                "error": True
            }
            yield f"data: {json.dumps(error_update)}\n\n"
        
        finally:
            # Send stream close event
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable Nginx buffering
        }
    )


@router.post("/{agent_id}/debug-prompt")
async def debug_agent_prompt(agent_id: str, execution_request: AgentExecution):
    """Debug: Get the complete prompt that would be sent to the agent"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Create a debug version of the agent executor to build messages
        from app.services.agent_executor import AgentExecutor
        from app.services.settings_crud import settings_crud
        from app.services.conversation_crud import conversation_crud
        from app.services.conversation_compactor import conversation_compactor
        
        executor = AgentExecutor()
        
        # Load memory context if enabled
        memory_context = None
        if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
            memory_context = await executor._load_memory_context(
                agent=agent,
                query=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                logger=None  # Skip logging for debug
            )
        
        # Load conversation history if conversation_id is provided
        loaded_history = []
        if execution_request.conversation_id:
            loaded_conversation = await conversation_crud.get(execution_request.conversation_id)
            if loaded_conversation and loaded_conversation.messages:
                for msg in loaded_conversation.messages:
                    loaded_history.append({
                        "role": msg.role,
                        "content": msg.content
                    })
        
        # Use loaded history if no history was provided
        if loaded_history and not execution_request.conversation_history:
            execution_request.conversation_history = loaded_history
        
        # Build initial messages using MessageBuilder
        messages = executor.message_builder.build_messages(
            agent=agent,
            execution_request=execution_request,
            memory_context=memory_context,
            tools=None  # We don't need tools for debugging the prompt
        )
        
        # Apply conversation compaction if enabled (same logic as execute)
        messages_for_agent = messages
        compaction_applied = False
        global_settings = await settings_crud.get_or_create()
        
        if global_settings.compaction_settings.enabled and execution_request.conversation_history:
            full_messages = []
            if execution_request.conversation_history:
                full_messages.extend(execution_request.conversation_history)
            if messages and messages[-1]["role"] == "user":
                full_messages.append(messages[-1])
            
            compacted_messages, was_compacted = await conversation_compactor.compact_conversation(
                messages=full_messages,
                user_context=global_settings.user_context,
                settings=global_settings,
                current_user_message=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input)
            )
            
            if was_compacted:
                agent_system_messages = [msg for msg in messages if msg["role"] == "system" and "User Context:" not in msg["content"] and "Previous Conversation Summary:" not in msg["content"]]
                messages_for_agent = agent_system_messages + compacted_messages
                compaction_applied = True
            elif global_settings.user_context:
                user_context_msg = {
                    "role": "system", 
                    "content": f"User Context: {global_settings.user_context}"
                }
                messages_for_agent = messages[:-1] + [user_context_msg] + [messages[-1]]
        
        # Return debug information
        return {
            "success": True,
            "agent_name": agent.name,
            "agent_id": agent_id,
            "input": execution_request.input,
            "memory_enabled": getattr(agent, 'memory_enabled', False),
            "memory_context": memory_context,
            "conversation_history_count": len(execution_request.conversation_history) if execution_request.conversation_history else 0,
            "compaction_applied": compaction_applied,
            "global_settings": {
                "compaction_enabled": global_settings.compaction_settings.enabled,
                "user_context": global_settings.user_context
            },
            "final_messages": messages_for_agent,
            "message_breakdown": {
                "system_messages": len([m for m in messages_for_agent if m["role"] == "system"]),
                "user_messages": len([m for m in messages_for_agent if m["role"] == "user"]), 
                "assistant_messages": len([m for m in messages_for_agent if m["role"] == "assistant"]),
                "total": len(messages_for_agent)
            }
        }
        
    except Exception as e:
        logger.error(f"Debug prompt failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")


# MCP Connection endpoints for agents
@router.get("/{agent_id}/mcp-tools")
async def get_agent_mcp_tools(agent_id: str):
    """Get all MCP tools available to an agent (local + external)"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Import here to avoid circular imports
        from app.core.mcp_agent_tools import MCPAgentTools
        from app.core.agent_tools import AgentTools
        from fastapi import FastAPI
        
        # Create tools instance (we'll need the app instance)
        app = FastAPI()  # This is a placeholder - ideally get from dependency
        agent_tools = AgentTools(app)
        mcp_tools = MCPAgentTools(agent_tools)
        
        # Get all tools for this agent
        all_tools = await mcp_tools.get_all_tools_for_agent(agent.mcp_connections)
        
        # Separate local and external tools
        local_tools = [t for t in all_tools if t.get("source") == "local"]
        external_tools = [t for t in all_tools if t.get("source") == "mcp_external"]
        
        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "local_tools": local_tools,
            "external_tools": external_tools,
            "total_tools": len(all_tools),
            "mcp_connections": agent.mcp_connections,
            "mcp_config": agent.mcp_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent MCP tools: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get agent MCP tools")


@router.post("/{agent_id}/mcp-connections")
async def assign_mcp_connection(agent_id: str, connection_data: Dict[str, Any]):
    """Assign an MCP connection to an agent"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        connection_id = connection_data.get("connection_id")
        if not connection_id:
            raise HTTPException(status_code=400, detail="connection_id is required")
        
        # Verify connection exists
        from app.services.mcp_connection_service import mcp_connection_service
        connection = await mcp_connection_service.get_connection(connection_id)
        if not connection:
            raise HTTPException(status_code=404, detail="MCP connection not found")
        
        # Add connection to agent if not already present
        if connection_id not in agent.mcp_connections:
            updated_connections = agent.mcp_connections + [connection_id]
            
            # Update agent
            update_data = AgentUpdate(mcp_connections=updated_connections)
            updated_agent = await agent_crud.update(agent_id, update_data)
            
            if not updated_agent:
                raise HTTPException(status_code=500, detail="Failed to update agent")
            
            return {
                "message": f"MCP connection '{connection.name}' assigned to agent '{agent.name}'",
                "connection_id": connection_id,
                "connection_name": connection.name,
                "agent_mcp_connections": updated_agent.mcp_connections
            }
        else:
            return {
                "message": f"MCP connection '{connection.name}' already assigned to agent '{agent.name}'",
                "connection_id": connection_id,
                "connection_name": connection.name,
                "agent_mcp_connections": agent.mcp_connections
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign MCP connection")


@router.delete("/{agent_id}/mcp-connections/{connection_id}")
async def unassign_mcp_connection(agent_id: str, connection_id: str):
    """Remove an MCP connection from an agent"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Remove connection from agent if present
        if connection_id in agent.mcp_connections:
            updated_connections = [conn_id for conn_id in agent.mcp_connections if conn_id != connection_id]
            
            # Update agent
            update_data = AgentUpdate(mcp_connections=updated_connections)
            updated_agent = await agent_crud.update(agent_id, update_data)
            
            if not updated_agent:
                raise HTTPException(status_code=500, detail="Failed to update agent")
            
            return {
                "message": f"MCP connection unassigned from agent '{agent.name}'",
                "connection_id": connection_id,
                "agent_mcp_connections": updated_agent.mcp_connections
            }
        else:
            return {
                "message": f"MCP connection not assigned to agent '{agent.name}'",
                "connection_id": connection_id,
                "agent_mcp_connections": agent.mcp_connections
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unassign MCP connection: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unassign MCP connection")


@router.put("/{agent_id}/mcp-config")
async def update_agent_mcp_config(agent_id: str, mcp_config: Dict[str, Any]):
    """Update MCP configuration for an agent"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Import the config model
        from app.models.mcp_connection import MCPAgentConfig
        
        # Validate config
        try:
            validated_config = MCPAgentConfig(**mcp_config)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid MCP config: {str(e)}")
        
        # Update agent
        update_data = AgentUpdate(mcp_config=validated_config)
        updated_agent = await agent_crud.update(agent_id, update_data)
        
        if not updated_agent:
            raise HTTPException(status_code=500, detail="Failed to update agent")
        
        return {
            "message": f"MCP configuration updated for agent '{agent.name}'",
            "mcp_config": updated_agent.mcp_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update MCP config")


@router.get("/{agent_id}/mcp-connections")
async def get_agent_mcp_connections(agent_id: str):
    """Get detailed information about agent's MCP connections"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Import here to avoid circular imports
        from app.core.mcp_agent_tools import MCPAgentTools
        from app.core.agent_tools import AgentTools
        from fastapi import FastAPI
        
        # Create tools instance
        app = FastAPI()  # Placeholder
        agent_tools = AgentTools(app)
        mcp_tools = MCPAgentTools(agent_tools)
        
        # Get connection details
        connections_info = await mcp_tools.list_connections_for_agent(agent.mcp_connections)
        
        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "mcp_connections": connections_info,
            "mcp_config": agent.mcp_config,
            "connections_count": len(connections_info)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent MCP connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get agent MCP connections")


@router.post("/{agent_id}/mcp-tools/{tool_name}/execute")
async def execute_agent_mcp_tool(agent_id: str, tool_name: str, tool_params: Dict[str, Any]):
    """Execute an MCP tool for an agent"""
    try:
        agent = await agent_crud.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Import here to avoid circular imports
        from app.core.mcp_agent_tools import MCPAgentTools
        from app.core.agent_tools import AgentTools
        from fastapi import FastAPI
        
        # Create tools instance
        app = FastAPI()  # Placeholder
        agent_tools = AgentTools(app)
        mcp_tools = MCPAgentTools(agent_tools)
        
        # Execute the tool
        result = await mcp_tools.execute_tool_for_agent(
            agent.mcp_connections,
            tool_name,
            tool_params.get("parameters", {}),
            agent.mcp_config.dict() if agent.mcp_config else {}
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute MCP tool: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to execute MCP tool")