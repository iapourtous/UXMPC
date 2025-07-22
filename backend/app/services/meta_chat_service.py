"""
Meta Chat Service

Routes user requests to appropriate agents or generates direct responses
"""

import logging
import json
import uuid
from typing import Optional, Dict, Any, List
import httpx
import asyncio

from app.models.meta_chat import (
    MetaChatRequest, MetaChatResponse, ChatIntent, ResponseType
)
from app.models.agent import Agent
from app.models.llm import LLMProfile
from app.services.llm_crud import llm_crud
from app.services.agent_crud import agent_crud
from app.services.agent_executor import agent_executor
from app.services.meta_agent_service import create_meta_agent
from app.models.meta_agent import AgentRequirement
from app.models.agent import AgentExecution
from app.core.prompt_manager import load_prompt
from app.services.html_validator import html_validator

logger = logging.getLogger(__name__)


class MetaChatService:
    """Service for intelligent request routing"""
    
    def __init__(self, llm_profile: LLMProfile):
        self.llm_profile = llm_profile
        
    async def process_request(self, request: MetaChatRequest) -> MetaChatResponse:
        """Process a user request through the meta-chat system"""
        try:
            # Check if manual mode with selected agents
            if request.mode == "manual" and request.selected_agents:
                logger.info(f"Manual mode: Using selected agents: {request.selected_agents}")
                
                # Execute multiple agents in parallel
                response_data = await self._execute_multiple_agents(
                    request.selected_agents,
                    request.message
                )
                
                # Generate HTML visualization
                # Create a simple intent for manual mode
                intent = ChatIntent(
                    intent="manual multi-agent query",
                    response_type=ResponseType.AGENT,
                    needs_agent=True,
                    agent_type="multiple",
                    parameters={},
                    confidence=1.0
                )
                
                html_response = await self._generate_html_response(
                    request.message,
                    response_data,
                    intent,
                    agent_name="Multiple Agents",
                    custom_instruct=request.instruct
                )
                
                return MetaChatResponse(
                    success=True,
                    agent_used="Multiple Agents",
                    agent_created=False,
                    response_data=response_data,
                    html_response=html_response,
                    metadata={
                        "mode": "manual",
                        "agents_used": request.selected_agents,
                        "execution_mode": "multi_agent"
                    },
                    session_id=str(uuid.uuid4())
                )
            
            # Auto mode: existing flow
            # Step 1: Analyze the request
            logger.info(f"Analyzing request: {request.message}")
            intent = await self._analyze_request(request.message)
            logger.info(f"Intent analysis: {intent.model_dump()}")
            
            # Step 2: Always use an agent (find existing or create new)
            logger.info("Looking for suitable agent")
            
            # Step 3: Find or create agent - pass original message for better context
            agent = await self._find_suitable_agent(intent, request.message)
            agent_created = False
            
            # Check coverage threshold
            coverage_threshold = 0.8  # 80% coverage required
            agent_coverage = getattr(agent, '_coverage', 1.0) if agent else 0.0
            missing_capabilities = getattr(agent, '_missing_capabilities', []) if agent else []
            
            if not agent or agent_coverage < coverage_threshold:
                if agent:
                    logger.info(f"Agent {agent.name} coverage insufficient ({agent_coverage:.2f} < {coverage_threshold}), creating custom agent")
                    logger.info(f"Missing capabilities: {missing_capabilities}")
                    # Store missing capabilities for agent creation
                    self._last_missing_capabilities = missing_capabilities
                else:
                    logger.info("No suitable agent found, creating one")
                    self._last_missing_capabilities = []
                
                agent = await self._create_agent_for_intent(intent, request.message)
                agent_created = True
                
                if not agent:
                    return MetaChatResponse(
                        success=False,
                        error="Failed to create agent for this request",
                        metadata={"intent": intent.model_dump()}
                    )
            
            # Step 4: Execute agent
            logger.info(f"Executing agent: {agent.name}")
            response_data = await self._execute_agent(agent, intent, request.message)
            
            # Generate HTML visualization
            html_response = await self._generate_html_response(
                request.message,
                response_data,
                intent,
                agent.name,
                request.instruct
            )
            
            return MetaChatResponse(
                success=True,
                agent_used=agent.name,
                agent_created=agent_created,
                response_data=response_data,
                html_response=html_response,
                metadata={
                    "intent": intent.model_dump(),
                    "agent_id": str(agent.id)
                },
                session_id=str(uuid.uuid4())
            )
                
        except Exception as e:
            logger.error(f"Meta-chat error: {str(e)}")
            return MetaChatResponse(
                success=False,
                error=str(e)
            )
    
    async def _analyze_request(self, message: str) -> ChatIntent:
        """Analyze user request to determine intent"""
        # Get list of available agents
        agents = await agent_crud.list(active_only=True)
        agent_list = []
        for agent in agents:
            agent_list.append({
                "name": agent.name,
                "description": agent.description
            })
        
        prompt = load_prompt(
            "meta_chat/analyze_intent",
            message=message,
            agent_list=json.dumps(agent_list, indent=2)
        )
        
        response = await self._call_llm(prompt)
        if response:
            try:
                data = json.loads(response)
                return ChatIntent(**data)
            except Exception as e:
                logger.error(f"Failed to parse intent: {e}")
                # Fallback to direct response
                return ChatIntent(
                    intent="unclear request",
                    response_type=ResponseType.DIRECT,
                    needs_agent=False,
                    confidence=0.5,
                    parameters={}
                )
        
        raise ValueError("No response from LLM")
    
    async def _find_suitable_agent(self, intent: ChatIntent, original_message: str) -> Optional[Agent]:
        """Find an existing agent that can handle the intent using semantic similarity + LLM evaluation"""
        # Get all active agents
        all_agents = await agent_crud.list(active_only=True)
        
        if not all_agents:
            return None
        
        # Pre-select agents using semantic similarity
        selected_agents = await self._preselect_agents_by_similarity(all_agents, original_message)
        
        # Prepare agent list with full descriptions for LLM evaluation
        agent_list = []
        for agent in selected_agents:
            agent_info = {
                "name": agent.name,
                "description": agent.description or "No description",
                "services": agent.mcp_services,
                "input_format": agent.input_schema if hasattr(agent, 'input_schema') else "text"
            }
            
            # Add objectives if available
            if hasattr(agent, 'objectives') and agent.objectives:
                agent_info["objectives"] = agent.objectives[:3]  # First 3 objectives
            
            # Add usage history for better selection
            if hasattr(agent, 'usage_history') and agent.usage_history:
                agent_info["usage_history"] = agent.usage_history[:3]  # Recent usage examples
                
            agent_list.append(agent_info)
        
        # Ask LLM to find the best agent
        prompt = load_prompt(
            "meta_chat/find_suitable_agent",
            original_message=original_message,
            agent_list=json.dumps(agent_list, indent=2)
        )

        response = await self._call_llm(prompt)
        
        if response:
            try:
                data = json.loads(response)
                selected_agent = data.get("selected_agent", "").strip()
                coverage = data.get("coverage", 0.0)
                missing_capabilities = data.get("missing_capabilities", [])
                reasoning = data.get("reasoning", "")
                
                # Log the evaluation results
                logger.info(f"Agent evaluation: {selected_agent}, coverage: {coverage}, missing: {missing_capabilities}")
                
                if selected_agent and selected_agent.lower() not in ["none", "null"]:
                    agent_name = selected_agent
                    
                    # Find the agent by name in selected agents
                    for agent in selected_agents:
                        if agent.name.lower() == agent_name.lower():
                            logger.info(f"LLM selected agent: {agent.name} (coverage: {coverage})")
                            # Store coverage info in agent object for later use
                            agent._coverage = coverage
                            agent._missing_capabilities = missing_capabilities
                            return agent
                    
                    # If exact match not found, try partial match
                    for agent in selected_agents:
                        if agent_name.lower() in agent.name.lower() or agent.name.lower() in agent_name.lower():
                            logger.info(f"LLM selected agent (partial match): {agent.name} (coverage: {coverage})")
                            agent._coverage = coverage
                            agent._missing_capabilities = missing_capabilities
                            return agent
            except Exception as e:
                logger.error(f"Failed to parse agent selection: {e}")
        
        logger.info("No suitable agent found by LLM")
        return None
    
    async def _preselect_agents_by_similarity(self, all_agents: List[Agent], query: str) -> List[Agent]:
        """Pre-select agents using semantic similarity, limiting to top 10 most relevant"""
        from app.services.agent_embedding_service import agent_embedding_service
        
        # Calculate query embedding
        query_embedding = agent_embedding_service.calculate_query_embedding(query)
        
        if not query_embedding:
            logger.warning("Could not calculate query embedding, returning all agents")
            return all_agents
        
        # Separate agents with and without embeddings
        agents_with_embeddings = []
        agents_without_embeddings = []
        
        for agent in all_agents:
            if hasattr(agent, 'response_embedding') and agent.response_embedding:
                agents_with_embeddings.append(agent)
            else:
                agents_without_embeddings.append(agent)
        
        # Calculate similarities for agents with embeddings
        scored_agents = []
        for agent in agents_with_embeddings:
            similarity = agent_embedding_service.cosine_similarity(
                query_embedding, 
                agent.response_embedding
            )
            scored_agents.append((agent, similarity))
        
        # Sort by similarity (descending)
        scored_agents.sort(key=lambda x: x[1], reverse=True)
        
        # Take top 10 most similar agents
        top_agents = [agent for agent, _ in scored_agents[:10]]
        
        # Add agents without embeddings (new agents) to ensure we have candidates
        # But limit total to 10 agents
        remaining_slots = 10 - len(top_agents)
        if remaining_slots > 0:
            top_agents.extend(agents_without_embeddings[:remaining_slots])
        
        logger.info(f"Pre-selected {len(top_agents)} agents out of {len(all_agents)} total agents")
        
        # Log similarity scores for debugging
        for agent, similarity in scored_agents[:5]:  # Log top 5
            logger.info(f"Agent {agent.name}: similarity={similarity:.3f}")
        
        return top_agents
    
    async def _create_agent_for_intent(self, intent: ChatIntent, original_message: str) -> Optional[Agent]:
        """Create a new agent using Meta Agent based on the original user request"""
        try:
            # Check if we have info about missing capabilities from previous agent evaluation
            missing_info = ""
            if hasattr(self, '_last_missing_capabilities') and self._last_missing_capabilities:
                missing_info = f"\nIMPORTANT: The existing agents were missing these capabilities: {', '.join(self._last_missing_capabilities)}"
            
            # Use the original message for better context
            requirement_desc = f"""Create an agent to handle this COMPLETE user request: "{original_message}"
            
The agent should be able to fulfill ALL aspects of this request.
If the request asks for multiple types of information (e.g., weather AND news), 
the agent should be able to provide ALL of them in a unified response.{missing_info}

Create appropriate tools and integrations to handle every part of the request.
For example, if user asks for "weather and news", create an agent that can fetch BOTH."""
            
            # Let the LLM generate an appropriate name based on the request
            agent_name = intent.intent.lower().replace(" ", "_")[:30] + "_agent"
            
            requirement = AgentRequirement(
                description=requirement_desc,
                name=agent_name,
                llm_profile=self.llm_profile.name
            )
            
            # Use meta agent to create
            meta_agent = await create_meta_agent(self.llm_profile.name, None)
            
            agent_id = None
            async for progress in meta_agent.create_agent_from_requirement(
                requirement,
                auto_activate=True,
                create_missing_tools=True,
                test_agent=False,
                max_tools_to_create=3
            ):
                if progress.step == "complete" and progress.details:
                    agent_id = progress.details.get("agent_id")
                    
            if agent_id:
                return await agent_crud.get(agent_id)
                
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            
        return None
    
    async def _execute_agent(self, agent: Agent, intent: ChatIntent, original_message: str) -> Dict[str, Any]:
        """Execute an agent with the original user message"""
        try:
            # Always send the original message in natural language
            # The agent will extract what it needs
            execution = AgentExecution(
                input=original_message,
                execution_options={}
            )
            
            # Execute
            result = await agent_executor.execute(agent, execution)
            
            if result.success:
                return {
                    "agent_output": result.output,
                    "execution_id": result.execution_id,
                    "tool_calls": len(result.tool_calls) if result.tool_calls else 0
                }
            else:
                return {
                    "error": result.error,
                    "execution_id": result.execution_id
                }
                
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            return {"error": str(e)}
    
    async def _execute_multiple_agents(self, agent_names: List[str], message: str) -> Dict[str, Any]:
        """Execute multiple agents in parallel and merge their responses"""
        # Get agents by name
        agents_to_execute = []
        for agent_name in agent_names:
            agents = await agent_crud.list(active_only=True)
            agent = next((a for a in agents if a.name == agent_name), None)
            if agent:
                agents_to_execute.append(agent)
            else:
                logger.warning(f"Agent '{agent_name}' not found or inactive")
        
        if not agents_to_execute:
            return {"error": "No valid agents found"}
        
        # Execute agents in parallel
        tasks = []
        for agent in agents_to_execute:
            task = self._execute_agent(agent, ChatIntent(
                intent="multi-agent query",
                response_type=ResponseType.AGENT,
                needs_agent=True,
                agent_type="multiple",
                parameters={},
                confidence=1.0
            ), message)
            tasks.append((agent.name, task))
        
        # Wait for all executions
        agent_responses = []
        for agent_name, task in tasks:
            try:
                result = await task
                agent_responses.append({
                    "agent_name": agent_name,
                    "output": result.get("agent_output", result.get("error", "No response")),
                    "success": "error" not in result
                })
            except Exception as e:
                logger.error(f"Error executing agent {agent_name}: {e}")
                agent_responses.append({
                    "agent_name": agent_name,
                    "output": f"Error: {str(e)}",
                    "success": False
                })
        
        # Merge responses
        return self._merge_agent_responses(agent_responses)
    
    def _merge_agent_responses(self, agent_responses: List[Dict]) -> Dict[str, Any]:
        """Merge responses from multiple agents into a single response"""
        merged_output = []
        
        for response in agent_responses:
            agent_name = response.get("agent_name")
            agent_output = response.get("output", "Pas de réponse")
            
            # Format each agent's response
            merged_output.append(f"Selon [{agent_name}]:\n<response>\n{agent_output}\n</response>")
        
        return {
            "agent_output": "\n\n".join(merged_output),
            "agents_used": [r["agent_name"] for r in agent_responses],
            "execution_mode": "manual_multi_agent",
            "individual_responses": agent_responses
        }
    
    async def _generate_direct_response(self, message: str, intent: ChatIntent) -> Dict[str, Any]:
        """Generate a direct response without using an agent"""
        prompt = load_prompt(
            "meta_chat/direct_response",
            message=message,
            intent=json.dumps(intent.model_dump())
        )
        
        response = await self._call_llm(prompt)
        
        return {
            "response": response,
            "intent": intent.intent,
            "parameters": intent.parameters
        }
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM API"""
        try:
            endpoint = self.llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            
            logger.info(f"Calling LLM with endpoint: {endpoint}, model: {self.llm_profile.model}")
            
            # Check if this is a Groq provider
            if "groq.com" in endpoint:
                return await self._call_groq_native(prompt)
            
            # Standard OpenAI-compatible API call
            headers = {
                "Authorization": f"Bearer {self.llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": self.llm_profile.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": self.llm_profile.max_tokens
            }
            
            # Add JSON mode if supported
            if self.llm_profile.mode == "json" and "json" in prompt.lower():
                payload["response_format"] = {"type": "json_object"}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    async def _call_groq_native(self, prompt: str) -> Optional[str]:
        """Call Groq using native client"""
        try:
            from groq import AsyncGroq
            
            logger.info("Using Groq native client")
            client = AsyncGroq(api_key=self.llm_profile.api_key)
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
            
            # For Groq with JSON mode, ensure "json" appears in messages
            if self.llm_profile.mode == "json" and "json" in prompt.lower():
                # Check if "json" is already in the messages
                has_json = any("json" in msg["content"].lower() for msg in messages)
                if not has_json:
                    messages[0]["content"] += " Always respond in valid JSON format."
            
            completion_params = {
                "model": self.llm_profile.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": self.llm_profile.max_tokens,
                "top_p": 1,
                "stream": False,
                "stop": None
            }
            
            # Add JSON mode if needed
            if self.llm_profile.mode == "json" and "json" in prompt.lower():
                completion_params["response_format"] = {"type": "json_object"}
            
            completion = await client.chat.completions.create(**completion_params)
            
            return completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Groq native call failed: {e}")
            return None
    
    async def _generate_html_response(
        self, 
        original_message: str, 
        response_data: Dict[str, Any], 
        intent: ChatIntent,
        agent_name: Optional[str] = None,
        custom_instruct: Optional[str] = None
    ) -> str:
        """Generate HTML/CSS/JS visualization for the response with validation"""
        
        # Prepare context for HTML generation
        context = {
            "original_question": original_message,
            "response_data": json.dumps(response_data, indent=2),
            "intent_type": intent.agent_type or "general",
            "agent_used": agent_name or "direct"
        }
        
        # Step 1: Create implementation plan
        logger.info("Creating HTML implementation plan...")
        planning_prompt = load_prompt(
            "meta_chat/html_planning",
            original_question=context["original_question"],
            response_data=context["response_data"],
            intent_type=context["intent_type"],
            custom_instruct=custom_instruct or ""
        )
        
        plan_response = await self._call_llm(planning_prompt)
        
        if not plan_response:
            logger.warning("No plan generated, falling back to direct generation")
            # Fallback to original approach
            prompt = load_prompt(
                "meta_chat/html_visualization",
                original_question=context["original_question"],
                response_data=context["response_data"],
                intent_type=context["intent_type"],
                custom_instruct=custom_instruct or ""
            )
            response = await self._call_llm(prompt)
        else:
            # Step 2: Generate HTML based on plan
            logger.info("Generating HTML based on implementation plan...")
            
            # Extract JSON plan
            try:
                plan_data = json.loads(plan_response)
                logger.info(f"Plan created with theme: {plan_data.get('visual_design', {}).get('theme', 'unknown')}")
            except:
                plan_data = plan_response
            
            implementation_prompt = load_prompt(
                "meta_chat/html_implementation",
                original_question=context["original_question"],
                response_data=context["response_data"],
                implementation_plan=json.dumps(plan_data, indent=2) if isinstance(plan_data, dict) else plan_response,
                custom_instruct=custom_instruct or ""
            )
            
            response = await self._call_llm(implementation_prompt)
        
        if not response:
            logger.error(f"LLM returned empty response for HTML generation. Context: {context['intent_type']}, Agent: {context['agent_used']}")
            # Try with a simpler fallback prompt if the main one fails
            fallback_prompt = f"""Create a simple HTML page that displays this information:

