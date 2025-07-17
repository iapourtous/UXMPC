"""
Meta Agent Models

This module defines the data models for the Meta Agent system,
which intelligently creates specialized agents based on user requirements.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class AgentComplexity(str, Enum):
    """Agent complexity levels"""
    SIMPLE = "simple"      # Single tool, basic logic
    MODERATE = "moderate"  # Multiple tools, some coordination
    COMPLEX = "complex"    # Many tools, complex workflows
    ADVANCED = "advanced"  # Sophisticated reasoning, memory, multi-step


class ToolRequirement(BaseModel):
    """Represents a tool requirement for an agent"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="What the tool should do")
    required: bool = Field(default=True, description="Is this tool required")
    exists: bool = Field(default=False, description="Does this tool already exist")
    existing_service_id: Optional[str] = Field(None, description="ID of existing service")
    service_type: str = Field(default="tool", description="Type of service needed")
    parameters: List[Dict[str, Any]] = Field(default=[], description="Expected parameters")
    

class AgentRequirement(BaseModel):
    """User's request for creating an agent"""
    description: str = Field(..., description="Natural language description of what the agent should do")
    name: Optional[str] = Field(None, description="Suggested name for the agent")
    examples: List[str] = Field(default=[], description="Example interactions or use cases")
    constraints: List[str] = Field(default=[], description="Any specific constraints or requirements")
    llm_profile: str = Field(..., description="LLM profile to use for meta agent")


class AgentProfilePlan(BaseModel):
    """Planned agent profile with all 7 dimensions"""
    name: str = Field(..., description="Agent name")
    endpoint: str = Field(..., description="API endpoint")
    
    # Core configuration
    system_prompt: str = Field(..., description="System prompt for the agent")
    description: str = Field(..., description="Agent description")
    
    # 7 Dimensions
    backstory: str = Field(..., description="Agent's identity and background")
    objectives: List[str] = Field(..., description="Clear objectives")
    constraints: List[str] = Field(..., description="Limitations and restrictions")
    memory_enabled: bool = Field(default=False, description="Should enable memory")
    reasoning_strategy: str = Field(default="standard", description="Reasoning approach")
    personality_traits: Dict[str, str] = Field(..., description="Personality configuration")
    decision_policies: Dict[str, Any] = Field(..., description="Decision-making policies")
    
    # Technical details
    input_schema: str = Field(default="text", description="Input format")
    output_schema: str = Field(default="text", description="Output format")
    complexity: AgentComplexity = Field(..., description="Agent complexity level")
    

class AgentAnalysis(BaseModel):
    """Analysis of agent requirements"""
    requirement_id: str = Field(..., description="Unique requirement ID")
    
    # Understanding
    understood_purpose: str = Field(..., description="What we understood the agent should do")
    use_cases: List[str] = Field(..., description="Identified use cases")
    domain: str = Field(..., description="Domain/category (travel, research, etc.)")
    
    # Requirements
    required_tools: List[ToolRequirement] = Field(..., description="Tools needed")
    required_capabilities: List[str] = Field(..., description="Capabilities needed")
    
    # Recommendations
    suggested_profile: AgentProfilePlan = Field(..., description="Recommended agent profile")
    complexity_assessment: AgentComplexity = Field(..., description="Complexity level")
    estimated_tools_to_create: int = Field(..., description="Number of new tools needed")
    

class CreationStep(BaseModel):
    """A step in the agent creation process"""
    step_type: str = Field(..., description="Type of step: analyze, create_tool, configure, test")
    description: str = Field(..., description="What this step does")
    status: str = Field(default="pending", description="Status: pending, in_progress, completed, failed")
    details: Optional[Dict[str, Any]] = Field(None, description="Step-specific details")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentCreationPlan(BaseModel):
    """Complete plan for creating an agent"""
    analysis: AgentAnalysis = Field(..., description="Requirements analysis")
    steps: List[CreationStep] = Field(..., description="Creation steps")
    estimated_duration: int = Field(..., description="Estimated seconds to complete")
    tools_to_create: List[ToolRequirement] = Field(..., description="New tools to create")
    tools_to_reuse: List[ToolRequirement] = Field(..., description="Existing tools to use")


class MetaAgentProgress(BaseModel):
    """Progress update during agent creation"""
    step: str = Field(..., description="Current step identifier")
    message: str = Field(..., description="Human-readable message")
    progress: int = Field(..., description="Progress percentage (0-100)")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    substeps: Optional[List[str]] = Field(None, description="Substeps if applicable")
    

class CreatedTool(BaseModel):
    """Information about a tool created for the agent"""
    service_id: str = Field(..., description="Created service ID")
    name: str = Field(..., description="Service name")
    description: str = Field(..., description="What the tool does")
    endpoint: str = Field(..., description="Service endpoint")
    success: bool = Field(..., description="Was creation successful")
    error: Optional[str] = Field(None, description="Error if creation failed")


class MetaAgentResponse(BaseModel):
    """Final response from meta agent"""
    success: bool = Field(..., description="Was agent creation successful")
    agent_id: Optional[str] = Field(None, description="Created agent ID")
    agent_name: Optional[str] = Field(None, description="Created agent name")
    agent_endpoint: Optional[str] = Field(None, description="Agent endpoint")
    
    # Creation details
    created_tools: List[CreatedTool] = Field(default=[], description="Tools created")
    reused_tools: List[str] = Field(default=[], description="Existing tools used")
    total_duration: float = Field(..., description="Total creation time in seconds")
    
    # Analysis
    analysis: Optional[AgentAnalysis] = Field(None, description="Requirements analysis")
    creation_log: List[CreationStep] = Field(default=[], description="Creation process log")
    
    # Errors
    error: Optional[str] = Field(None, description="Error message if failed")
    partial_success: bool = Field(default=False, description="Some components succeeded")
    

class MetaAgentRequest(BaseModel):
    """Request to create an agent via meta agent"""
    requirement: AgentRequirement = Field(..., description="Agent requirements")
    auto_activate: bool = Field(default=True, description="Automatically activate agent when ready")
    create_missing_tools: bool = Field(default=True, description="Create tools that don't exist")
    test_agent: bool = Field(default=True, description="Test the agent after creation")
    max_tools_to_create: int = Field(default=5, description="Maximum new tools to create")