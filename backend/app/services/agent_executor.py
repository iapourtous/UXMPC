import json
import httpx
import logging
import uuid
import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, AsyncGenerator
from app.models.agent import (
    Agent, AgentExecution, AgentExecutionResponse,
    AgentExecutionProgress, ExecutionStep
)
from app.services.llm_crud import llm_crud
from app.services.service_crud import service_crud
from app.core.database import get_database
from app.core.mongodb_logger import ServiceLogger
from app.services.conversation_crud import conversation_crud
from app.models.conversation import MessageCreate, ConversationCreate
from app.services.conversation_compactor import conversation_compactor
from app.services.settings_crud import settings_crud
from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Executes agents by orchestrating LLM and MCP services"""
    
    def __init__(self):
        """Initialize the agent executor and load markdown capabilities"""
        self.markdown_capabilities = self._load_markdown_capabilities()
    
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
        
        # Handle conversation persistence
        conversation_id = None
        conversation = None
        
        if execution_request.save_conversation:
            # Get or create conversation
            if execution_request.conversation_id:
                conversation = await conversation_crud.get(execution_request.conversation_id)
                if conversation:
                    conversation_id = conversation.id
                else:
                    logger.warning(f"Conversation {execution_request.conversation_id} not found, creating new one")
            
            if not conversation:
                # Get latest conversation or create new one
                conversation = await conversation_crud.get_latest_conversation()
                if not conversation:
                    # Create new conversation
                    conversation = await conversation_crud.create(
                        ConversationCreate(
                            user_id=None,  # TODO: Add user support
                            title=f"New Conversation - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                            metadata={"execution_id": execution_id}
                        )
                    )
                conversation_id = conversation.id
        
        try:
            await agent_logger.info(
                f"Agent execution started",
                agent=agent.name,
                input_type=type(execution_request.input).__name__,
                conversation_id=conversation_id
            )
            
            # Save user message to conversation
            if conversation_id and execution_request.save_conversation:
                user_content = execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input)
                await conversation_crud.add_message(
                    conversation_id,
                    MessageCreate(
                        role="user",
                        content=user_content,
                        metadata={"execution_id": execution_id},
                        agent_id=None  # User messages don't have agent_id
                    )
                )
            
            # Validate input against schema
            if not self._validate_input(execution_request.input, agent.input_schema):
                error = "Input does not match agent's input schema"
                await agent_logger.error(error)
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
                await agent_logger.error(error)
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
                    agent_logger=agent_logger
                )
            
            # Load conversation history if conversation_id is provided
            loaded_history = []
            if conversation_id:
                # Load messages from conversation
                loaded_conversation = await conversation_crud.get(conversation_id)
                if loaded_conversation and loaded_conversation.messages:
                    # Convert stored messages to the format expected by LLM
                    for msg in loaded_conversation.messages:
                        loaded_history.append({
                            "role": msg.role,
                            "content": msg.content
                        })
            
            # If no history was provided but we loaded from conversation, use that
            if loaded_history and not execution_request.conversation_history:
                execution_request.conversation_history = loaded_history
            
            # Prepare tools from MCP services (BEFORE building messages)
            tools = await self._prepare_tools(agent.mcp_services, agent_logger, agent)
            
            # Build messages with tools context
            messages = self._build_messages(agent, execution_request, memory_context, tools)
            
            # Apply conversation compaction if enabled
            messages_for_agent = messages
            compaction_applied = False
            
            # Get global settings for compaction
            global_settings = await settings_crud.get_or_create()
            
            # Check if we should compact the conversation
            await agent_logger.info(
                "Compaction check",
                compaction_enabled=global_settings.compaction_settings.enabled,
                has_conversation_history=bool(execution_request.conversation_history),
                history_length=len(execution_request.conversation_history) if execution_request.conversation_history else 0
            )
            
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
                    
                    await agent_logger.info(
                        "Applied conversation compaction",
                        original_message_count=len(full_messages),
                        compacted_message_count=len(compacted_messages),
                        agent_system_messages_count=len(agent_system_messages),
                        final_messages_count=len(messages_for_agent)
                    )
                    
                    # Log the structure for debugging
                    for i, msg in enumerate(messages_for_agent):
                        role = msg["role"]
                        content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                        await agent_logger.debug(f"Message {i}: {role} - {content_preview}")
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
                
                await agent_logger.info("Using Adaptive Chain of Thought reasoning")
                
                # Import adaptive CoT engine
                from app.services.cot_adaptive_engine import adaptive_cot_engine
                
                # Prepare context for CoT
                cot_context = {
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
                            logger.warning(f"Tool {tool_name} not found in any category")
                            return f"Tool {tool_name} not found"
                        
                        # Execute the service directly
                        result = await mcp_manager._execute_service(service, arguments)
                        return result
                    except Exception as e:
                        logger.error(f"Tool execution error for {tool_name}: {str(e)}", exc_info=True)
                        return f"Error executing {tool_name}: {str(e)}"
                
                # Execute adaptive CoT with tools
                cot_result = await adaptive_cot_engine.execute(
                    problem=execution_request.input if isinstance(execution_request.input, str) else json.dumps(execution_request.input),
                    context=cot_context,
                    llm_profile=llm_profile,
                    conversation_history=messages_for_agent,
                    agent_config=agent_config,
                    tools=tools,  # Pass the tools
                    tool_executor=cot_tool_executor  # Pass the executor
                )
                
                if cot_result.success:
                    # Log CoT iterations
                    await agent_logger.info(
                        f"CoT completed with {cot_result.total_iterations} iterations",
                        complexity=cot_result.complexity_profile.cluster.value if cot_result.complexity_profile else "unknown",
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
                    await agent_logger.warning("CoT failed, falling back to standard execution")
                    result = await self._call_llm_with_tools(
                        llm_profile=llm_profile,
                        agent=agent,
                        messages=messages_for_agent,
                        tools=tools,
                        agent_logger=agent_logger,
                        max_iterations=agent.max_iterations
                    )
            else:
                # Standard execution without CoT
                result = await self._call_llm_with_tools(
                    llm_profile=llm_profile,
                    agent=agent,
                    messages=messages_for_agent,
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
                    execution_id=execution_id,
                    conversation_id=conversation_id
                )
            
            await agent_logger.info(
                "Agent execution completed",
                tool_calls_count=len(result.get("tool_calls", [])),
                iterations=result.get("iterations", 1)
            )
            
            # Save assistant response to conversation
            if conversation_id and execution_request.save_conversation:
                assistant_content = result["output"] if isinstance(result["output"], str) else json.dumps(result["output"])
                await conversation_crud.add_message(
                    conversation_id,
                    MessageCreate(
                        role="assistant",
                        content=assistant_content,
                        metadata={
                            "execution_id": execution_id,
                            "tool_calls_count": len(result.get("tool_calls", [])),
                            "iterations": result.get("iterations", 1)
                        },
                        tool_calls=result.get("tool_calls", []),
                        agent_id=agent.id  # Include agent ID
                    )
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
            
            # Update usage history for agent selection
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
                usage=result.get("usage", {}),
                conversation_id=conversation_id
            )
            
        except Exception as e:
            error_msg = f"Agent execution failed: {str(e)}"
            await agent_logger.error(error_msg, error=str(e))
            logger.error(error_msg, exc_info=True)
            
            # Save error to conversation if applicable
            if conversation_id and execution_request.save_conversation:
                await conversation_crud.add_message(
                    conversation_id,
                    MessageCreate(
                        role="assistant",
                        content="I encountered an error while processing your request.",
                        metadata={"execution_id": execution_id, "error": error_msg},
                        agent_id=agent.id
                    )
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
        
        # Add external MCP tools from connections
        if hasattr(agent, 'mcp_connections') and agent.mcp_connections:
            from app.services.mcp_client_service import mcp_client_service
            await agent_logger.info(f"Adding external MCP tools from {len(agent.mcp_connections)} connections")
            
            for connection_id in agent.mcp_connections:
                try:
                    # Get tools from MCP connection
                    mcp_tools = await mcp_client_service.get_available_tools(connection_id)
                    await agent_logger.debug(f"Retrieved {len(mcp_tools)} tools from connection {connection_id}")
                    
                    # Convert MCP tools to OpenAI function format
                    for mcp_tool in mcp_tools:
                        tool = {
                            "type": "function",
                            "function": {
                                "name": f"mcp_{connection_id}_{mcp_tool['name']}",  # Prefix to avoid conflicts
                                "description": mcp_tool.get('description', f"MCP tool: {mcp_tool['name']}"),
                                "parameters": mcp_tool.get('inputSchema', {
                                    "type": "object",
                                    "properties": {},
                                    "required": []
                                })
                            }
                        }
                        tools.append(tool)
                        await agent_logger.debug(f"Prepared external MCP tool: {mcp_tool['name']} from connection {connection_id}")
                        
                except Exception as e:
                    await agent_logger.error(f"Failed to load tools from MCP connection {connection_id}: {e}")
        
        return tools
    
    def _format_tools_for_context(self, tools: List[Dict[str, Any]]) -> str:
        """Format tool definitions for inclusion in system context"""
        if not tools:
            return ""
        
        formatted = "## Available Tools and Their Capabilities\n\n"
        formatted += "You have access to the following tools. Use them when needed to gather information or perform actions:\n\n"
        
        for i, tool in enumerate(tools, 1):
            if tool.get("type") != "function":
                continue
                
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            description = func.get("description", "No description available")
            params = func.get("parameters", {})
            
            # Tool header
            formatted += f"### {i}. {name}\n"
            formatted += f"{description}\n"
            
            # Parameters
            properties = params.get("properties", {})
            required = params.get("required", [])
            
            if properties:
                formatted += "**Parameters:**\n"
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "No description")
                    is_required = param_name in required
                    req_text = "required" if is_required else "optional"
                    
                    formatted += f"  - `{param_name}` ({param_type}, {req_text}): {param_desc}\n"
            else:
                formatted += "**Parameters:** None\n"
            
            formatted += "\n"
        
        formatted += "💡 **How to use tools:**\n"
        formatted += "- Call tools when you need specific information or to perform actions\n"
        formatted += "- Provide all required parameters\n"
        formatted += "- You can call multiple tools in sequence if needed\n"
        formatted += "- Once you have gathered all necessary information, provide your final answer\n\n"
        
        return formatted
    
    def _load_markdown_capabilities(self) -> str:
        """Load markdown capabilities instructions from file"""
        try:
            # Try to load from the prompts directory
            prompt_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'prompts',
                'markdown_capabilities.txt'
            )
            
            if os.path.exists(prompt_file):
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning(f"Markdown capabilities file not found at {prompt_file}")
                return ""
        except Exception as e:
            logger.error(f"Error loading markdown capabilities: {e}")
            return ""
    
    def _build_messages(self, agent: Agent, execution_request: AgentExecution, memory_context: Optional[str] = None, tools: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, str]]:
        """Build message list for LLM"""
        messages = []
        
        # Build enhanced system prompt with agent's identity
        # Add current date at the beginning of every prompt
        current_date = datetime.utcnow().strftime('%d/%m/%Y')
        system_content = f"Date d'aujourd'hui : {current_date}\n\n"
        
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
        
        # Add markdown rendering capabilities instructions
        if self.markdown_capabilities:
            system_content += self.markdown_capabilities + "\n\n"
        
        # Add memory context if available
        if memory_context:
            system_content += f"# Relevant Context from Memory\n{memory_context}\n\n"
        
        # Add available tools to context
        if tools:
            tools_description = self._format_tools_for_context(tools)
            if tools_description:
                system_content += tools_description
        
        # Add memory tools instructions if enabled
        if hasattr(agent, 'memory_enabled') and agent.memory_enabled:
            memory_config = getattr(agent, 'memory_config', {})
            if memory_config.get('active_memory', True):
                system_content += """# Your Memory System
