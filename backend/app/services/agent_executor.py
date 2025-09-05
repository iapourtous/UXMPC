import json
import logging
import uuid
import asyncio
import os
import copy
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, AsyncGenerator
from app.models.agent import (
    Agent, AgentExecution, AgentExecutionResponse,
    AgentExecutionProgress, ExecutionStep
)
from app.services.llm_crud import llm_crud
from app.core.database import get_database
from app.services.unified_logger import UnifiedLogger
from app.services.conversation_crud import conversation_crud
from app.models.conversation import MessageCreate, ConversationCreate
from app.services.conversation_manager import ConversationManager
from app.services.message_builder import MessageBuilder
from app.services.tool_manager import ToolManager
from app.services.conversation_compactor import conversation_compactor
from app.services.settings_crud import settings_crud
from app.core.llm_client import llm_client
from app.core.json_extractor import extract_json_from_text

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executes agents by orchestrating LLM and MCP services"""
    
    def __init__(self):
        """Initialize the agent executor, message builder and tool manager"""
        self.message_builder = MessageBuilder()
        self.tool_manager = ToolManager()
    
    def _create_logger(self, agent: Agent, execution_id: str) -> UnifiedLogger:
        """Create a unified logger for agent execution"""
        db = get_database()
        return UnifiedLogger(f"agent_{agent.id}", f"Agent: {agent.name}", execution_id, db=db)
    
    async def execute(
        self, 
        agent: Agent, 
        execution_request: AgentExecution
    ) -> AgentExecutionResponse:
        """Execute an agent with the given input"""
        execution_id = str(uuid.uuid4())
        
        # Create unified logger for this execution
        logger = self._create_logger(agent, execution_id)
        
        # Handle conversation persistence
        conversation_manager = ConversationManager(logger)
        conversation_id = None
        
        if execution_request.save_conversation:
            conversation = await conversation_manager.get_or_create_conversation(
                execution_id=execution_id,
                conversation_id=execution_request.conversation_id,
                create_new=False
            )
            conversation_id = conversation.id if conversation else None
        
        try:
            # Log execution start
            await logger.log_agent_execution(
                agent_id=agent.id,
                agent_name=agent.name,
                input_data=execution_request.input,
                execution_type="standard",
                conversation_id=conversation_id
            )
            
            # Save user message to conversation
            if conversation_id and execution_request.save_conversation:
                await conversation_manager.save_user_message(
                    conversation_id=conversation_id,
                    content=execution_request.input,
                    execution_id=execution_id
                )
            
            # Validate input against schema
            if not self._validate_input(execution_request.input, agent.input_schema):
                error = "Input does not match agent's input schema"
                await logger.error(error)
                return AgentExecutionResponse(
                    success=False,
                    error=error,
                    execution_id=execution_id,
                    conversation_id=conversation_id
                )
            
            # Get LLM profile
            llm_profile = await llm_crud.get_by_name(agent.llm_profile)
            if not llm_profile or not llm_profile.active:
                error = f"LLM profile '{agent.llm_profile}' not found or inactive"
                await logger.error(error)
                return AgentExecutionResponse(
                    success=False,
                    error=error,
                    execution_id=execution_id,
                    conversation_id=conversation_id
                )
            
            # Load relevant context from memory if enabled (do this first)
            memory_context = None
            if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
                memory_context = await self._load_memory_context(
                    agent=agent,
                    query=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                    logger=logger
                )
            
            # Load conversation history if conversation_id is provided
            loaded_history = []
            if conversation_id:
                loaded_history = await conversation_manager.load_conversation_history(conversation_id)
            
            # If no history was provided but we loaded from conversation, use that
            if loaded_history and not execution_request.conversation_history:
                execution_request.conversation_history = loaded_history
            
            # Prepare tools from MCP services (BEFORE building messages)
            tools = await self.tool_manager.prepare_tools(agent.mcp_services, agent, logger)
            
            # Build messages with tools context
            messages = self.message_builder.build_messages(agent, execution_request, memory_context, tools)
            
            # Apply conversation compaction if enabled
            messages_for_agent = messages
            compaction_applied = False
            
            # Get global settings for compaction
            global_settings = await settings_crud.get_or_create()
            
            # Check if we should compact the conversation
            # Check compaction quietly
            await logger.debug("Checking conversation compaction")
            
            if global_settings.compaction_settings.enabled and execution_request.conversation_history:
                # Prepare full message list including history for compaction check
                full_messages = []
                if execution_request.conversation_history:
                    full_messages.extend(execution_request.conversation_history)
                # Add current user message
                if messages and messages[-1]["role"] == "user":
                    full_messages.append(messages[-1])
                
                # Attempt compaction
                compacted_messages, was_compacted = await conversation_compactor.compact_conversation(
                    messages=full_messages,
                    user_context=global_settings.user_context,
                    settings=global_settings,
                    current_user_message=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input)
                )
                
                if was_compacted:
                    # Rebuild messages with compacted version
                    # Keep system messages from agent configuration (backstory, objectives, etc.)
                    agent_system_messages = [msg for msg in messages if msg["role"] == "system" and "User Context:" not in msg["content"] and "Previous Conversation Summary:" not in msg["content"]]
                    
                    # The compacted_messages already include user context and summary, so combine them properly
                    messages_for_agent = agent_system_messages + compacted_messages
                    compaction_applied = True
                    
                    # Log compaction quietly
                    await logger.debug(f"Compacted: {len(full_messages)} -> {len(messages_for_agent)} messages")
                    
                    # Message structure logging removed for cleaner output
                elif global_settings.user_context:
                    # No compaction but add user context if available
                    user_context_msg = {
                        "role": "system",
                        "content": f"User Context: {global_settings.user_context}"
                    }
                    # Insert user context after agent system messages
                    system_msg_count = sum(1 for msg in messages if msg["role"] == "system")
                    messages_for_agent = messages[:system_msg_count] + [user_context_msg] + messages[system_msg_count:]
            elif global_settings.user_context and not execution_request.conversation_history:
                # No history but add user context if available
                user_context_msg = {
                    "role": "system",
                    "content": f"User Context: {global_settings.user_context}"
                }
                # Insert user context after agent system messages
                system_msg_count = sum(1 for msg in messages if msg["role"] == "system")
                messages_for_agent = messages[:system_msg_count] + [user_context_msg] + messages[system_msg_count:]
            
            # Check if agent uses chain-of-thought reasoning
            if (hasattr(agent, 'reasoning_strategy') and 
                agent.reasoning_strategy == "chain-of-thought"):
                
                # Log CoT usage quietly
                await logger.debug("Using Adaptive Chain of Thought reasoning")
                await logger.info(
                    "COT mode activated for agent",
                    agent_id=agent.id,
                    conversation_length=len(messages)
                )
                
                # Import adaptive CoT engine
                from app.services.cot_adaptive_engine import adaptive_cot_engine
                
                # Prepare context for CoT
                cot_context = {
                    "agent_id": str(agent.id),  # Add agent_id for memory storage
                    "conversation_id": execution_request.conversation_id if hasattr(execution_request, 'conversation_id') else None,
                    "memory_context": memory_context,
                    "available_tools": [tool["function"]["name"] for tool in tools] if tools else [],
                    "conversation_history": execution_request.conversation_history or [],
                    "user_context": global_settings.user_context if 'global_settings' in locals() else None
                }
                
                # Extract agent configuration for 7D
                agent_config = {
                    "name": agent.name,
                    "backstory": getattr(agent, 'backstory', ''),
                    "objectives": getattr(agent, 'objectives', []),
                    "constraints": getattr(agent, 'constraints', []),
                    "personality": getattr(agent, 'personality_traits', {}),
                    "reasoning": {
                        "strategies": [agent.reasoning_strategy] if hasattr(agent, 'reasoning_strategy') else ['logical']
                    },
                    "decision_policies": getattr(agent, 'decision_policies', {})
                }
                
                # Create tool executor function for CoT
                async def cot_tool_executor(tool_name: str, arguments: Dict[str, Any]) -> Any:
                    """Execute a tool and return its result"""
                    try:
                        # Check if it's a memory tool FIRST
                        if tool_name in ["memory_search", "memory_store", "memory_analyze"]:
                            from app.core.agent_memory_tools import memory_search, memory_store, memory_analyze
                            
                            # Inject agent_id
                            arguments["agent_id"] = agent.id
                            
                            # Call the appropriate memory tool
                            if tool_name == "memory_search":
                                result = await memory_search(**arguments)
                            elif tool_name == "memory_store":
                                result = await memory_store(**arguments)
                            elif tool_name == "memory_analyze":
                                result = await memory_analyze(**arguments)
                            else:
                                result = f"Unknown memory tool: {tool_name}"
                            
                            return result
                        
                        # Check if it's an external MCP tool
                        if tool_name.startswith("mcp_") and hasattr(agent, 'mcp_connections'):
                            from app.services.mcp_client_service import mcp_client_service
                            # Extract connection_id and actual tool name
                            parts = tool_name.split("_", 2)
                            if len(parts) >= 3:
                                connection_id = parts[1]
                                actual_tool = "_".join(parts[2:])
                                result = await mcp_client_service.execute_tool(
                                    connection_id, actual_tool, arguments
                                )
                                return result
                        
                        # Check if it's a registered MCP tool
                        from app.core.mcp_manager import mcp_manager
                        if tool_name in mcp_manager.tools:
                            # Execute via the stored tool function
                            result = await mcp_manager.tools[tool_name](**arguments)
                            return result
                        
                        # Otherwise find and execute as service
                        service = await service_crud.get_by_name(tool_name)
                        if not service:
                            await logger.warning(f"Tool {tool_name} not found in any category")
                            return f"Tool {tool_name} not found"
                        
                        # Execute the service directly
                        result = await mcp_manager._execute_service(service, arguments)
                        return result
                    except Exception as e:
                        await logger.error(f"Tool execution error for {tool_name}: {str(e)}", exc_info=True)
                        return f"Error executing {tool_name}: {str(e)}"
                
                # Execute adaptive CoT with tools
                cot_result = await adaptive_cot_engine.execute(
                    problem=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                    context=cot_context,
                    llm_profile=llm_profile,
                    conversation_history=messages_for_agent,
                    agent_config=agent_config,
                    tools=tools,  # Pass the tools
                    tool_executor=cot_tool_executor,  # Pass the executor
                    execution_id=execution_id
                )
                
                if cot_result.success:
                    # Log CoT completion quietly
                    await logger.debug(f"CoT completed: {cot_result.total_iterations} iterations")
                    
                    await logger.info(
                        "COT execution completed",
                        iterations=cot_result.total_iterations,
                        tool_calls=len(cot_result.all_tool_results),
                        success=cot_result.success,
                        convergence_reason=cot_result.convergence_reason
                    )
                    
                    # Format result to match expected structure
                    # Extract all tool calls from iterations
                    all_tool_calls = []
                    for iteration in cot_result.iterations:
                        for i, tool_call in enumerate(iteration.tool_calls):
                            # Find corresponding result
                            result = None
                            if i < len(iteration.tool_results):
                                tool_result = iteration.tool_results[i]
                                result = tool_result.result if tool_result.success else tool_result.error
                            
                            all_tool_calls.append({
                                "tool": tool_call.tool_name,
                                "arguments": json.dumps(tool_call.arguments) if tool_call.arguments else "{}",
                                "result": result,
                                "iteration": iteration.iteration_number
                            })
                    
                    result = {
                        "output": cot_result.final_answer,
                        "tool_calls": all_tool_calls,  # Include all tool calls made
                        "iterations": cot_result.total_iterations,
                        "usage": {},  # Could be enhanced to track token usage
                        "reasoning_chain": [
                            {
                                "iteration": it.iteration_number,
                                "thought": it.thought,
                                "tools_used": [tc.tool_name for tc in it.tool_calls],
                                "confidence": it.confidence
                            }
                            for it in cot_result.iterations
                        ]
                    }
                else:
                    # Fallback to standard execution if CoT fails
                    await logger.warning("CoT failed, falling back to standard execution")
                    result = await self._call_llm_with_tools(
                        llm_profile=llm_profile,
                        agent=agent,
                        messages=messages_for_agent,
                        tools=tools,
                        logger=logger,
                        max_iterations=agent.max_iterations
                    )
            else:
                # Standard execution without CoT
                result = await self._call_llm_with_tools(
                    llm_profile=llm_profile,
                    agent=agent,
                    messages=messages_for_agent,
                    tools=tools,
                    logger=logger,
                    max_iterations=agent.max_iterations
                )
            
            # Validate output against schema
            if not self._validate_output(result["output"], agent.output_schema):
                error = "Output does not match agent's output schema"
                await logger.error(error, output=result["output"])
                return AgentExecutionResponse(
                    success=False,
                    error=error,
                    execution_id=execution_id,
                    conversation_id=conversation_id
                )
            
            # Log completion quietly
            await logger.debug("Agent execution completed")
            
            # Save assistant response to conversation
            if conversation_id and execution_request.save_conversation:
                await conversation_manager.save_assistant_message(
                    conversation_id=conversation_id,
                    content=result["output"],
                    agent_id=agent.id,
                    execution_id=execution_id
                )
            
            # Save conversation to memory if enabled
            if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
                await self._save_to_memory(
                    agent=agent,
                    execution_id=execution_id,
                    input_data=execution_request.input,
                    output_data=result["output"],
                    messages=messages,
                    logger=logger
                )
            
            # Update usage history for agent selection
            await self._update_usage_history(
                agent=agent,
                query=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                response=result["output"] if isinstance(result["output"], str) else json.dumps(result["output"]),
                logger=logger
            )
            
            return AgentExecutionResponse(
                success=True,
                output=result["output"],
                execution_id=execution_id,
                tool_calls=result.get("tool_calls", []),
                iterations=result.get("iterations", 1),
                usage=result.get("usage", {}),
                conversation_id=conversation_id,
                reasoning_chain=result.get("reasoning_chain")
            )
            
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            await logger.error(error_msg, error=str(e), exc_info=True)
            
            # Save error to conversation if applicable
            if conversation_id and execution_request.save_conversation:
                await conversation_manager.save_assistant_message(
                    conversation_id=conversation_id,
                    content="I encountered an error while processing your request.",
                    agent_id=agent.id,
                    execution_id=execution_id
                )
            
            return AgentExecutionResponse(
                success=False,
                error=error_msg,
                execution_id=execution_id,
                conversation_id=conversation_id
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
    
    
    
    async def _call_llm_with_tools(
        self,
        llm_profile: Any,
        agent: Agent,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        logger: UnifiedLogger,
        max_iterations: int
    ) -> Dict[str, Any]:
        """Call LLM with tools using centralized client"""
        tool_calls_history = []
        iterations = 0
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        # Force text mode for compatibility with tools
        text_mode_profile = copy.copy(llm_profile)
        text_mode_profile.mode = "text"
        
        while iterations < max_iterations:
            iterations += 1
            await logger.debug(f"LLM iteration {iterations}")
            
            try:
                # Use centralized client for LLM call with text mode profile
                response = await llm_client.call_with_tools_iteration(
                    llm_profile=text_mode_profile,
                    messages=messages,
                    tools=tools,
                    temperature=agent.temperature or text_mode_profile.temperature,
                    max_tokens=agent.max_tokens or text_mode_profile.max_tokens,
                    require_tool_use=agent.require_tool_use if tools else False,
                    timeout=120.0
                )
                
                # Log the response for debugging
                await logger.debug("LLM response structure", response_keys=list(response.keys()) if isinstance(response, dict) else type(response).__name__)
                
                # Check if response has expected structure
                if "choices" not in response:
                    await logger.error("Unexpected LLM response format", response=response)
                    raise ValueError(f"LLM response missing 'choices' field. Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
                
                choice = response["choices"][0]
                message = choice["message"]
                
                # Handle case where model returns only tool_calls without content (like in CoT)
                if not message.get("content") and message.get("tool_calls"):
                    await logger.info("Model returned tool_calls without content, creating minimal content")
                    # Create a minimal content to indicate tool usage
                    message["content"] = "I'm using tools to gather the information needed to answer your question."
                elif not message.get("content") and not message.get("tool_calls"):
                    await logger.warning("Model returned neither content nor tool_calls, creating default response")
                    # Create a default response to continue
                    message["content"] = "Let me process your request."
                
                # Update usage
                if "usage" in response:
                    usage = response["usage"]
                    total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
                    total_usage["total_tokens"] += usage.get("total_tokens", 0)
                
                # Add assistant message to history
                messages.append(message)
                
                # Check for tool calls
                if "tool_calls" in message and message["tool_calls"]:
                    # Execute tools
                    tool_results = await self.tool_manager.execute_tool_calls(
                        message["tool_calls"],
                        logger,
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
                        await logger.warning(f"Max iterations ({max_iterations}) reached while still making tool calls")
                
                # No tool calls means the agent has its final answer
                output = message["content"]
                
                # Try to parse as JSON if output schema is not text
                if agent.output_schema and agent.output_schema != "text":
                    # Use our JSON extractor for robust parsing
                    extracted = extract_json_from_text(output)
                    if extracted:
                        output = extracted
                        await logger.debug("Successfully extracted JSON from text response")
                    else:
                        # Fallback to direct parsing
                        try:
                            output = json.loads(output)
                        except:
                            # Keep as text if parsing fails
                            await logger.warning(
                                "Could not parse output as JSON despite non-text schema",
                                schema=agent.output_schema
                            )
                            pass
                
                return {
                    "output": output,
                    "tool_calls": tool_calls_history,
                    "iterations": iterations,
                    "usage": total_usage
                }
                
            except Exception as e:
                await logger.error(f"Error in LLM iteration {iterations}: {str(e)}")
                # If we have partial results, return them
                if iterations > 1 and tool_calls_history:
                    return {
                        "output": f"Partial results after {iterations-1} iterations. Error: {str(e)}",
                        "tool_calls": tool_calls_history,
                        "iterations": iterations,
                        "usage": total_usage
                    }
                raise
        
        # Max iterations reached
        await logger.warning(f"Max iterations ({max_iterations}) reached")
        return {
            "output": "Max iterations reached without completion",
            "tool_calls": tool_calls_history,
            "iterations": iterations,
            "usage": total_usage
        }
    
    
    async def _load_memory_context(
        self,
        agent: Agent,
        query: str,
        logger: Optional[UnifiedLogger]
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
                if logger:
                    await logger.info(f"Loaded {len(context_parts)} memories")
                return context
            
            return None
            
        except Exception as e:
            if logger:
                await logger.error(f"Failed to load memory context: {str(e)}")
            return None
    
    
    async def _save_to_memory(
        self,
        agent: Agent,
        execution_id: str,
        input_data: Union[str, Dict[str, Any]],
        output_data: Union[str, Dict[str, Any]],
        messages: List[Dict[str, str]],
        logger: UnifiedLogger
    ):
        """Save conversation to agent's memory"""
        try:
            from app.services.agent_memory_service import agent_memory_service
            
            # Only save the NEW messages from this execution to avoid duplicates
            # We need to identify which messages are new vs. historical
            new_messages = []
            
            # The user input for this execution
            user_content = input_data if isinstance(input_data, str) else json.dumps(input_data)
            new_messages.append({
                "role": "user",
                "content": user_content
            })
            
            # The assistant response for this execution
            output_content = output_data if isinstance(output_data, str) else json.dumps(output_data)
            new_messages.append({
                "role": "assistant", 
                "content": output_content
            })
            
            # Save only the new messages to memory
            await agent_memory_service.save_conversation(
                agent_id=agent.id,
                conversation_id=execution_id,
                messages=new_messages,
                user_id=None,  # Could be extended to track user
                metadata={
                    "execution_id": execution_id,
                    "timestamp": str(uuid.uuid4())
                }
            )
            
            await logger.debug("Conversation saved")
            
            # Extract preferences from the new messages only
            await agent_memory_service.extract_preferences(
                agent_id=agent.id,
                conversation=new_messages
            )
            
        except Exception as e:
            await logger.error(f"Failed to save to memory: {str(e)}")
            # Don't fail the execution if memory save fails
    
    async def _update_usage_history(
        self,
        agent: Agent,
        query: str,
        response: str,
        logger: UnifiedLogger
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
            
            await logger.debug("Updated usage history")
            
        except Exception as e:
            await logger.error(f"Failed to update usage history: {str(e)}")
            # Don't fail the execution if usage history update fails
    
    async def execute_with_progress(
        self, 
        agent: Agent, 
        execution_request: AgentExecution
    ) -> AsyncGenerator[AgentExecutionProgress, None]:
        """Execute an agent with streaming progress updates"""
        execution_id = str(uuid.uuid4())
        db = get_database()
        logger = self._create_logger(agent, execution_id)
        
        try:
            # Initial progress
            yield AgentExecutionProgress(
                step=ExecutionStep.STARTING,
                message=f"Starting execution for agent '{agent.name}'",
                progress=5
            )
            
            await logger.info(
                f"Agent execution started (streaming)",
                agent=agent.name,
                input_type=type(execution_request.input).__name__
            )
            
            # Validate input
            yield AgentExecutionProgress(
                step=ExecutionStep.VALIDATING,
                message="Validating input against schema",
                progress=10
            )
            
            if not self._validate_input(execution_request.input, agent.input_schema):
                error = "Input does not match agent's input schema"
                await logger.error(error)
                yield AgentExecutionProgress(
                    step=ExecutionStep.ERROR,
                    message="Validation failed",
                    progress=0,
                    error_detail=error
                )
                return
            
            # Get LLM profile
            llm_profile = await llm_crud.get_by_name(agent.llm_profile)
            if not llm_profile or not llm_profile.active:
                error = f"LLM profile '{agent.llm_profile}' not found or inactive"
                await logger.error(error)
                yield AgentExecutionProgress(
                    step=ExecutionStep.ERROR,
                    message="LLM profile error",
                    progress=0,
                    error_detail=error
                )
                return
            
            # Prepare tools
            yield AgentExecutionProgress(
                step=ExecutionStep.PREPARING_TOOLS,
                message=f"Preparing {len(agent.mcp_services)} tools",
                progress=20
            )
            
            tools = await self.tool_manager.prepare_tools(agent.mcp_services, agent, logger)
            
            # Load memory context
            memory_context = None
            if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
                yield AgentExecutionProgress(
                    step=ExecutionStep.LOADING_MEMORY,
                    message="Loading memory context",
                    progress=25
                )
                memory_context = await self._load_memory_context(
                    agent=agent,
                    query=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                    logger=logger
                )
            
            # Build messages with tools context
            messages = self.message_builder.build_messages(agent, execution_request, memory_context, tools)
            
            # Execute with LLM iterations
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            tool_calls_history = []
            iterations = 0
            max_iterations = agent.max_iterations
            
            # Main execution loop
            progress_base = 30
            progress_per_iteration = 50 / max_iterations  # Reserve 50% for iterations
            
            while iterations < max_iterations:
                iterations += 1
                current_progress = int(progress_base + (iterations - 1) * progress_per_iteration)
                
                yield AgentExecutionProgress(
                    step=ExecutionStep.CALLING_LLM,
                    message=f"Calling LLM (iteration {iterations}/{max_iterations})",
                    progress=current_progress,
                    iteration=iterations,
                    total_iterations=max_iterations
                )
                
                # Call LLM with tools
                result = await self._call_llm_with_streaming_updates(
                    llm_profile=llm_profile,
                    agent=agent,
                    messages=messages,
                    tools=tools,
                    logger=logger,
                    current_iteration=iterations,
                    progress_callback=lambda p: self._create_progress_update(p, current_progress, progress_per_iteration)
                )
                
                # Update usage
                if "usage" in result:
                    for key in total_usage:
                        total_usage[key] += result["usage"].get(key, 0)
                
                # Process tool calls
                if result.get("tool_calls"):
                    for tool_call in result["tool_calls"]:
                        tool_name = tool_call["function"]["name"]
                        yield AgentExecutionProgress(
                            step=ExecutionStep.EXECUTING_TOOL,
                            message=f"Executing tool: {tool_name}",
                            progress=current_progress + int(progress_per_iteration * 0.5),
                            iteration=iterations,
                            total_iterations=max_iterations,
                            tool_call=tool_call
                        )
                        
                        # Execute tool calls
                        tool_results = await self.tool_manager.execute_tool_calls(
                            [tool_call], logger, agent
                        )
                        
                        tool_calls_history.extend(result["tool_calls"])
                        
                        # Add tool results to messages
                        for i, tool_result in enumerate(tool_results):
                            yield AgentExecutionProgress(
                                step=ExecutionStep.PROCESSING_RESULT,
                                message=f"Processing result from {tool_name}",
                                progress=current_progress + int(progress_per_iteration * 0.8),
                                iteration=iterations,
                                total_iterations=max_iterations,
                                tool_result=tool_result
                            )
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": result["tool_calls"][i]["id"],
                                "content": json.dumps(tool_result)
                            })
                
                # Add assistant response to messages
                messages.append({"role": "assistant", "content": result["message"]})
                
                # Check if we have a final answer
                if not result.get("tool_calls") and result.get("message"):
                    # We have a final response
                    output = result["message"]
                    
                    # Save to memory
                    if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
                        yield AgentExecutionProgress(
                            step=ExecutionStep.SAVING_MEMORY,
                            message="Saving conversation to memory",
                            progress=85
                        )
                        await self._save_to_memory(
                            agent, execution_id, execution_request.input,
                            output, messages, logger
                        )
                    
                    # Validate output
                    if not self._validate_output(output, agent.output_schema):
                        error = "Output does not match agent's output schema"
                        await logger.error(error, output=output)
                        yield AgentExecutionProgress(
                            step=ExecutionStep.ERROR,
                            message="Output validation failed",
                            progress=0,
                            error_detail=error
                        )
                        return
                    
                    await logger.info(
                        "Agent execution completed",
                        tool_calls_count=len(tool_calls_history),
                        iterations=iterations
                    )
                    
                    # Final progress
                    yield AgentExecutionProgress(
                        step=ExecutionStep.COMPLETE,
                        message="Execution completed successfully",
                        progress=100,
                        partial_output=output,
                        iteration=iterations,
                        total_iterations=max_iterations
                    )
                    return
                
                # Send heartbeat to keep connection alive
                yield AgentExecutionProgress(
                    step=ExecutionStep.HEARTBEAT,
                    message="Processing...",
                    progress=current_progress + int(progress_per_iteration * 0.9),
                    iteration=iterations,
                    total_iterations=max_iterations
                )
            
            # Max iterations reached
            await logger.warning(
                "Max iterations reached without final answer",
                iterations=iterations
            )
            
            yield AgentExecutionProgress(
                step=ExecutionStep.COMPLETE,
                message="Max iterations reached",
                progress=100,
                partial_output="Max iterations reached without completion",
                iteration=iterations,
                total_iterations=max_iterations
            )
            
        except Exception as e:
            await logger.error(f"Agent execution failed: {str(e)}")
            yield AgentExecutionProgress(
                step=ExecutionStep.ERROR,
                message="Execution failed",
                progress=0,
                error_detail=str(e)
            )
    
    def _create_progress_update(self, internal_progress: Dict, base_progress: int, range: float) -> int:
        """Convert internal progress to overall progress"""
        internal_percent = internal_progress.get("percent", 0)
        return int(base_progress + (internal_percent / 100) * range)
    
    async def _call_llm_with_streaming_updates(
        self,
        llm_profile,
        agent: Agent,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        logger: UnifiedLogger
    ) -> Dict[str, Any]:
        """Call LLM with tools (wrapper for existing method)"""
        # For now, we'll use the existing method
        # In the future, this could be enhanced to provide more granular updates
        return await self._call_llm_with_tools(
            llm_profile=llm_profile,
            agent=agent,
            messages=messages,
            tools=tools,
            logger=logger
        )


# Singleton instance
agent_executor = AgentExecutor()