"""
Meta Chat Models

Simple models for the meta-chat system that routes requests to agents
"""

from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, Field
from enum import Enum


class ResponseType(str, Enum):
    """Type of response needed"""
    DIRECT = "direct"  # LLM can answer directly
    AGENT = "agent"    # Need to use an agent


class MetaChatRequest(BaseModel):
    """Request to the meta-chat system"""
    message: str = Field(..., description="User's message/question")
    llm_profile: str = Field(..., description="LLM profile to use")
    mode: Literal["auto", "manual"] = Field(default="auto", description="Execution mode: auto (system selects agents) or manual (user selects agents)")
    selected_agents: Optional[List[str]] = Field(default=None, description="List of agent names to use in manual mode")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional context")
    instruct: Optional[str] = Field(default=None, description="Custom presentation instructions for HTML generation")


class ChatIntent(BaseModel):
    """Analysis of user intent"""
    intent: str = Field(..., description="What the user wants")
    response_type: ResponseType = Field(..., description="How to respond")
    needs_agent: bool = Field(..., description="Whether an agent is needed")
    agent_type: Optional[str] = Field(None, description="Type of agent needed (weather, search, etc)")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters extracted from request")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in analysis")


class MetaChatResponse(BaseModel):
    """Response from the meta-chat system"""
    success: bool = Field(..., description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Direct message response")
    agent_used: Optional[str] = Field(None, description="Name of agent used if any")
    agent_created: bool = Field(default=False, description="Whether a new agent was created")
    response_data: Dict[str, Any] = Field(default_factory=dict, description="Response data from agent or LLM")
    html_response: Optional[str] = Field(None, description="HTML/CSS/JS visualization of the response")
    error: Optional[str] = Field(None, description="Error message if any")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    session_id: Optional[str] = Field(None, description="Session ID for feedback tracking")


class EnhanceRequest(BaseModel):
    """Request to enhance a query and instructions"""
    query: str = Field(..., description="Original user query to enhance")
    instructions: Optional[str] = Field(None, description="Optional presentation instructions to enhance")
    llm_profile: str = Field(..., description="LLM profile to use for enhancement")


class EnhanceResponse(BaseModel):
    """Response with enhanced query and instructions"""
    enhanced_query: str = Field(..., description="Enhanced query with data source suggestions")
    enhanced_instructions: str = Field(..., description="Enhanced presentation instructions")
    suggested_sources: List[str] = Field(default_factory=list, description="Suggested data sources")
    query_type: str = Field(..., description="Detected type of query")