You have a persistent memory that remembers past conversations, user preferences, and important information. You can interact with it naturally:

## Memory Tools Available:
- **memory_search**: Ask natural questions like "What did the user tell me about their programming preferences?" or "Do I know anything about Python frameworks?"
- **memory_store**: Save discoveries like "User prefers detailed technical explanations" or "Client works in healthcare industry"
- **memory_analyze**: Get insights about conversation patterns and user preferences

## How to Use Your Memory:
✅ **Search naturally**: ALWAYS start by asking your memory first, even for general questions. Ask things like "What do I know about X?" or "Have we discussed Y before?"
✅ **Be conversational**: "What do I remember about X?" "Did we discuss Y before?" "What are their preferences?"
✅ **Store insights**: After learning something important, save it for future conversations
✅ **Check understanding**: Use memory_analyze to understand conversation patterns and knowledge gaps

💡 **Remember**: Your memory understands context and semantics - you can ask questions just like you would ask a human!

"""
        
        # Add original system prompt if provided
        if agent.system_prompt:
            system_content += agent.system_prompt
        
        # Add critical constraints about links and web access
        system_content += """

# CRITICAL CONSTRAINTS
- You do NOT have access to the internet, search engines, or web browsing capabilities
- You CANNOT generate, invent, or hallucinate URL links
- You CANNOT claim to have performed web searches or accessed websites
- If you don't have a specific tool to access information, clearly state this limitation
- Use ONLY the tools that are explicitly provided to you
- Base your responses ONLY on your training knowledge and stored memory