Question: {original_message}

Response: {response_data.get('agent_output', 'No response available')}

Make it clean and readable with basic CSS styling."""
            
            logger.info("Trying fallback prompt...")
            response = await self._call_llm(fallback_prompt)
            
            if not response:
                logger.error("Fallback prompt also failed")
                return "<html><body><h1>Error generating visualization</h1></body></html>"
        
        logger.info(f"LLM response length: {len(response)} characters")
        
        # Extract HTML from response
        html_content = self._extract_html(response)
        
        # Validation loop - for all HTML content
        max_attempts = 3
        for attempt in range(max_attempts):
            logger.info(f"Validating HTML (attempt {attempt + 1}/{max_attempts})")
            
            # Test the HTML
            validation_result = await html_validator.test_html(html_content)
            
            if validation_result['success']:
                logger.info("HTML validation passed!")
                break
            
            # If last attempt, return as is
            if attempt == max_attempts - 1:
                logger.warning(f"HTML validation failed after {max_attempts} attempts")
                break
            
            # Build correction prompt - simple and universal
            errors_text = html_validator.format_errors_for_llm(validation_result['errors'])
            correction_prompt = f"""Fix the errors in this HTML code:

ERRORS:
{errors_text}

HTML:
```html
{html_content}
```

Return only the corrected HTML code."""
            
            # Get corrected HTML
            correction_response = await self._call_llm(correction_prompt)
            if correction_response:
                html_content = self._extract_html(correction_response)
            else:
                break
        
        return html_content
    
    async def enhance_request(self, query: str, instructions: Optional[str] = None) -> Dict[str, Any]:
        """Enhance user query and instructions for better results"""
        try:
            # Load the enhancement prompt
            prompt = load_prompt(
                "meta_chat/enhance_request",
                query=query,
                instructions=instructions or ""
            )
            
            # Call LLM to enhance the request
            response = await self._call_llm(prompt)
            
            if not response:
                logger.error("No response from LLM for request enhancement")
                return {
                    "enhanced_query": query,
                    "enhanced_instructions": instructions or "",
                    "suggested_sources": [],
                    "query_type": "general"
                }
            
            try:
                # Parse the JSON response
                enhanced_data = json.loads(response)
                
                # Validate the response structure
                if not all(key in enhanced_data for key in ["enhanced_query", "enhanced_instructions"]):
                    raise ValueError("Missing required fields in enhancement response")
                
                return enhanced_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse enhancement response: {e}")
                # Return original values as fallback
                return {
                    "enhanced_query": query,
                    "enhanced_instructions": instructions or "",
                    "suggested_sources": [],
                    "query_type": "general"
                }
                
        except Exception as e:
            logger.error(f"Error enhancing request: {e}")
            # Return original values as fallback
            return {
                "enhanced_query": query,
                "enhanced_instructions": instructions or "",
                "suggested_sources": [],
                "query_type": "general"
            }
    
    def _extract_html(self, response: str) -> str:
        """Extract HTML content from LLM response"""
        import re
        
        # Check if wrapped in code blocks
        html_match = re.search(r'```html\s*([\s\S]*?)\s*```', response)
        if html_match:
            return html_match.group(1)
        elif response.strip().startswith('<!DOCTYPE'):
            return response
        else:
            # Fallback: wrap response in basic HTML
            return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Response</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
    </style>
</head>
<body>
    <div class="container">
        <pre>{response}</pre>
    </div>
</body>
</html>"""
    


# Factory function
async def create_meta_chat(llm_profile_name: str) -> MetaChatService:
    """Create a meta chat service with the specified LLM profile"""
    llm_profile = await llm_crud.get_by_name(llm_profile_name)
    if not llm_profile or not llm_profile.active:
        raise ValueError(f"LLM profile '{llm_profile_name}' not found or inactive")
    
    return MetaChatService(llm_profile)