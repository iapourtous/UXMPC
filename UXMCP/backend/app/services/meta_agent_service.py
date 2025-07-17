"""
Meta Agent Service

This service intelligently creates specialized agents based on user requirements.
It analyzes needs, determines profiles, manages tools, and orchestrates the entire creation process.
"""

import logging
import asyncio
import json
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from app.models.meta_agent import (
    AgentRequirement, AgentAnalysis, AgentProfilePlan,
    ToolRequirement, CreationStep, AgentCreationPlan,
    MetaAgentProgress, CreatedTool, MetaAgentResponse,
    AgentComplexity
)
from app.models.agent import AgentCreate
from app.models.llm import LLMProfile
from app.services.llm_crud import llm_crud
from app.services.agent_crud import agent_crud
from app.services.service_crud import service_crud
from app.services.agent_service import create_agent as create_service_agent
from app.core.tool_analyzer import ToolAnalyzer
from app.core.dynamic_router import mount_service
from app.core.prompt_manager import load_prompt
import httpx

logger = logging.getLogger(__name__)


class MetaAgentService:
    """Service for creating agents intelligently"""
    
    def __init__(self, llm_profile: LLMProfile, app):
        self.llm_profile = llm_profile
        self.app = app
        self.tool_analyzer = ToolAnalyzer(llm_profile)
        self.base_url = "http://localhost:8000"
    
    async def create_agent_from_requirement(
        self,
        requirement: AgentRequirement,
        auto_activate: bool = True,
        create_missing_tools: bool = True,
        test_agent: bool = True,
        max_tools_to_create: int = 5
    ) -> AsyncGenerator[MetaAgentProgress, None]:
        """
        Create an agent based on natural language requirements
        Yields progress updates throughout the process
        """
        start_time = datetime.utcnow()
        requirement_id = str(uuid.uuid4())
        created_tools = []
        agent_id = None
        
        try:
            # Step 1: Analyze requirements
            yield MetaAgentProgress(
                step="analyzing",
                message="Analyzing your requirements...",
                progress=5,
                details={"requirement": requirement.description}
            )
            
            analysis = await self._analyze_requirements(requirement, requirement_id)
            
            yield MetaAgentProgress(
                step="analysis_complete",
                message=f"I understand you need: {analysis.understood_purpose}",
                progress=15,
                details={
                    "domain": analysis.domain,
                    "complexity": analysis.complexity_assessment,
                    "use_cases": analysis.use_cases[:3]  # First 3 use cases
                }
            )
            
            # Step 2: Identify required tools
            yield MetaAgentProgress(
                step="identifying_tools",
                message="Identifying required tools and capabilities...",
                progress=25
            )
            
            # Log all required tools for debugging
            logger.info(f"Total required tools identified: {len(analysis.required_tools)}")
            for tool in analysis.required_tools:
                logger.info(f"  - {tool.name}: {tool.description}")
            
            # Match with existing services
            matched_tools, unmatched_tools = await self.tool_analyzer.match_existing_services(
                analysis.required_tools
            )
            
            yield MetaAgentProgress(
                step="tools_identified",
                message=f"Found {len(matched_tools)} existing tools, need to create {len(unmatched_tools)} new ones",
                progress=35,
                details={
                    "existing_tools": [t.name for t in matched_tools],
                    "tools_to_create": [t.name for t in unmatched_tools]
                }
            )
            
            # Step 3: Create missing tools if allowed
            if create_missing_tools and unmatched_tools:
                tools_to_create = unmatched_tools[:max_tools_to_create]
                
                for i, tool in enumerate(tools_to_create):
                    progress = 40 + (i * 30 / len(tools_to_create))
                    
                    yield MetaAgentProgress(
                        step="creating_tool",
                        message=f"Creating tool: {tool.name}",
                        progress=int(progress),
                        details={"tool": tool.name, "description": tool.description}
                    )
                    
                    # Generate detailed specification
                    spec = await self.tool_analyzer.generate_tool_specification(
                        tool,
                        {"purpose": analysis.understood_purpose, "domain": analysis.domain}
                    )
                    
                    # Create the tool using AI Service Creator
                    created_tool = await self._create_tool_with_ai(tool, spec)
                    
                    if created_tool.success:
                        yield MetaAgentProgress(
                            step="tool_created",
                            message=f"Successfully created: {tool.name}",
                            progress=int(progress + 5),
                            details={"service_id": created_tool.service_id}
                        )
                        created_tools.append(created_tool)
                        # Update the tool requirement with the new service
                        tool.exists = True
                        tool.existing_service_id = created_tool.service_id
                    else:
                        yield MetaAgentProgress(
                            step="tool_failed",
                            message=f"Failed to create {tool.name}: {created_tool.error}",
                            progress=int(progress + 5),
                            details={"error": created_tool.error}
                        )
            
            # Step 4: Prepare final tool list
            all_tools = matched_tools + [t for t in unmatched_tools if t.exists]
            tool_service_names = []
            
            # Activate inactive services if needed
            for tool in all_tools:
                if tool.existing_service_id:
                    service = await service_crud.get(tool.existing_service_id)
                    if service:
                        tool_service_names.append(service.name)
                        if not service.active and auto_activate:
                            yield MetaAgentProgress(
                                step="activating_service",
                                message=f"Activating service: {service.name}",
                                progress=70,
                                details={"service": service.name}
                            )
                            try:
                                await mount_service(self.app, service)
                                await service_crud.activate(service.id)
                            except Exception as e:
                                logger.error(f"Failed to activate service {service.name}: {e}")
            
            # Step 5: Create the agent
            yield MetaAgentProgress(
                step="creating_agent",
                message="Creating your intelligent agent...",
                progress=75,
                details={"name": analysis.suggested_profile.name}
            )
            
            agent = await self._create_agent(
                analysis.suggested_profile,
                tool_service_names,
                requirement.llm_profile
            )
            
            if agent:
                agent_id = agent.id
                
                # Step 6: Activate agent if requested
                if auto_activate:
                    yield MetaAgentProgress(
                        step="activating_agent",
                        message="Activating your agent...",
                        progress=85
                    )
                    
                    try:
                        activated = await agent_crud.activate(agent_id)
                        yield MetaAgentProgress(
                            step="agent_activated",
                            message=f"Agent '{agent.name}' is now active!",
                            progress=90,
                            details={"endpoint": agent.endpoint}
                        )
                    except Exception as e:
                        logger.error(f"Failed to activate agent: {e}")
                
                # Step 7: Test agent if requested
                if test_agent and agent.active:
                    yield MetaAgentProgress(
                        step="testing_agent",
                        message="Testing your agent...",
                        progress=95
                    )
                    
                    test_result = await self._test_agent(agent)
                    
                    if test_result["success"]:
                        yield MetaAgentProgress(
                            step="test_complete",
                            message="Agent tested successfully!",
                            progress=98,
                            details={"test_output": str(test_result.get("output", ""))[:100]}
                        )
                    else:
                        yield MetaAgentProgress(
                            step="test_failed",
                            message=f"Agent test failed: {test_result.get('error', 'Unknown error')}",
                            progress=98,
                            details={"error": test_result.get("error")}
                        )
            
            # Final response
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            response = MetaAgentResponse(
                success=agent_id is not None,
                agent_id=agent_id,
                agent_name=agent.name if agent else None,
                agent_endpoint=agent.endpoint if agent else None,
                created_tools=created_tools,
                reused_tools=[t.name for t in matched_tools],
                total_duration=duration,
                analysis=analysis,
                partial_success=len(created_tools) > 0
            )
            
            yield MetaAgentProgress(
                step="complete",
                message="Agent creation complete!",
                progress=100,
                details=response.dict()
            )
            
        except Exception as e:
            logger.error(f"Meta agent error: {str(e)}")
            yield MetaAgentProgress(
                step="error",
                message="Failed to create agent",
                progress=100,
                details={"error": str(e)}
            )
    
    async def _analyze_requirements(
        self,
        requirement: AgentRequirement,
        requirement_id: str
    ) -> AgentAnalysis:
        """Analyze requirements using LLM"""
        prompt = load_prompt(
            "meta_agent/analyze_agent_requirements",
            description=requirement.description,
            suggested_name=requirement.name or "Not specified",
            examples=json.dumps(requirement.examples, indent=2) if requirement.examples else "None",
            constraints=json.dumps(requirement.constraints, indent=2) if requirement.constraints else "None"
        )
        
        try:
            response = await self._call_llm(prompt, temperature=0.5)
            if response:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    data = json.loads(json_match.group())
                    
                    # Get required tools based on capabilities
                    required_tools = await self.tool_analyzer.analyze_required_tools(
                        data["understood_purpose"],
                        data["use_cases"],
                        data["domain"]
                    )
                    
                    # Create profile plan
                    profile = AgentProfilePlan(
                        name=data.get("suggested_name", requirement.name or "custom_agent"),
                        endpoint=data.get("suggested_endpoint", "/api/agent/custom"),
                        system_prompt=f"You are an AI agent specialized in {data['domain']}. {data['suggested_profile']['backstory']}",
                        description=data["understood_purpose"],
                        backstory=data["suggested_profile"]["backstory"],
                        objectives=data["suggested_profile"]["objectives"],
                        constraints=data["suggested_profile"]["constraints"],
                        memory_enabled=data["suggested_profile"]["memory_enabled"],
                        reasoning_strategy=data["suggested_profile"]["reasoning_strategy"],
                        personality_traits=data["suggested_profile"]["personality_traits"],
                        decision_policies=data["suggested_profile"]["decision_policies"],
                        complexity=AgentComplexity(data["complexity"])
                    )
                    
                    return AgentAnalysis(
                        requirement_id=requirement_id,
                        understood_purpose=data["understood_purpose"],
                        use_cases=data["use_cases"],
                        domain=data["domain"],
                        required_tools=required_tools,
                        required_capabilities=data["required_capabilities"],
                        suggested_profile=profile,
                        complexity_assessment=AgentComplexity(data["complexity"]),
                        estimated_tools_to_create=len([t for t in required_tools if not t.exists])
                    )
                    
        except Exception as e:
            logger.error(f"Failed to analyze requirements: {str(e)}")
            raise
    
    async def _create_tool_with_ai(
        self,
        tool: ToolRequirement,
        specification: Dict[str, Any]
    ) -> CreatedTool:
        """Create a tool using the AI Service Creator"""
        try:
            # Get service creator agent
            service_agent = await create_service_agent(self.llm_profile.name, self.app)
            
            # Prepare the description with detailed requirements
            detailed_description = f"""{specification['description']}

Examples:
{chr(10).join(specification.get('examples', ['No specific examples']))}

Special Requirements:
{chr(10).join(specification.get('special_requirements', ['None']))}

Error Handling: {specification.get('error_handling', 'Return clear error messages')}
"""
            
            # Create the service
            service_id = None
            success = False
            error = None
            
            async for update in service_agent.create_service_from_description(
                name=tool.name,
                description=detailed_description,
                service_type=tool.service_type
            ):
                if update["step"] == "success":
                    service_id = update["service_id"]
                    success = True
                elif update["step"] == "error":
                    error = update.get("error", "Unknown error")
                elif update["step"] == "timeout":
                    error = "Service creation timed out"
            
            return CreatedTool(
                service_id=service_id or "",
                name=tool.name,
                description=tool.description,
                endpoint=f"/api/{tool.name}",
                success=success,
                error=error
            )
            
        except Exception as e:
            logger.error(f"Failed to create tool {tool.name}: {str(e)}")
            return CreatedTool(
                service_id="",
                name=tool.name,
                description=tool.description,
                endpoint="",
                success=False,
                error=str(e)
            )
    
    async def _create_agent(
        self,
        profile: AgentProfilePlan,
        tool_names: List[str],
        llm_profile_name: str
    ) -> Optional[Any]:
        """Create the actual agent"""
        try:
            # Determine max_iterations based on complexity
            max_iterations = 5  # Default
            if profile.complexity in [AgentComplexity.COMPLEX, AgentComplexity.ADVANCED]:
                max_iterations = 10
            
            agent_data = AgentCreate(
                name=profile.name,
                llm_profile=llm_profile_name,
                mcp_services=tool_names,
                system_prompt=profile.system_prompt,
                endpoint=profile.endpoint,
                description=profile.description,
                backstory=profile.backstory,
                objectives=profile.objectives,
                constraints=profile.constraints,
                memory_enabled=profile.memory_enabled,
                reasoning_strategy=profile.reasoning_strategy,
                personality_traits=profile.personality_traits,
                decision_policies=profile.decision_policies,
                input_schema=profile.input_schema,
                output_schema=profile.output_schema,
                max_iterations=max_iterations,
                active=False  # Start inactive
            )
            
            return await agent_crud.create(agent_data)
            
        except Exception as e:
            logger.error(f"Failed to create agent: {str(e)}")
            return None
    
    async def _test_agent(self, agent) -> Dict[str, Any]:
        """Test the created agent"""
        try:
            # Simple test based on agent type
            test_input = "Hello, can you introduce yourself and explain what you can help me with?"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/agents/{agent.id}/execute",
                    json={
                        "input": test_input,
                        "execution_options": {}
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": result.get("success", False),
                        "output": result.get("output"),
                        "error": result.get("error")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Test failed with status {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to test agent: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _call_llm(
        self,
        prompt: str,
        temperature: float = 0.7
    ) -> Optional[str]:
        """Call the LLM API"""
        try:
            endpoint = self.llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [
                {"role": "system", "content": "You are an expert AI architect designing intelligent agents."},
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": self.llm_profile.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": self.llm_profile.max_tokens
            }
            
            # Add JSON mode if supported
            if self.llm_profile.mode == "json":
                payload["response_format"] = {"type": "json_object"}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"LLM API call failed: {str(e)}")
            return None


# Factory function
async def create_meta_agent(llm_profile_name: str, app) -> MetaAgentService:
    """Create a meta agent service with specified LLM profile"""
    llm_profile = await llm_crud.get_by_name(llm_profile_name)
    if not llm_profile or not llm_profile.active:
        raise ValueError(f"LLM profile '{llm_profile_name}' not found or inactive")
    
    # Ensure LLM profile is in JSON mode for structured responses
    if llm_profile.mode != "json":
        raise ValueError(f"LLM profile '{llm_profile_name}' must be configured with mode='json' for meta agent. Current mode: '{llm_profile.mode}'")
    
    return MetaAgentService(llm_profile, app)