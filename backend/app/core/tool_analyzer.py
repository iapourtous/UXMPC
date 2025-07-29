"""
Tool Analyzer for Meta Agent

This module analyzes existing services and determines which ones
can be used for a given agent requirement using LLM evaluation.
"""

import logging
import asyncio
import httpx
from typing import List, Dict, Any, Optional, Tuple
from app.services.service_crud import service_crud
from app.models.service import Service
from app.models.meta_agent import ToolRequirement
from app.core.prompt_manager import load_prompt
from app.core.llm_client import llm_client
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
        
        logger.info(f"Analyzing tools for purpose: {purpose}")
        logger.info(f"Domain: {domain}")
        logger.info(f"Use cases: {use_cases}")
        logger.debug(f"Generated prompt: {prompt[:500]}...")
        
        try:
            response = await llm_client.call_simple(
                llm_profile=self.llm_profile,
                prompt=prompt,
                system_message="You are an expert system architect. Always respond with valid JSON format containing a 'tools' array.",
                temperature=0.3
            )
            logger.info(f"Full LLM response for tool analysis: {response}")
            
            if response:
                try:
                    # Parse JSON response expecting {"tools": [...]} format
                    response_data = json.loads(response)
                    logger.info(f"Parsed JSON response: {response_data}")
                    
                    # Extract tools array from the response
                    if isinstance(response_data, dict) and "tools" in response_data:
                        tools_data = response_data["tools"]
                        logger.info(f"Extracted tools array: {tools_data}")
                        if isinstance(tools_data, list):
                            return [ToolRequirement(**tool) for tool in tools_data]
                        else:
                            logger.error(f"Tools property is not an array: {type(tools_data)}")
                    elif isinstance(response_data, list):
                        # Fallback: if response is directly an array
                        logger.info(f"Response is directly an array: {response_data}")
                        return [ToolRequirement(**tool) for tool in response_data]
                    else:
                        logger.error(f"Unexpected JSON structure: {response_data}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing failed: {e}")
                    logger.error(f"Raw response: {response}")
                    
                except Exception as e:
                    logger.error(f"Error processing tools: {e}")
                    logger.error(f"Response data: {response_data if 'response_data' in locals() else 'None'}")
                
                logger.error("Failed to extract valid tools from response")
        except Exception as e:
            logger.error(f"Failed to analyze required tools: {str(e)}")
        
        return []
    
    async def match_existing_services(
        self,
        required_tools: List[ToolRequirement]
    ) -> Tuple[List[ToolRequirement], List[ToolRequirement]]:
        """
        Match required tools with existing services using improved multi-stage evaluation
        
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
            logger.info("No existing services found, all tools will need to be created")
            return [], required_tools

        logger.info(f"Found {len(service_summaries)} existing services for matching")
        
        # Create a map for quick lookup
        service_map = {s["id"]: s for s in service_summaries}

        # Ask improved LLM to match tools with better prompt
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
            response = await llm_client.call_simple(
                llm_profile=self.llm_profile,
                prompt=prompt,
                system_message="You are an expert at matching software tools with existing services. Always respond with valid JSON format.",
                temperature=0.2
            )
            
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
                            logger.info(f"✓ Matched {tool.name} with service {service_map[service_id]['name']}")
                        else:
                            tool.exists = False
                            unmatched_tools.append(tool)
                            logger.info(f"✗ No match found for {tool.name}, will create new service")
                    
                    logger.info(f"Matching complete: {len(matched_tools)} matched, {len(unmatched_tools)} to create")
                    return matched_tools, unmatched_tools
                    
        except Exception as e:
            logger.error(f"Failed to match services: {str(e)}")

        # If matching fails, assume all tools need to be created
        logger.warning("Tool matching failed, will create all tools")
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
            response = await llm_client.call_simple(
                llm_profile=self.llm_profile,
                prompt=prompt,
                system_message="You are an expert software architect evaluating service compatibility. Always respond with valid JSON format.",
                temperature=0.2
            )
            
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
            response = await llm_client.call_simple(
                llm_profile=self.llm_profile,
                prompt=prompt,
                system_message="You are an expert at designing tool specifications. Always respond with valid JSON format.",
                temperature=0.5
            )
            
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
    
