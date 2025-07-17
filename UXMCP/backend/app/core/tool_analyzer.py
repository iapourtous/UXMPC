"""
Tool Analyzer for Meta Agent

This module analyzes existing services and determines which ones
can be used for a given agent requirement using LLM evaluation.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from app.services.service_crud import service_crud
from app.models.service import Service
from app.models.meta_agent import ToolRequirement
from app.core.prompt_manager import load_prompt
import httpx
import json

logger = logging.getLogger(__name__)


class ToolAnalyzer:
    """Analyzes tools/services for agent requirements"""
    
    def __init__(self, llm_profile):
        self.llm_profile = llm_profile
        self.base_url = "http://localhost:8000"
    
    async def analyze_required_tools(
        self,
        purpose: str,
        use_cases: List[str],
        domain: str
    ) -> List[ToolRequirement]:
        """
        Ask LLM to determine what tools are needed for the agent
        
        Returns:
            List of tool requirements
        """
        prompt = load_prompt(
            "tool_analyzer/identify_required_tools",
            purpose=purpose,
            domain=domain,
            use_cases=chr(10).join(f"- {uc}" for uc in use_cases)
        )
        
        try:
            response = await self._call_llm(prompt, temperature=0.3)
            if response:
                # Parse JSON response
                import re
                json_match = re.search(r'\[[\s\S]*\]', response)
                if json_match:
                    tools_data = json.loads(json_match.group())
                    return [ToolRequirement(**tool) for tool in tools_data]
        except Exception as e:
            logger.error(f"Failed to analyze required tools: {str(e)}")
        
        return []
    
    async def match_existing_services(
        self,
        required_tools: List[ToolRequirement]
    ) -> Tuple[List[ToolRequirement], List[ToolRequirement]]:
        """
        Match required tools with existing services using LLM evaluation
        
        Returns:
            Tuple of (matched_tools, unmatched_tools)
        """
        # Get service summaries from the API (including inactive services)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/services/summary?active_only=false")
                response.raise_for_status()
                service_summaries = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch service summaries: {str(e)}")
            return [], required_tools
        
        if not service_summaries:
            # No services available, all tools need to be created
            return [], required_tools
        
        # Create a map for quick lookup
        service_map = {s["id"]: s for s in service_summaries}
        
        # Ask LLM to match tools
        prompt = load_prompt(
            "tool_analyzer/match_tools_services",
            required_tools=json.dumps([{
                "name": t.name,
                "description": t.description,
                "type": t.service_type,
                "parameters": t.parameters
            } for t in required_tools], indent=2),
            available_services=json.dumps(service_summaries, indent=2)
        )
        
        try:
            response = await self._call_llm(prompt, temperature=0.1)
            if response:
                # Parse JSON response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    matches = json.loads(json_match.group())
                    
                    matched_tools = []
                    unmatched_tools = []
                    
                    for tool in required_tools:
                        service_id = matches.get(tool.name)
                        if service_id and service_id in service_map:
                            tool.exists = True
                            tool.existing_service_id = service_id
                            matched_tools.append(tool)
                        else:
                            tool.exists = False
                            unmatched_tools.append(tool)
                    
                    return matched_tools, unmatched_tools
                    
        except Exception as e:
            logger.error(f"Failed to match services: {str(e)}")
        
        # If matching fails, assume all tools need to be created
        return [], required_tools
    
    async def evaluate_service_compatibility(
        self,
        service: Service,
        requirement: str
    ) -> Dict[str, Any]:
        """
        Evaluate how well a service matches a requirement
        
        Returns:
            Dict with compatibility score and analysis
        """
        prompt = load_prompt(
            "tool_analyzer/evaluate_service_compatibility",
            requirement=requirement,
            service_name=service.name,
            service_type=service.service_type,
            service_description=service.description,
            service_route=service.route,
            service_params=json.dumps([p.dict() for p in service.params], indent=2),
            service_documentation=service.documentation[:500] if service.documentation else 'None'
        )
        
        try:
            response = await self._call_llm(prompt, temperature=0.2)
            if response:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Failed to evaluate compatibility: {str(e)}")
        
        return {
            "functional_match": 0,
            "parameter_match": 0,
            "output_usefulness": 0,
            "overall_compatibility": 0,
            "can_use": False,
            "reasoning": "Evaluation failed"
        }
    
    async def generate_tool_specification(
        self,
        tool_requirement: ToolRequirement,
        agent_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate detailed specification for creating a new tool
        
        Returns:
            Specification for the AI Service Creator
        """
        prompt = load_prompt(
            "tool_analyzer/generate_tool_specification",
            tool_name=tool_requirement.name,
            tool_description=tool_requirement.description,
            tool_type=tool_requirement.service_type,
            tool_parameters=json.dumps(tool_requirement.parameters, indent=2),
            agent_purpose=agent_context.get('purpose', 'Not specified'),
            agent_domain=agent_context.get('domain', 'General')
        )
        
        try:
            response = await self._call_llm(prompt, temperature=0.5)
            if response:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"Failed to generate specification: {str(e)}")
        
        # Fallback specification
        return {
            "name": tool_requirement.name,
            "description": tool_requirement.description,
            "service_type": tool_requirement.service_type,
            "examples": ["Basic functionality"],
            "special_requirements": [],
            "error_handling": "Return error messages clearly"
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
                {"role": "system", "content": "You are an expert at analyzing software tools and services."},
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