from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from typing import List, Optional, AsyncGenerator
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