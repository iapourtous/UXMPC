"""
Meta Chat Service

Routes user requests to appropriate agents or generates direct responses
"""

import logging
import json
import uuid
from typing import Optional, Dict, Any, List
import httpx

from app.models.meta_chat import (
    MetaChatRequest, MetaChatResponse, ChatIntent, ResponseType,
    QueryType, ClarificationQuestion, ClarificationQuestionnaire,
    ClarificationAnswers, MetaChatSession, QuestionType
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

# Temporary session storage (in production, use Redis or database)
SESSIONS: Dict[str, MetaChatSession] = {}


class MetaChatService:
    """Service for intelligent request routing"""
    
    def __init__(self, llm_profile: LLMProfile):
        self.llm_profile = llm_profile
        
    async def process_request(self, request: MetaChatRequest) -> MetaChatResponse:
        """Process a user request through the meta-chat system"""
        try:
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
        
        prompt = load_prompt(
            "meta_chat/html_visualization",
            original_question=context["original_question"],
            response_data=context["response_data"],
            intent_type=context["intent_type"],
            custom_instruct=custom_instruct or ""
        )

        # Generate initial HTML
        logger.info(f"Calling LLM for HTML generation... Prompt length: {len(prompt)} chars")
        response = await self._call_llm(prompt)
        
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
    
    async def generate_clarification_questionnaire(self, query: str, llm_profile: str) -> ClarificationQuestionnaire:
        """Generate a clarification questionnaire for a query"""
        try:
            # Analyze query type
            query_analysis = await self._analyze_query_type(query)
            logger.info(f"Query analysis: {query_analysis}")
            
            # Generate questions
            questions = await self._generate_clarification_questions(query, query_analysis)
            
            # Create session
            session_id = str(uuid.uuid4())
            session = MetaChatSession(
                session_id=session_id,
                original_query=query,
                llm_profile=llm_profile,
                query_type=QueryType[query_analysis["query_type"]],
                questions=questions,
                status="pending_clarification"
            )
            
            # Store session
            SESSIONS[session_id] = session
            
            # Return questionnaire
            return ClarificationQuestionnaire(
                session_id=session_id,
                query_type=session.query_type,
                questions=questions
            )
            
        except Exception as e:
            logger.error(f"Failed to generate questionnaire: {e}")
            raise
    
    async def process_with_clarifications(self, session_id: str, answers: Dict[str, Any]) -> MetaChatResponse:
        """Process a query using clarification answers"""
        try:
            # Retrieve session
            session = SESSIONS.get(session_id)
            if not session:
                return MetaChatResponse(
                    success=False,
                    error="Session not found or expired"
                )
            
            # Process clarifications to get enhanced message and auto instructions
            clarified = await self._process_clarifications(session, answers)
            
            # Update session
            session.answers = answers
            session.enhanced_message = clarified["enhanced_message"]
            session.auto_instruct = clarified["auto_instruct"]
            session.status = "processing"
            
            # Create a request with the enhanced message and auto-generated instructions
            request = MetaChatRequest(
                message=clarified["enhanced_message"],
                llm_profile=session.llm_profile,
                instruct=clarified["auto_instruct"]
            )
            
            # Process normally with the enhanced request
            response = await self.process_request(request)
            
            # Add enhanced query and instructions to metadata
            if response.success:
                response.metadata["enhanced_message"] = clarified["enhanced_message"]
                response.metadata["auto_instruct"] = clarified["auto_instruct"]
                response.metadata["original_query"] = session.original_query
                response.metadata["questionnaire_answers"] = answers
                
                # Add agent details if available
                if response.agent_used:
                    try:
                        agent = await agent_crud.get_by_name(response.agent_used)
                        if agent:
                            response.metadata["agent_details"] = {
                                "id": str(agent.id),
                                "name": agent.name,
                                "description": agent.description,
                                "mcp_services": agent.mcp_services
                            }
                    except Exception as e:
                        logger.error(f"Failed to get agent details: {e}")
            
            # Update session status
            session.status = "completed"
            
            # Clean up session after processing
            del SESSIONS[session_id]
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to process with clarifications: {e}")
            return MetaChatResponse(
                success=False,
                error=str(e)
            )
    
    async def _analyze_query_type(self, query: str) -> Dict[str, Any]:
        """Analyze query to determine its type and parameters"""
        prompt = load_prompt(
            "meta_chat/analyze_query_type",
            query=query
        )
        
        response = await self._call_llm(prompt)
        if response:
            try:
                data = json.loads(response)
                return data
            except Exception as e:
                logger.error(f"Failed to parse query type analysis: {e}")
                # Fallback
                return {
                    "query_type": "GENERAL",
                    "main_subject": query,
                    "detected_parameters": {},
                    "confidence": 0.5,
                    "reasoning": "Could not analyze query type"
                }
        
        raise ValueError("No response from LLM")
    
    async def _generate_clarification_questions(self, query: str, query_analysis: Dict[str, Any]) -> List[ClarificationQuestion]:
        """Generate contextual clarification questions based on query type"""
        prompt = load_prompt(
            "meta_chat/generate_clarification_questions",
            original_query=query,
            query_type=query_analysis["query_type"],
            detected_parameters=json.dumps(query_analysis["detected_parameters"])
        )
        
        logger.info(f"Calling LLM for questions generation with prompt length: {len(prompt)}")
        # Force JSON mode for questions generation
        json_prompt = prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON format as specified above."
        response = await self._call_llm_json_mode(json_prompt)
        
        if response:
            logger.info(f"LLM response for questions (length: {len(response)})")
            logger.info(f"First 100 chars: {response[:100]}")
            logger.info(f"Last 100 chars: {response[-100:]}")
            try:
                data = json.loads(response)
                logger.info(f"Parsed JSON successfully: {data}")
                questions = []
                for q in data.get("questions", []):
                    logger.info(f"Processing question: {q}")
                    try:
                        question = ClarificationQuestion(
                            id=q["id"],
                            question=q["question"],
                            type=QuestionType(q["type"]),
                            options=q.get("options"),
                            default=q.get("default"),
                            required=q.get("required", False),
                            context=q.get("context")
                        )
                        questions.append(question)
                        logger.info(f"Successfully created question: {q['id']}")
                    except Exception as qe:
                        logger.error(f"Failed to create question {q.get('id', 'unknown')}: {qe}")
                        logger.error(f"Question data: {q}")
                        raise qe
                logger.info(f"Generated {len(questions)} questions successfully")
                return questions
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON for questions: {e}")
                logger.error(f"Raw LLM response for questions: {response}")
                # Try to extract JSON from response if it's wrapped in text
                cleaned_response = self._extract_json_from_response(response)
                if cleaned_response:
                    try:
                        data = json.loads(cleaned_response)
                        logger.info(f"Successfully parsed cleaned JSON: {data}")
                        questions = []
                        for q in data.get("questions", []):
                            question = ClarificationQuestion(
                                id=q["id"],
                                question=q["question"],
                                type=QuestionType[q["type"]],
                                options=q.get("options"),
                                default=q.get("default"),
                                required=q.get("required", False),
                                context=q.get("context")
                            )
                            questions.append(question)
                        return questions
                    except Exception as e2:
                        logger.error(f"Even cleaned JSON failed: {e2}")
                # Fallback: return contextual questions based on query type
                return self._generate_fallback_questions(query_analysis["query_type"])
            except Exception as e:
                logger.error(f"Failed to parse clarification questions: {e}")
                logger.error(f"Raw response: {response}")
                return self._generate_fallback_questions(query_analysis["query_type"])
        
        logger.error("No response from LLM for questions generation")
        return self._generate_fallback_questions(query_analysis["query_type"])
    
    async def _process_clarifications(self, session: MetaChatSession, answers: Dict[str, Any]) -> Dict[str, str]:
        """Process clarification answers to generate enhanced message and auto instructions"""
        prompt = load_prompt(
            "meta_chat/process_clarifications",
            original_query=session.original_query,
            query_type=session.query_type.value,
            answers=json.dumps(answers)
        )
        
        response = await self._call_llm(prompt)
        if response:
            try:
                data = json.loads(response)
                return {
                    "enhanced_message": data["enhanced_message"],
                    "auto_instruct": data["auto_instruct"]
                }
            except Exception as e:
                logger.error(f"Failed to parse clarification processing: {e}")
                # Fallback
                return {
                    "enhanced_message": session.original_query,
                    "auto_instruct": "Create a clean, modern presentation of the information"
                }
        
        raise ValueError("No response from LLM")
    
    def _generate_fallback_questions(self, query_type: str) -> List[ClarificationQuestion]:
        """Generate fallback questions based on query type"""
        logger.info(f"Generating fallback questions for query type: {query_type}")
        
        if query_type == "CREATION":
            return [
                ClarificationQuestion(
                    id="complexity",
                    question="Quel niveau de complexité souhaitez-vous ?",
                    type=QuestionType.CHOICE,
                    options=["Basique", "Intermédiaire", "Avancé"],
                    default="Intermédiaire",
                    required=False,
                    context="Détermine les fonctionnalités et la sophistication"
                ),
                ClarificationQuestion(
                    id="style",
                    question="Quel style visuel préférez-vous ?",
                    type=QuestionType.CHOICE,
                    options=["Moderne", "Rétro", "Minimaliste", "Coloré"],
                    default="Moderne",
                    required=False,
                    context="Influence le design et les couleurs"
                ),
                ClarificationQuestion(
                    id="interactivity",
                    question="Souhaitez-vous des éléments interactifs ?",
                    type=QuestionType.BOOLEAN,
                    default=True,
                    required=False,
                    context="Ajoute des contrôles utilisateur"
                )
            ]
        elif query_type == "VISUALIZATION":
            return [
                ClarificationQuestion(
                    id="chart_type",
                    question="Quel type de visualisation préférez-vous ?",
                    type=QuestionType.CHOICE,
                    options=["Graphique", "Tableau", "Dashboard", "Carte"],
                    default="Graphique",
                    required=False,
                    context="Format de présentation des données"
                ),
                ClarificationQuestion(
                    id="color_scheme",
                    question="Quelle palette de couleurs souhaitez-vous ?",
                    type=QuestionType.CHOICE,
                    options=["Professionnelle", "Colorée", "Monochrome", "Personnalisée"],
                    default="Professionnelle",
                    required=False,
                    context="Thème visuel du graphique"
                )
            ]
        elif query_type == "INFORMATION":
            return [
                ClarificationQuestion(
                    id="detail_level",
                    question="Quel niveau de détail voulez-vous ?",
                    type=QuestionType.CHOICE,
                    options=["Résumé", "Détaillé", "Technique"],
                    default="Détaillé",
                    required=False,
                    context="Quantité d'informations affichées"
                ),
                ClarificationQuestion(
                    id="format",
                    question="Dans quel format souhaitez-vous la réponse ?",
                    type=QuestionType.CHOICE,
                    options=["Texte", "Visuel", "Interactif"],
                    default="Visuel",
                    required=False,
                    context="Mode de présentation"
                )
            ]
        else:  # ANALYSIS or GENERAL
            return [
                ClarificationQuestion(
                    id="presentation",
                    question="Comment souhaitez-vous que la réponse soit présentée ?",
                    type=QuestionType.CHOICE,
                    options=["Simple", "Détaillé", "Interactif"],
                    default="Détaillé",
                    required=False,
                    context="Format de présentation"
                ),
                ClarificationQuestion(
                    id="focus",
                    question="Sur quoi souhaitez-vous vous concentrer ?",
                    type=QuestionType.TEXT,
                    default="",
                    required=False,
                    context="Aspects spécifiques à mettre en avant"
                )
            ]
    
    def _extract_json_from_response(self, response: str) -> Optional[str]:
        """Extract JSON from LLM response that might be wrapped in text"""
        import re
        
        # Try to find JSON blocks in the response
        json_patterns = [
            r'```json\s*(.*?)\s*```',  # JSON in code blocks
            r'```\s*(.*?)\s*```',      # Any code blocks
            r'\{.*\}',                 # Raw JSON objects
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response, re.DOTALL)
            for match in matches:
                try:
                    # Test if it's valid JSON
                    json.loads(match)
                    return match
                except:
                    continue
        
        return None
    
    async def _call_llm_json_mode(self, prompt: str) -> Optional[str]:
        """Call LLM API with JSON mode forced"""
        try:
            endpoint = self.llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            
            logger.info(f"Calling LLM in JSON mode with endpoint: {endpoint}")
            
            # Check if this is a Groq provider
            if "groq.com" in endpoint:
                from groq import AsyncGroq
                
                client = AsyncGroq(api_key=self.llm_profile.api_key)
                
                messages = [
                    {"role": "system", "content": "You are a helpful assistant. Always respond in valid JSON format."},
                    {"role": "user", "content": prompt}
                ]
                
                completion_params = {
                    "model": self.llm_profile.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": self.llm_profile.max_tokens,
                    "response_format": {"type": "json_object"}
                }
                
                completion = await client.chat.completions.create(**completion_params)
                return completion.choices[0].message.content
            
            # Standard OpenAI-compatible API call with JSON mode
            headers = {
                "Authorization": f"Bearer {self.llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Always respond in valid JSON format."},
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": self.llm_profile.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": self.llm_profile.max_tokens,
                "response_format": {"type": "json_object"}
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                return result["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"JSON mode LLM call failed: {e}")
            return None


# Factory function
async def create_meta_chat(llm_profile_name: str) -> MetaChatService:
    """Create a meta chat service with the specified LLM profile"""
    llm_profile = await llm_crud.get_by_name(llm_profile_name)
    if not llm_profile or not llm_profile.active:
        raise ValueError(f"LLM profile '{llm_profile_name}' not found or inactive")
    
    return MetaChatService(llm_profile)