import json
import httpx
import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from app.models.agent import Agent, AgentExecution, AgentExecutionResponse
from app.services.llm_crud import llm_crud
from app.services.service_crud import service_crud
from app.core.database import get_database
from app.core.mongodb_logger import ServiceLogger

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executes agents by orchestrating LLM and MCP services"""
    
    async def execute(
        self, 
        agent: Agent, 
        execution_request: AgentExecution
    ) -> AgentExecutionResponse:
        """Execute an agent with the given input"""
        execution_id = str(uuid.uuid4())
        db = get_database()
        
        # Create logger for this execution
        agent_logger = ServiceLogger(db, f"agent_{agent.id}", f"Agent: {agent.name}", execution_id)
        
        try:
            await agent_logger.info(
                f"Agent execution started",
                agent=agent.name,
                input_type=type(execution_request.input).__name__
            )
            
            # Validate input against schema
            if not self._validate_input(execution_request.input, agent.input_schema):
                error = "Input does not match agent's input schema"
                await agent_logger.error(error)
                return AgentExecutionResponse(
                    success=False,
                    error=error,
                    execution_id=execution_id
                )
            
            # Get LLM profile
            llm_profile = await llm_crud.get_by_name(agent.llm_profile)
            if not llm_profile or not llm_profile.active:
                error = f"LLM profile '{agent.llm_profile}' not found or inactive"
                await agent_logger.error(error)
                return AgentExecutionResponse(
                    success=False,
                    error=error,
                    execution_id=execution_id
                )
            
            # Prepare tools from MCP services
            tools = await self._prepare_tools(agent.mcp_services, agent_logger, agent)
            
            # Load relevant context from memory if enabled
            memory_context = None
            if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
                memory_context = await self._load_memory_context(
                    agent=agent,
                    query=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                    agent_logger=agent_logger
                )
            
            # Build messages
            messages = self._build_messages(agent, execution_request, memory_context)
            
            # Execute with LLM
            result = await self._call_llm_with_tools(
                llm_profile=llm_profile,
                agent=agent,
                messages=messages,
                tools=tools,
                agent_logger=agent_logger,
                max_iterations=agent.max_iterations
            )
            
            # Validate output against schema
            if not self._validate_output(result["output"], agent.output_schema):
                error = "Output does not match agent's output schema"
                await agent_logger.error(error, output=result["output"])
                return AgentExecutionResponse(
                    success=False,
                    error=error,
                    execution_id=execution_id
                )
            
            await agent_logger.info(
                "Agent execution completed",
                tool_calls_count=len(result.get("tool_calls", [])),
                iterations=result.get("iterations", 1)
            )
            
            # Save conversation to memory if enabled
            if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
                await self._save_to_memory(
                    agent=agent,
                    execution_id=execution_id,
                    input_data=execution_request.input,
                    output_data=result["output"],
                    messages=messages,
                    agent_logger=agent_logger
                )
            
            # Update usage history for meta-chat selection
            await self._update_usage_history(
                agent=agent,
                query=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                response=result["output"] if isinstance(result["output"], str) else json.dumps(result["output"]),
                agent_logger=agent_logger
            )
            
            return AgentExecutionResponse(
                success=True,
                output=result["output"],
                execution_id=execution_id,
                tool_calls=result.get("tool_calls", []),
                iterations=result.get("iterations", 1),
                usage=result.get("usage", {})
            )
            
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            await agent_logger.error(error_msg, error=str(e))
            logger.error(error_msg, exc_info=True)
            
            return AgentExecutionResponse(
                success=False,
                error=error_msg,
                execution_id=execution_id
            )
    
    def _validate_input(self, input_data: Union[Dict[str, Any], str], schema: Union[Dict[str, Any], str]) -> bool:
        """Validate input against schema"""
        if schema == "text":
            return isinstance(input_data, str)
        elif isinstance(schema, dict):
            # Basic JSON schema validation
            if not isinstance(input_data, dict):
                return False
            # TODO: Implement full JSON schema validation
            return True
        return True
    
    def _validate_output(self, output_data: Any, schema: Union[Dict[str, Any], str]) -> bool:
        """Validate output against schema"""
        if schema == "text":
            return isinstance(output_data, str)
        elif isinstance(schema, dict):
            # Basic JSON schema validation
            if not isinstance(output_data, dict):
                return False
            # TODO: Implement full JSON schema validation
            return True
        return True
    
    async def _prepare_tools(self, service_names: List[str], agent_logger: ServiceLogger, agent: Agent) -> List[Dict[str, Any]]:
        """Prepare tool definitions from MCP services"""
        tools = []
        
        for service_name in service_names:
            service = await service_crud.get_by_name(service_name)
            if not service:
                await agent_logger.warning(f"Service '{service_name}' not found")
                continue
            
            if not service.active:
                await agent_logger.warning(f"Service '{service_name}' is not active")
                continue
            
            # Convert service to OpenAI tool format
            tool = {
                "type": "function",
                "function": {
                    "name": service.name,
                    "description": service.description or f"MCP service: {service.name}",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters
            for param in service.params:
                tool["function"]["parameters"]["properties"][param.name] = {
                    "type": param.type,
                    "description": param.description or param.name
                }
                if param.required:
                    tool["function"]["parameters"]["required"].append(param.name)
            
            tools.append(tool)
            await agent_logger.debug(f"Prepared tool: {service.name}")
        
        # Add memory tools if memory is enabled
        if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
            memory_config = getattr(agent, 'memory_config', {})
            if memory_config.get('active_memory', True):
                await agent_logger.info("Adding memory tools to agent")
                memory_tools = await self._create_memory_tools(agent)
                tools.extend(memory_tools)
        
        return tools
    
    def _build_messages(self, agent: Agent, execution_request: AgentExecution, memory_context: Optional[str] = None) -> List[Dict[str, str]]:
        """Build message list for LLM"""
        messages = []
        
        # Build enhanced system prompt with agent's identity
        system_content = ""
        
        # Add backstory if available
        if hasattr(agent, 'backstory') and agent.backstory:
            system_content += f"# Your Identity and Background\n{agent.backstory}\n\n"
        
        # Add objectives
        if hasattr(agent, 'objectives') and agent.objectives:
            system_content += "# Your Objectives\n"
            for obj in agent.objectives:
                system_content += f"- {obj}\n"
            system_content += "\n"
        
        # Add constraints
        if hasattr(agent, 'constraints') and agent.constraints:
            system_content += "# Your Constraints\n"
            for constraint in agent.constraints:
                system_content += f"- {constraint}\n"
            system_content += "\n"
        
        # Add reasoning strategy
        if hasattr(agent, 'reasoning_strategy') and agent.reasoning_strategy != "standard":
            if agent.reasoning_strategy == "chain-of-thought":
                system_content += "# Reasoning Approach\nUse chain-of-thought reasoning. Think step by step before providing your final answer.\n\n"
            elif agent.reasoning_strategy == "tree-of-thought":
                system_content += "# Reasoning Approach\nUse tree-of-thought reasoning. Consider multiple paths and evaluate them before choosing the best approach.\n\n"
        
        # Add personality traits
        if hasattr(agent, 'personality_traits') and agent.personality_traits:
            traits = agent.personality_traits
            if traits.get('tone') == 'professional':
                system_content += "Maintain a professional tone. "
            elif traits.get('tone') == 'friendly':
                system_content += "Be friendly and approachable. "
            
            if traits.get('verbosity') == 'concise':
                system_content += "Be concise and to the point. "
            elif traits.get('verbosity') == 'detailed':
                system_content += "Provide detailed and comprehensive responses. "
            
            if traits.get('empathy') == 'high':
                system_content += "Show empathy and understanding. "
            
            if traits.get('humor') == 'subtle':
                system_content += "You may use subtle humor when appropriate. "
            
            if system_content.endswith(". "):
                system_content += "\n\n"
        
        # Add memory context if available
        if memory_context:
            system_content += f"# Relevant Context from Memory\n{memory_context}\n\n"
        
        # Add memory tools instructions if enabled
        if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
            memory_config = getattr(agent, 'memory_config', {})
            if memory_config.get('active_memory', True):
                system_content += """# Memory Management
