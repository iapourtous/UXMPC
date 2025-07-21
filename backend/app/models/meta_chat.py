"""
Meta Chat Models

Simple models for the meta-chat system that routes requests to agents
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class ResponseType(str, Enum):
    """Type of response needed"""
    DIRECT = "direct"  # LLM can answer directly
    AGENT = "agent"    # Need to use an agent


class QueryType(str, Enum):
    """Type of user query"""
    INFORMATION = "information"      # Weather, news, Wikipedia search, etc.
    CREATION = "creation"           # Games, tools, calculators, etc.
    VISUALIZATION = "visualization" # Charts, dashboards, maps, etc.
    ANALYSIS = "analysis"          # Data analysis, comparisons, etc.
    GENERAL = "general"           # Unclear or mixed type


class QuestionType(str, Enum):
    """Type of clarification question"""
    CHOICE = "choice"       # Multiple choice
    TEXT = "text"          # Free text input
    NUMBER = "number"      # Numeric input
    BOOLEAN = "boolean"    # Yes/No toggle
    MULTISELECT = "multiselect"  # Multiple selections allowed


class MetaChatRequest(BaseModel):
    """Request to the meta-chat system"""
    message: str = Field(..., description="User's message/question")
    llm_profile: str = Field(..., description="LLM profile to use")
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


class ClarificationQuestion(BaseModel):
    """A single clarification question"""
    id: str = Field(..., description="Unique question ID")
    question: str = Field(..., description="The question to ask")
    type: QuestionType = Field(..., description="Type of input expected")
    options: Optional[List[str]] = Field(None, description="Options for choice/multiselect questions")
    default: Optional[Any] = Field(None, description="Default value if user skips")
    required: bool = Field(default=False, description="Whether the question is required")
    context: Optional[str] = Field(None, description="Additional context or help text")


class ClarificationQuestionnaire(BaseModel):
    """Generated questionnaire for a query"""
    session_id: str = Field(..., description="Session ID for tracking")
    query_type: QueryType = Field(..., description="Detected type of query")
    questions: List[ClarificationQuestion] = Field(..., description="List of clarification questions")
    expires_at: Optional[str] = Field(None, description="When this questionnaire expires")


class ClarificationAnswers(BaseModel):
    """User's answers to clarification questions"""
    session_id: str = Field(..., description="Session ID to match questionnaire")
    answers: Dict[str, Any] = Field(..., description="Question ID to answer mapping")


class MetaChatSession(BaseModel):
    """Complete session data for meta-chat"""
    session_id: str = Field(..., description="Unique session ID")
    original_query: str = Field(..., description="Original user query")
    llm_profile: str = Field(..., description="LLM profile being used")
    query_type: QueryType = Field(..., description="Detected query type")
    questions: Optional[List[ClarificationQuestion]] = Field(None, description="Generated questions")
    answers: Optional[Dict[str, Any]] = Field(None, description="User answers")
    enhanced_message: Optional[str] = Field(None, description="Enhanced message for agents")
    auto_instruct: Optional[str] = Field(None, description="Auto-generated presentation instructions")
    status: str = Field(default="pending_clarification", description="Session status")