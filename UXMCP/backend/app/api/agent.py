"""
Agent API endpoints for autonomous service creation

This module provides endpoints for the AI agent that can create,
test, and debug services automatically.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from app.services.agent_service import create_agent
from fastapi import FastAPI
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentCreateServiceRequest(BaseModel):
    """Request model for agent service creation"""
    name: str
    description: str
    service_type: str = "tool"
    llm_profile: str
    # External API fields (optional)
    api_documentation: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_headers: Optional[dict] = None


@router.post("/create-service")
async def create_service_with_agent(
    request: AgentCreateServiceRequest,
    app: FastAPI = Depends(lambda: router.app)
):
    """
    Create a service using the autonomous agent.
    
    The agent will:
    1. Analyze the description
    2. Generate initial code
    3. Create the service
    4. Iteratively test and fix until it works
    
    Returns a streaming response with progress updates.
    """
    try:
        # Validate service name
        if not request.name.replace("_", "").replace("-", "").isalnum():
            raise HTTPException(
                status_code=400,
                detail="Service name must be alphanumeric with underscores and hyphens only"
            )
        
        # Create the agent
        try:
            agent = await create_agent(request.llm_profile, app)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Define async generator for SSE
        async def generate():
            try:
                # Send initial event
                yield f"data: {json.dumps({'step': 'starting', 'message': 'Initializing agent...'})}\n\n"
                
                # Run the agent
                async for update in agent.create_service_from_description(
                    name=request.name,
                    description=request.description,
                    service_type=request.service_type,
                    api_documentation=request.api_documentation,
                    api_base_url=request.api_base_url,
                    api_key=request.api_key,
                    api_headers=request.api_headers
                ):
                    # Send each update as SSE
                    yield f"data: {json.dumps(update)}\n\n"
                    
                    # Small delay to not overwhelm client
                    await asyncio.sleep(0.1)
                
                # Send completion event
                yield f"data: {json.dumps({'step': 'completed', 'message': 'Agent finished'})}\n\n"
                
            except Exception as e:
                logger.error(f"Agent error during streaming: {str(e)}")
                yield f"data: {json.dumps({'step': 'error', 'message': str(e)})}\n\n"
        
        # Return SSE response
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable Nginx buffering
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create service with agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_agent_status():
    """Get the status of the agent system"""
    return {
        "status": "active",
        "version": "1.0.0",
        "capabilities": [
            "create_service",
            "test_service",
            "debug_service",
            "auto_fix_errors"
        ]
    }


class AgentAnalyzeRequest(BaseModel):
    """Request model for analyzing a service description"""
    description: str
    service_type: str = "tool"
    llm_profile: str


@router.post("/analyze")
async def analyze_service_description(
    request: AgentAnalyzeRequest,
    app: FastAPI = Depends(lambda: router.app)
):
    """
    Analyze a service description and return suggested configuration
    without actually creating the service.
    
    Useful for previewing what the agent would create.
    """
    try:
        # Create the agent
        agent = await create_agent(request.llm_profile, app)
        
        # Get context
        context = agent._build_context(request.service_type)
        
        # Generate service config
        service_config = await agent._generate_initial_service(
            name="preview_service",
            description=request.description,
            service_type=request.service_type,
            context=context
        )
        
        if not service_config:
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze service description"
            )
        
        return {
            "analysis": {
                "suggested_name": service_config.get("name"),
                "suggested_route": service_config.get("route"),
                "method": service_config.get("method"),
                "parameters": service_config.get("params", []),
                "dependencies": service_config.get("dependencies", []),
                "has_output_schema": bool(service_config.get("output_schema")),
                "documentation_preview": service_config.get("documentation", "")[:200] + "..."
            },
            "preview_code": service_config.get("code", ""),
            "service_type": request.service_type
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to analyze service description: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def get_agent_tools():
    """Get a list of tools available to the agent"""
    from app.core.agent_tools import AgentTools
    
    # Create a dummy instance to get tools list
    tools = AgentTools(None)
    return {
        "tools": tools.get_tools_list(),
        "description": "Tools available to the agent for service creation and management"
    }


@router.get("/documentation")
async def get_agent_documentation():
    """Get the documentation that the agent uses as context"""
    from app.core.service_documentation import (
        get_service_documentation,
        get_common_errors_solutions
    )
    
    return {
        "documentation": {
            "service_guide": get_service_documentation(),
            "error_solutions": get_common_errors_solutions()
        },
        "description": "Documentation used by the agent to understand UXMCP services"
    }