You have access to memory management tools:
- **memory_search**: Search your memory BEFORE using external tools to check if you already know the answer
- **memory_store**: Save important findings, user preferences, and key information for future use (importance 0.8+ for critical info)
- **memory_analyze**: Analyze your memory patterns to understand past interactions

Memory usage guidelines:
1. Always search your memory first before using external tools
2. Store important discoveries and user preferences with appropriate importance levels
3. Use descriptive content when storing memories for better future retrieval
4. Check memory_analyze periodically to understand your knowledge gaps

"""
        
        # Add original system prompt if provided
        if agent.system_prompt:
            system_content += agent.system_prompt
        
        # Add instruction about providing final answer
        system_content += "\n\nIMPORTANT: When you have gathered enough information to answer the user's question completely, provide your final answer WITHOUT making any more tool calls. The absence of tool calls in your response indicates that you have completed your task."
        
        # Only add system message if there's content
        if system_content.strip():
            messages.append({
                "role": "system",
                "content": system_content.strip()
            })
        
        # Add conversation history if provided
        if execution_request.conversation_history:
            messages.extend(execution_request.conversation_history)
        
        # Build user message
        user_content = ""
        if agent.pre_prompt:
            user_content = agent.pre_prompt + "\n\n"
        
        if isinstance(execution_request.input, str):
            user_content += execution_request.input
        else:
            user_content += json.dumps(execution_request.input)
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    async def _call_llm_with_tools(
        self,
        llm_profile: Any,
        agent: Agent,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        agent_logger: ServiceLogger,
        max_iterations: int
    ) -> Dict[str, Any]:
        """Call LLM with tools and handle tool execution"""
        endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
        
        # Check if this is a Groq provider
        if "groq.com" in endpoint:
            return await self._call_groq_with_tools(
                llm_profile, agent, messages, tools, agent_logger, max_iterations
            )
        
        # Standard OpenAI-compatible API
        headers = {
            "Authorization": f"Bearer {llm_profile.api_key}",
            "Content-Type": "application/json"
        }
        
        tool_calls_history = []
        iterations = 0
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            while iterations < max_iterations:
                iterations += 1
                await agent_logger.debug(f"LLM iteration {iterations}")
                
                # Prepare payload
                payload = {
                    "model": llm_profile.model,
                    "messages": messages,
                    "temperature": agent.temperature or llm_profile.temperature,
                    "max_tokens": agent.max_tokens or llm_profile.max_tokens
                }
                
                # Add tools if available
                if tools:  # Include tools on every call to allow continued tool use
                    payload["tools"] = tools
                    if agent.require_tool_use:
                        payload["tool_choice"] = "required"
                    else:
                        payload["tool_choice"] = "auto"
                
                # Call LLM
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                # Log the response for debugging
                await agent_logger.debug("LLM response structure", response_keys=list(result.keys()) if isinstance(result, dict) else type(result).__name__)
                
                # Check if response has expected structure
                if "choices" not in result:
                    await agent_logger.error("Unexpected LLM response format", response=result)
                    raise ValueError(f"LLM response missing 'choices' field. Keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                
                choice = result["choices"][0]
                message = choice["message"]
                
                # Update usage
                if "usage" in result:
                    usage = result["usage"]
                    total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
                    total_usage["total_tokens"] += usage.get("total_tokens", 0)
                
                # Add assistant message to history
                messages.append(message)
                
                # Check for tool calls
                if "tool_calls" in message and message["tool_calls"]:
                    # Execute tools
                    tool_results = await self._execute_tool_calls(
                        message["tool_calls"],
                        agent_logger,
                        agent
                    )
                    
                    # Add tool results to history
                    for tool_call, result in zip(message["tool_calls"], tool_results):
                        tool_calls_history.append({
                            "tool": tool_call["function"]["name"],
                            "arguments": tool_call["function"]["arguments"],
                            "result": result
                        })
                        
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(result),
                            "tool_call_id": tool_call["id"]
                        })
                    
                    # Continue conversation if not at max iterations
                    if iterations < max_iterations:
                        continue
                    else:
                        # Max iterations reached with tool calls pending
                        await agent_logger.warning(f"Max iterations ({max_iterations}) reached while still making tool calls")
                
                # No tool calls means the agent has its final answer
                output = message["content"]
                
                # Try to parse as JSON if output schema is not text
                if agent.output_schema != "text":
                    try:
                        output = json.loads(output)
                    except:
                        pass
                
                return {
                    "output": output,
                    "tool_calls": tool_calls_history,
                    "iterations": iterations,
                    "usage": total_usage
                }
        
        # Max iterations reached
        await agent_logger.warning(f"Max iterations ({max_iterations}) reached")
        return {
            "output": "Max iterations reached without completion",
            "tool_calls": tool_calls_history,
            "iterations": iterations,
            "usage": total_usage
        }
    
    async def _execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        agent_logger: ServiceLogger,
        agent: Optional[Agent] = None
    ) -> List[Dict[str, Any]]:
        """Execute tool calls by calling MCP services or memory tools"""
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = json.loads(tool_call["function"]["arguments"])
            
            await agent_logger.info(f"Executing tool: {tool_name}", arguments=tool_args)
            
            try:
                # Check if it's a memory tool
                if tool_name in ["memory_search", "memory_store", "memory_analyze"] and agent:
                    from app.core.agent_memory_tools import memory_search, memory_store, memory_analyze
                    
                    # Inject agent_id
                    tool_args["agent_id"] = agent.id
                    
                    # Call the appropriate memory tool
                    if tool_name == "memory_search":
                        result = await memory_search(**tool_args)
                    elif tool_name == "memory_store":
                        result = await memory_store(**tool_args)
                    elif tool_name == "memory_analyze":
                        result = await memory_analyze(**tool_args)
                    
                    results.append(result)
                    continue
                
                # Otherwise, call the MCP service
                service = await service_crud.get_by_name(tool_name)
                if not service:
                    result = {"error": f"Service '{tool_name}' not found"}
                else:
                    # Build URL
                    url = f"http://localhost:8000{service.route}"
                    
                    # Replace path parameters
                    for param_name, param_value in tool_args.items():
                        url = url.replace(f"{{{param_name}}}", str(param_value))
                    
                    # Make HTTP request
                    async with httpx.AsyncClient() as client:
                        if service.method == "GET":
                            query_params = {k: v for k, v in tool_args.items() if f"{{{k}}}" not in service.route}
                            response = await client.get(url, params=query_params)
                        elif service.method == "POST":
                            response = await client.post(url, json=tool_args)
                        else:
                            response = await client.request(service.method, url, json=tool_args)
                    
                    if response.status_code == 200:
                        result = response.json()
                    else:
                        result = {"error": f"Service returned {response.status_code}: {response.text}"}
                
            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                await agent_logger.error(error_msg, tool=tool_name)
                result = {"error": error_msg}
            
            results.append(result)
        
        return results
    
    async def _load_memory_context(
        self,
        agent: Agent,
        query: str,
        agent_logger: ServiceLogger
    ) -> Optional[str]:
        """Load relevant context from agent's memory"""
        try:
            from app.services.agent_memory_service import agent_memory_service
            
            # Search for relevant memories
            memories = await agent_memory_service.load_context(
                agent_id=agent.id,
                query=query,
                k=agent.memory_config.get('search_k', 5) if hasattr(agent, 'memory_config') else 5
            )
            
            if not memories:
                return None
            
            # Build context string
            context_parts = []
            for memory in memories:
                if memory.score > 0.7:  # Only include highly relevant memories
                    context_parts.append(f"[Previous conversation - Score: {memory.score:.2f}]\n{memory.memory.content}")
            
            if context_parts:
                context = "\n\n".join(context_parts)
                await agent_logger.info(f"Loaded {len(context_parts)} relevant memories")
                return context
            
            return None
            
        except Exception as e:
            await agent_logger.error(f"Failed to load memory context: {str(e)}")
            return None
    
    async def _create_memory_tools(self, agent: Agent) -> List[Dict[str, Any]]:
        """Create memory management tools for the agent"""
        from app.core.agent_memory_tools import MEMORY_TOOLS
        
        tools = []
        for tool_def in MEMORY_TOOLS:
            tool = {
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
            
            # Add parameters (skip agent_id as it will be injected)
            for param_name, param_config in tool_def["parameters"].items():
                if param_name != "agent_id":
                    prop = {
                        "type": param_config["type"],
                        "description": param_config.get("description", "")
                    }
                    
                    # Add enum if specified
                    if "enum" in param_config:
                        prop["enum"] = param_config["enum"]
                    
                    # Add default if specified
                    if "default" in param_config:
                        prop["default"] = param_config["default"]
                    
                    tool["function"]["parameters"]["properties"][param_name] = prop
                    
                    # Add to required if needed
                    if param_config.get("required", False):
                        tool["function"]["parameters"]["required"].append(param_name)
            
            tools.append(tool)
        
        return tools
    
    async def _save_to_memory(
        self,
        agent: Agent,
        execution_id: str,
        input_data: Union[str, Dict[str, Any]],
        output_data: Union[str, Dict[str, Any]],
        messages: List[Dict[str, str]],
        agent_logger: ServiceLogger
    ):
        """Save conversation to agent's memory"""
        try:
            from app.services.agent_memory_service import agent_memory_service
            
            # Extract conversation messages (skip system prompt)
            conversation = []
            for msg in messages:
                if msg["role"] != "system":
                    conversation.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Add the final assistant response if not already in messages
            if messages[-1]["role"] != "assistant":
                output_content = output_data if isinstance(output_data, str) else json.dumps(output_data)
                conversation.append({
                    "role": "assistant",
                    "content": output_content
                })
            
            # Save to memory
            await agent_memory_service.save_conversation(
                agent_id=agent.id,
                conversation_id=execution_id,
                messages=conversation,
                user_id=None,  # Could be extended to track user
                metadata={
                    "execution_id": execution_id,
                    "timestamp": str(uuid.uuid4())
                }
            )
            
            await agent_logger.info("Conversation saved to memory")
            
            # Extract preferences if any
            await agent_memory_service.extract_preferences(
                agent_id=agent.id,
                conversation=conversation
            )
            
        except Exception as e:
            await agent_logger.error(f"Failed to save to memory: {str(e)}")
            # Don't fail the execution if memory save fails
    
    async def _update_usage_history(
        self,
        agent: Agent,
        query: str,
        response: str,
        agent_logger: ServiceLogger
    ):
        """Update agent's usage history with the latest query/response"""
        try:
            # Ensure usage_history exists and is a list
            if not hasattr(agent, 'usage_history') or agent.usage_history is None:
                agent.usage_history = []
            
            # Add new entry
            new_entry = {
                "query": query[:200],  # Limit query length to avoid too much data
                "response": response[:500]  # Limit response length
            }
            
            # Add to beginning of list (most recent first)
            agent.usage_history.insert(0, new_entry)
            
            # Keep only the last 3 entries
            if len(agent.usage_history) > 3:
                agent.usage_history = agent.usage_history[:3]
            
            # Recalculate response embedding with the updated history
            from app.services.agent_embedding_service import agent_embedding_service
            new_embedding = agent_embedding_service.calculate_agent_embedding(agent.usage_history)
            agent.response_embedding = new_embedding
            
            # Save agent to database with both usage_history and response_embedding
            from app.services.agent_crud import agent_crud
            from app.models.agent import AgentUpdate
            update_data = AgentUpdate(
                usage_history=agent.usage_history,
                response_embedding=agent.response_embedding
            )
            await agent_crud.update(agent.id, update_data)
            
            await agent_logger.info(f"Updated usage history ({len(agent.usage_history)} entries) and response embedding")
            
        except Exception as e:
            await agent_logger.error(f"Failed to update usage history: {str(e)}")
            # Don't fail the execution if usage history update fails
    
    async def _call_groq_with_tools(
        self,
        llm_profile: Any,
        agent: Agent,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        agent_logger: ServiceLogger,
        max_iterations: int
    ) -> Dict[str, Any]:
        """Call Groq with tools using native client"""
        try:
            from groq import AsyncGroq
            
            client = AsyncGroq(api_key=llm_profile.api_key)
            
            tool_calls_history = []
            iterations = 0
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            
            while iterations < max_iterations:
                iterations += 1
                await agent_logger.debug(f"Groq LLM iteration {iterations}")
                
                # Prepare parameters
                completion_params = {
                    "model": llm_profile.model,
                    "messages": messages,
                    "temperature": agent.temperature or llm_profile.temperature,
                    "max_tokens": agent.max_tokens or llm_profile.max_tokens,
                    "top_p": 1,
                    "stream": False,
                    "stop": None
                }
                
                # Add tools if available
                if tools:
                    completion_params["tools"] = tools
                    if agent.require_tool_use:
                        completion_params["tool_choice"] = "required"
                    else:
                        completion_params["tool_choice"] = "auto"
                
                # Call Groq
                completion = await client.chat.completions.create(**completion_params)
                
                # Get the message
                message = completion.choices[0].message
                message_dict = {
                    "role": "assistant",
                    "content": message.content
                }
                
                # Handle tool calls if present
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    message_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in message.tool_calls
                    ]
                
                # Update usage if available
                if hasattr(completion, 'usage'):
                    usage = completion.usage
                    total_usage["prompt_tokens"] += getattr(usage, 'prompt_tokens', 0)
                    total_usage["completion_tokens"] += getattr(usage, 'completion_tokens', 0)
                    total_usage["total_tokens"] += getattr(usage, 'total_tokens', 0)
                
                # Add assistant message to history
                messages.append(message_dict)
                
                # Check for tool calls
                if "tool_calls" in message_dict and message_dict["tool_calls"]:
                    # Execute tools
                    tool_results = await self._execute_tool_calls(
                        message_dict["tool_calls"],
                        agent_logger,
                        agent
                    )
                    
                    # Add tool results to history
                    for tool_call, result in zip(message_dict["tool_calls"], tool_results):
                        tool_calls_history.append({
                            "tool": tool_call["function"]["name"],
                            "arguments": tool_call["function"]["arguments"],
                            "result": result
                        })
                        
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(result),
                            "tool_call_id": tool_call["id"]
                        })
                    
                    # Continue conversation if not at max iterations
                    if iterations < max_iterations:
                        continue
                    else:
                        await agent_logger.warning(f"Max iterations ({max_iterations}) reached while still making tool calls")
                
                # No tool calls means the agent has its final answer
                output = message.content
                
                # Try to parse as JSON if output schema is not text
                if agent.output_schema != "text":
                    try:
                        output = json.loads(output)
                    except:
                        pass
                
                return {
                    "output": output,
                    "tool_calls": tool_calls_history,
                    "iterations": iterations,
                    "usage": total_usage
                }
        
        except Exception as e:
            await agent_logger.error(f"Groq call with tools failed: {e}")
            raise
        
        # Max iterations reached
        await agent_logger.warning(f"Max iterations ({max_iterations}) reached")
        return {
            "output": "Max iterations reached without completion",
            "tool_calls": tool_calls_history,
            "iterations": iterations,
            "usage": total_usage
        }


# Singleton instance
agent_executor = AgentExecutor()