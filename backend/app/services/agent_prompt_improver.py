"""
Agent Prompt Improver Service

This service analyzes an agent's configuration and available tools
to generate an optimized system prompt using LLM intelligence.
"""

import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from app.models.agent import Agent
from app.services.agent_crud import agent_crud
from app.services.service_crud import service_crud
from app.services.llm_crud import llm_crud
from app.core.llm_client import llm_client
from app.core.prompt_manager import load_prompt

logger = logging.getLogger(__name__)


class AgentPromptImprover:
    """Service for improving agent system prompts based on their tools and configuration"""
    
    def __init__(self):
        self.llm_profile = None
    
    async def _get_llm_profile(self):
        """Get the default LLM profile for prompt improvement"""
        if not self.llm_profile:
            # Try to get the most capable LLM profile
            profiles = await llm_crud.list(active_only=True)
            if profiles:
                # Prefer GPT-4 or Claude for better prompt generation
                for profile in profiles:
                    if 'gpt-4' in profile.model.lower() or 'claude' in profile.model.lower():
                        self.llm_profile = profile
                        break
                # Fallback to first active profile
                if not self.llm_profile:
                    self.llm_profile = profiles[0]
        return self.llm_profile
    
    async def _analyze_tools(self, service_names: List[str]) -> List[Dict[str, Any]]:
        """Analyze and format tool information for the agent"""
        tools_info = []
        
        for service_name in service_names:
            service = await service_crud.get_by_name(service_name)
            if not service or not service.active:
                continue
            
            tool_info = {
                "name": service.name,
                "description": service.description or "No description available",
                "documentation": service.documentation,
                "parameters": []
            }
            
            # Format parameters with details
            for param in service.params:
                param_info = {
                    "name": param.name,
                    "type": param.type,
                    "required": param.required,
                    "description": param.description or "No description"
                }
                tool_info["parameters"].append(param_info)
            
            tools_info.append(tool_info)
        
        return tools_info
    
    def _format_agent_config(self, agent: Agent) -> Dict[str, Any]:
        """Format agent configuration for prompt generation"""
        config = {
            "name": agent.name,
            "description": agent.description,
            "current_system_prompt": agent.system_prompt,
            "backstory": getattr(agent, 'backstory', ''),
            "objectives": getattr(agent, 'objectives', []),
            "constraints": getattr(agent, 'constraints', []),
            "reasoning_strategy": getattr(agent, 'reasoning_strategy', 'standard'),
            "personality_traits": getattr(agent, 'personality_traits', {}),
            "decision_policies": getattr(agent, 'decision_policies', {}),
            "memory_enabled": getattr(agent, 'memory_enabled', False),
            "max_iterations": agent.max_iterations,
            "temperature": agent.temperature,
            "require_tool_use": agent.require_tool_use
        }
        return config
    
    async def improve_system_prompt(
        self,
        agent_id: str,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate an improved system prompt for the agent
        
        Args:
            agent_id: The agent to improve
            stream: Whether to stream progress updates
            
        Yields:
            Progress updates and final improved prompt
        """
        try:
            # Step 1: Load agent
            if stream:
                yield {
                    "step": "loading",
                    "message": "Loading agent configuration...",
                    "progress": 10
                }
            
            agent = await agent_crud.get(agent_id)
            if not agent:
                yield {
                    "step": "error",
                    "message": "Agent not found",
                    "error": True
                }
                return
            
            # Step 2: Analyze tools
            if stream:
                yield {
                    "step": "analyzing_tools",
                    "message": f"Analyzing {len(agent.mcp_services)} available tools...",
                    "progress": 20
                }
            
            tools_info = await self._analyze_tools(agent.mcp_services)
            
            # Step 3: Format agent configuration
            if stream:
                yield {
                    "step": "analyzing_config",
                    "message": "Analyzing agent configuration...",
                    "progress": 30
                }
            
            agent_config = self._format_agent_config(agent)
            
            # Step 4: Prepare LLM prompt
            if stream:
                yield {
                    "step": "preparing",
                    "message": "Preparing optimization request...",
                    "progress": 40
                }
            
            # Load the prompt template
            improvement_prompt = load_prompt(
                "agent/improve_system_prompt",
                agent_name=agent.name,
                agent_description=agent.description,
                agent_config=json.dumps(agent_config, indent=2),
                tools_info=json.dumps(tools_info, indent=2),
                tools_count=len(tools_info),
                current_prompt=agent.system_prompt or "No current system prompt"
            )
            
            # Step 5: Call LLM
            if stream:
                yield {
                    "step": "generating",
                    "message": "Generating optimized system prompt...",
                    "progress": 50
                }
            
            llm_profile = await self._get_llm_profile()
            if not llm_profile:
                yield {
                    "step": "error",
                    "message": "No active LLM profile found",
                    "error": True
                }
                return
            
            # Make the LLM call
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert in prompt engineering and agent system design. Your task is to create comprehensive, well-structured system prompts that maximize agent effectiveness."
                },
                {
                    "role": "user",
                    "content": improvement_prompt
                }
            ]
            
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )
            
            if response and "choices" in response and response["choices"]:
                improved_prompt = response["choices"][0]["message"]["content"]
                
                # Step 6: Return improved prompt
                if stream:
                    yield {
                        "step": "complete",
                        "message": "System prompt optimization complete!",
                        "progress": 100,
                        "improved_prompt": improved_prompt,
                        "metadata": {
                            "tools_analyzed": len(tools_info),
                            "agent_name": agent.name,
                            "optimization_model": llm_profile.model
                        }
                    }
                else:
                    yield {
                        "improved_prompt": improved_prompt
                    }
            else:
                yield {
                    "step": "error",
                    "message": "Failed to generate improved prompt",
                    "error": True
                }
                
        except Exception as e:
            logger.error(f"Error improving system prompt: {str(e)}")
            yield {
                "step": "error",
                "message": f"Unexpected error: {str(e)}",
                "error": True
            }
    
    async def analyze_prompt_quality(
        self,
        prompt: str,
        tools_info: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze the quality of a system prompt
        
        Returns:
            Quality metrics and suggestions
        """
        metrics = {
            "has_tool_documentation": any("tool" in prompt.lower()),
            "has_methodology": any(word in prompt.lower() for word in ["phase", "step", "methodology", "approach"]),
            "has_examples": "```" in prompt or "example" in prompt.lower(),
            "has_quality_checks": any(word in prompt.lower() for word in ["verify", "check", "validate", "ensure"]),
            "word_count": len(prompt.split()),
            "tools_mentioned": sum(1 for tool in tools_info if tool["name"] in prompt),
            "structure_score": 0
        }
        
        # Calculate structure score
        if "##" in prompt:
            metrics["structure_score"] += 25
        if "###" in prompt:
            metrics["structure_score"] += 25
        if "-" in prompt or "*" in prompt:
            metrics["structure_score"] += 25
        if metrics["has_examples"]:
            metrics["structure_score"] += 25
        
        # Overall quality score
        metrics["overall_score"] = (
            (metrics["has_tool_documentation"] * 20) +
            (metrics["has_methodology"] * 20) +
            (metrics["has_examples"] * 20) +
            (metrics["has_quality_checks"] * 15) +
            (metrics["structure_score"] * 0.25)
        )
        
        return metrics
    
    async def improve_prompt_from_feedback(
        self,
        agent_id: str,
        user_feedback: str,
        last_response: str,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        stream: bool = True
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Improve system prompt based on negative user feedback
        
        Args:
            agent_id: The agent to improve
            user_feedback: User's description of what was wrong
            last_response: The problematic response from the agent
            conversation_context: Recent conversation history
            stream: Whether to stream progress updates
            
        Yields:
            Progress updates and improved prompt
        """
        try:
            # Step 1: Load agent
            if stream:
                yield {
                    "step": "loading",
                    "message": "Loading agent configuration...",
                    "progress": 10
                }
            
            agent = await agent_crud.get(agent_id)
            if not agent:
                yield {
                    "step": "error",
                    "message": "Agent not found",
                    "error": True
                }
                return
            
            # Step 2: Analyze tools
            if stream:
                yield {
                    "step": "analyzing_feedback",
                    "message": "Analyzing feedback and context...",
                    "progress": 20
                }
            
            tools_info = await self._analyze_tools(agent.mcp_services)
            
            # Step 3: Prepare context
            if stream:
                yield {
                    "step": "analyzing_patterns",
                    "message": "Identifying improvement patterns...",
                    "progress": 30
                }
            
            # Format conversation context
            context_str = json.dumps(conversation_context[-5:] if conversation_context else [], indent=2)
            
            # Step 4: Prepare improvement prompt
            if stream:
                yield {
                    "step": "preparing",
                    "message": "Preparing improvement strategy...",
                    "progress": 40
                }
            
            # Load the feedback improvement template
            improvement_prompt = load_prompt(
                "agent/improve_from_feedback",
                agent_name=agent.name,
                current_prompt=agent.system_prompt or "No current system prompt",
                tools_info=json.dumps(tools_info, indent=2),
                tools_count=len(tools_info),
                user_feedback=user_feedback,
                last_response=last_response,
                conversation_context=context_str
            )
            
            # Step 5: Call LLM for improvement
            if stream:
                yield {
                    "step": "generating",
                    "message": "Generating improved system prompt based on feedback...",
                    "progress": 60
                }
            
            llm_profile = await self._get_llm_profile()
            if not llm_profile:
                yield {
                    "step": "error",
                    "message": "No active LLM profile found",
                    "error": True
                }
                return
            
            # Make the LLM call with focus on general improvements
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert in continuous improvement and prompt engineering. Focus on GENERAL improvements that address classes of issues, not specific cases. Avoid overfitting to individual feedback."
                },
                {
                    "role": "user",
                    "content": improvement_prompt
                }
            ]
            
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.7,
                max_tokens=4000
            )
            
            if response and "choices" in response and response["choices"]:
                improved_prompt = response["choices"][0]["message"]["content"]
                
                # Step 6: Analyze improvements made
                if stream:
                    yield {
                        "step": "analyzing_improvements",
                        "message": "Analyzing improvements made...",
                        "progress": 80
                    }
                
                # Quick analysis of what changed
                improvement_summary = self._analyze_improvements(
                    agent.system_prompt or "",
                    improved_prompt
                )
                
                # Step 7: Return improved prompt
                if stream:
                    yield {
                        "step": "complete",
                        "message": "System prompt improved based on feedback!",
                        "progress": 100,
                        "improved_prompt": improved_prompt,
                        "improvement_summary": improvement_summary,
                        "metadata": {
                            "agent_name": agent.name,
                            "feedback_addressed": user_feedback[:100] + "..." if len(user_feedback) > 100 else user_feedback,
                            "optimization_model": llm_profile.model
                        }
                    }
                else:
                    yield {
                        "improved_prompt": improved_prompt,
                        "improvement_summary": improvement_summary
                    }
            else:
                yield {
                    "step": "error",
                    "message": "Failed to generate improved prompt",
                    "error": True
                }
                
        except Exception as e:
            logger.error(f"Error improving prompt from feedback: {str(e)}")
            yield {
                "step": "error",
                "message": f"Unexpected error: {str(e)}",
                "error": True
            }
    
    def _analyze_improvements(self, original: str, improved: str) -> Dict[str, Any]:
        """Analyze what improvements were made"""
        return {
            "length_change": len(improved) - len(original),
            "sections_added": improved.count("##") - original.count("##"),
            "lists_added": improved.count("- ") - original.count("- "),
            "code_blocks_added": improved.count("```") - original.count("```"),
            "has_new_methodology": "methodology" in improved.lower() and "methodology" not in original.lower(),
            "has_new_validation": "validate" in improved.lower() and "validate" not in original.lower()
        }


# Singleton instance
agent_prompt_improver = AgentPromptImprover()