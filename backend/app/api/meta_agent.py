"""
Meta Agent API Endpoints

This module provides API endpoints for the Meta Agent system,
including SSE support for real-time progress updates.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import json
import logging

from app.models.meta_agent import (
    MetaAgentRequest, AgentRequirement, MetaAgentResponse
)
from app.services.meta_agent_service import create_meta_agent
from app.services.llm_crud import llm_crud
from fastapi import FastAPI

logger = logging.getLogger(__name__)

router = APIRouter()


async def event_generator(meta_agent, requirement, options):
    """Generate SSE events from meta agent progress"""
    try:
        async for progress in meta_agent.create_agent_from_requirement(
            requirement=requirement,
            auto_activate=options.get("auto_activate", True),
            create_missing_tools=options.get("create_missing_tools", True),
            test_agent=options.get("test_agent", True),
            max_tools_to_create=options.get("max_tools_to_create", 5)
        ):
            # Convert progress to SSE format
            event_data = json.dumps(progress.dict())
            yield f"data: {event_data}\n\n"
            
            # If complete or error, send final event
            if progress.step in ["complete", "error"]:
                yield f"data: {json.dumps({'step': 'completed'})}\n\n"
                
    except Exception as e:
        logger.error(f"Error in event generator: {str(e)}")
        error_event = json.dumps({
            "step": "error",
            "message": "Internal error occurred",
            "error": str(e)
        })
        yield f"data: {error_event}\n\n"


@router.post("/create")
async def create_agent_sse(
    request: MetaAgentRequest,
    app: FastAPI = Depends(lambda: router.app)
):
    """
    Create an agent using the Meta Agent system with SSE progress updates
    
    This endpoint streams progress updates as the agent is being created,
    including tool creation, configuration, and testing phases.
    """
    try:
        # Validate LLM profile
        llm_profile = await llm_crud.get_by_name(request.requirement.llm_profile)
        if not llm_profile or not llm_profile.active:
            raise HTTPException(
                status_code=400,
                detail=f"LLM profile '{request.requirement.llm_profile}' not found or inactive"
            )
        
        # Create meta agent
        meta_agent = await create_meta_agent(request.requirement.llm_profile, app)
        
        # Create SSE response
        return StreamingResponse(
            event_generator(
                meta_agent,
                request.requirement,
                {
                    "auto_activate": request.auto_activate,
                    "create_missing_tools": request.create_missing_tools,
                    "test_agent": request.test_agent,
                    "max_tools_to_create": request.max_tools_to_create
                }
            ),
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
        logger.error(f"Failed to create agent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_requirements(
    requirement: AgentRequirement,
    app: FastAPI = Depends(lambda: router.app)
):
    """
    Analyze agent requirements without creating anything
    
    This endpoint is useful for previewing what the meta agent would do
    before actually creating the agent and tools.
    """
    try:
        # Validate LLM profile
        llm_profile = await llm_crud.get_by_name(requirement.llm_profile)
        if not llm_profile or not llm_profile.active:
            raise HTTPException(
                status_code=400,
                detail=f"LLM profile '{requirement.llm_profile}' not found or inactive"
            )
        
        # Create meta agent
        meta_agent = await create_meta_agent(requirement.llm_profile, app)
        
        # Analyze requirements
        import uuid
        analysis = await meta_agent._analyze_requirements(
            requirement,
            str(uuid.uuid4())
        )
        
        # Match with existing services
        matched_tools, unmatched_tools = await meta_agent.tool_analyzer.match_existing_services(
            analysis.required_tools
        )
        
        return {
            "analysis": analysis.dict(),
            "matched_tools": [t.dict() for t in matched_tools],
            "unmatched_tools": [t.dict() for t in unmatched_tools],
            "summary": {
                "understood_purpose": analysis.understood_purpose,
                "complexity": analysis.complexity_assessment,
                "tools_available": len(matched_tools),
                "tools_to_create": len(unmatched_tools),
                "estimated_time": "2-5 minutes" if len(unmatched_tools) > 0 else "30 seconds"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze requirements: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-tools")
async def suggest_tools_for_purpose(
    request: Dict[str, Any],
    app: FastAPI = Depends(lambda: router.app)
):
    """
    Suggest tools for a given purpose without creating an agent
    
    Request body:
    {
        "purpose": "What you want to accomplish",
        "domain": "Optional domain/category",
        "llm_profile": "LLM profile to use"
    }
    """
    try:
        purpose = request.get("purpose")
        domain = request.get("domain", "general")
        llm_profile_name = request.get("llm_profile")
        
        if not purpose or not llm_profile_name:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: purpose, llm_profile"
            )
        
        # Validate LLM profile
        llm_profile = await llm_crud.get_by_name(llm_profile_name)
        if not llm_profile or not llm_profile.active:
            raise HTTPException(
                status_code=400,
                detail=f"LLM profile '{llm_profile_name}' not found or inactive"
            )
        
        # Create tool analyzer
        from app.core.tool_analyzer import ToolAnalyzer
        analyzer = ToolAnalyzer(llm_profile)
        
        # Analyze required tools
        required_tools = await analyzer.analyze_required_tools(
            purpose,
            [purpose],  # Use purpose as a use case
            domain
        )
        
        # Match with existing services
        matched_tools, unmatched_tools = await analyzer.match_existing_services(
            required_tools
        )
        
        return {
            "purpose": purpose,
            "domain": domain,
            "suggested_tools": {
                "available": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "service_id": t.existing_service_id
                    }
                    for t in matched_tools
                ],
                "need_to_create": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters
                    }
                    for t in unmatched_tools
                ]
            },
            "total_tools": len(required_tools),
            "ready_to_use": len(matched_tools),
            "require_creation": len(unmatched_tools)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to suggest tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def get_agent_templates():
    """
    Get predefined agent templates for common use cases
    
    These templates can be used as starting points for creating agents.
    """
    templates = [
        {
            "name": "Research Assistant",
            "description": "An intelligent research assistant that can search the web, analyze information, and provide summaries",
            "domain": "research",
            "complexity": "moderate",
            "suggested_tools": ["web_search", "content_summarizer", "fact_checker"],
            "example_request": "Create a research assistant that can help me find and analyze information on any topic"
        },
        {
            "name": "Travel Planner",
            "description": "A travel planning agent that helps with destinations, flights, hotels, and itineraries",
            "domain": "travel",
            "complexity": "complex",
            "suggested_tools": ["weather_service", "flight_search", "hotel_finder", "attraction_recommender"],
            "example_request": "Create a travel planning assistant that can help me plan complete trips including flights, hotels, and activities"
        },
        {
            "name": "Code Helper",
            "description": "A programming assistant that can help with code generation, debugging, and explanations",
            "domain": "programming",
            "complexity": "moderate",
            "suggested_tools": ["code_analyzer", "documentation_search", "error_explainer"],
            "example_request": "Create a coding assistant that can help me write, debug, and understand code"
        },
        {
            "name": "Customer Support",
            "description": "A customer service agent that can handle inquiries, complaints, and provide assistance",
            "domain": "customer_service",
            "complexity": "moderate",
            "suggested_tools": ["knowledge_base_search", "ticket_manager", "sentiment_analyzer"],
            "example_request": "Create a customer support agent that can handle customer inquiries professionally and efficiently"
        },
        {
            "name": "Data Analyst",
            "description": "An agent that can analyze data, create visualizations, and provide insights",
            "domain": "data_analysis",
            "complexity": "complex",
            "suggested_tools": ["data_processor", "chart_generator", "statistical_analyzer", "report_writer"],
            "example_request": "Create a data analysis assistant that can help me understand and visualize data patterns"
        }
    ]
    
    return {
        "templates": templates,
        "usage": "Use these templates as inspiration for your agent requirements"
    }