IMPORTANT: When you have gathered enough information to answer the user's question completely, provide your final answer WITHOUT making any more tool calls. The absence of tool calls in your response indicates that you have completed your task."""
        
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
        """Call LLM with tools using centralized client"""
        tool_calls_history = []
        iterations = 0
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        while iterations < max_iterations:
            iterations += 1
            await agent_logger.debug(f"LLM iteration {iterations}")
            
            try:
                # Use centralized client for LLM call
                response = await llm_client.call_with_tools_iteration(
                    llm_profile=llm_profile,
                    messages=messages,
                    tools=tools,
                    temperature=agent.temperature or llm_profile.temperature,
                    max_tokens=agent.max_tokens or llm_profile.max_tokens,
                    require_tool_use=agent.require_tool_use if tools else False,
                    timeout=120.0
                )
                
                # Log the response for debugging
                await agent_logger.debug("LLM response structure", response_keys=list(response.keys()) if isinstance(response, dict) else type(response).__name__)
                
                # Check if response has expected structure
                if "choices" not in response:
                    await agent_logger.error("Unexpected LLM response format", response=response)
                    raise ValueError(f"LLM response missing 'choices' field. Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
                
                choice = response["choices"][0]
                message = choice["message"]
                
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
                
            except Exception as e:
                await agent_logger.error(f"Error in LLM iteration {iterations}: {str(e)}")
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
                
                # Check if it's an external MCP tool
                if tool_name.startswith("mcp_") and agent and hasattr(agent, 'mcp_connections'):
                    from app.services.mcp_client_service import mcp_client_service
                    
                    # Parse connection_id and tool name from prefixed name
                    # Format: mcp_{connection_id}_{tool_name}
                    parts = tool_name.split("_", 2)  # Split into mcp, connection_id, tool_name
                    if len(parts) >= 3:
                        connection_id = parts[1]
                        actual_tool_name = parts[2]
                        
                        # Execute external MCP tool
                        mcp_result = await mcp_client_service.execute_tool(connection_id, actual_tool_name, tool_args)
                        
                        if mcp_result.success:
                            result = mcp_result.result
                        else:
                            result = {"error": f"MCP tool execution failed: {mcp_result.error}"}
                        
                        results.append(result)
                        continue
                
                # Otherwise, call the internal MCP service
                service = await service_crud.get_by_name(tool_name)
                if not service:
                    result = {"error": f"Service '{tool_name}' not found"}
                else:
                    # Build URL
                    url = f"http://localhost:8000{service.route}"
                    
                    # Replace path parameters
                    for param_name, param_value in tool_args.items():
                        url = url.replace(f"{{{param_name}}}", str(param_value))
                    
                    # Make HTTP request with extended timeout for agent tools
                    async with httpx.AsyncClient(timeout=180.0) as client:  # 3 minutes timeout
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
        agent_logger: Optional[ServiceLogger]
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
                if agent_logger:
                    await agent_logger.info(f"Loaded {len(context_parts)} relevant memories")
                return context
            
            return None
            
        except Exception as e:
            if agent_logger:
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
            
            await agent_logger.info("Conversation saved to memory")
            
            # Extract preferences from the new messages only
            await agent_memory_service.extract_preferences(
                agent_id=agent.id,
                conversation=new_messages
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
    
    async def execute_with_progress(
        self, 
        agent: Agent, 
        execution_request: AgentExecution
    ) -> AsyncGenerator[AgentExecutionProgress, None]:
        """Execute an agent with streaming progress updates"""
        execution_id = str(uuid.uuid4())
        db = get_database()
        agent_logger = ServiceLogger(db, f"agent_{agent.id}", f"Agent: {agent.name}", execution_id)
        
        try:
            # Initial progress
            yield AgentExecutionProgress(
                step=ExecutionStep.STARTING,
                message=f"Starting execution for agent '{agent.name}'",
                progress=5
            )
            
            await agent_logger.info(
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
                await agent_logger.error(error)
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
                await agent_logger.error(error)
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
            
            tools = await self._prepare_tools(agent.mcp_services, agent_logger, agent)
            
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
                    agent_logger=agent_logger
                )
            
            # Build messages with tools context
            messages = self._build_messages(agent, execution_request, memory_context, tools)
            
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
                    agent_logger=agent_logger,
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
                        tool_results = await self._execute_tool_calls(
                            [tool_call], agent_logger, agent
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
                            output, messages, agent_logger
                        )
                    
                    # Validate output
                    if not self._validate_output(output, agent.output_schema):
                        error = "Output does not match agent's output schema"
                        await agent_logger.error(error, output=output)
                        yield AgentExecutionProgress(
                            step=ExecutionStep.ERROR,
                            message="Output validation failed",
                            progress=0,
                            error_detail=error
                        )
                        return
                    
                    await agent_logger.info(
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
            await agent_logger.warning(
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
            await agent_logger.error(f"Agent execution failed: {str(e)}")
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
        agent_logger: ServiceLogger
    ) -> Dict[str, Any]:
        """Call LLM with tools (wrapper for existing method)"""
        # For now, we'll use the existing method
        # In the future, this could be enhanced to provide more granular updates
        return await self._call_llm_with_tools(
            llm_profile=llm_profile,
            agent=agent,
            messages=messages,
            tools=tools,
            agent_logger=agent_logger
        )


# Singleton instance
agent_executor = AgentExecutor()