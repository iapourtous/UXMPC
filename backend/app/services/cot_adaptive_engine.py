"""
Adaptive Chain of Thought Engine with Tool Support
Main orchestrator for adaptive reasoning with tool execution and convergence detection
"""
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import json
import re
from datetime import datetime
from app.core.llm_client import llm_client

from app.services.cot_complexity_analyzer import ComplexityAnalyzer, ComplexityProfile
from app.services.cot_demonstration_generator import DemonstrationGenerator, ReasoningPath
from app.services.llm_crud import llm_crud
from app.services.settings_crud import settings_crud
from app.services.intrinsic_llm_tools import (
    INTRINSIC_LLM_TOOLS,
    INTRINSIC_TOOL_NAMES,
    intrinsic_tools_executor
)

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call request"""
    tool_name: str
    arguments: Dict[str, Any]
    
    
@dataclass
class ToolResult:
    """Result from a tool execution"""
    tool_name: str
    result: Any
    success: bool
    error: Optional[str] = None


@dataclass
class ReasoningIteration:
    """Single iteration in the reasoning chain"""
    iteration_number: int
    reasoning_type: str
    thought: str
    tool_calls: List[ToolCall]
    tool_results: List[ToolResult]
    evaluation: str
    confidence: float
    should_continue: bool
    knowledge_gathered: str  # Summary of what was learned
    # Validation fields
    is_valid: bool = True  # Whether this iteration passed validation
    validation_feedback: Optional[str] = None  # Feedback from validation
    correction_attempts: int = 0  # Number of correction attempts
    relevance_score: float = 1.0  # How relevant the step was (0-1)
    progress_score: float = 1.0  # How much progress was made (0-1)
    correctness_score: float = 1.0  # How correct the reasoning is (0-1)


@dataclass
class ChainOfThoughtResult:
    """Complete result of Chain of Thought reasoning"""
    final_answer: str
    iterations: List[ReasoningIteration]
    total_iterations: int
    complexity_profile: ComplexityProfile
    convergence_reason: str
    success: bool
    all_tool_results: List[ToolResult]  # All tools results accumulated


class ConvergenceDetector:
    """Detects when reasoning has converged to a stable answer"""
    
    def __init__(self):
        self.confidence_threshold = 0.85
        self.min_iterations_with_tools = 3  # At least 3 iterations if tools are available
        
    def check_convergence(
        self,
        iterations: List[ReasoningIteration],
        max_iterations: int,
        has_tools: bool
    ) -> Tuple[bool, str]:
        """
        Check if reasoning has converged
        
        Returns:
            Tuple of (has_converged, reason)
        """
        if not iterations:
            return False, "No iterations yet"
        
        current_iteration = iterations[-1]
        
        # Check max iterations
        if len(iterations) >= max_iterations:
            return True, f"Reached maximum iterations ({max_iterations})"
        
        # If tools are available, ensure they've been used
        if has_tools:
            tool_calls_made = sum(len(it.tool_calls) for it in iterations)
            if tool_calls_made == 0 and len(iterations) < self.min_iterations_with_tools:
                return False, "Tools available but not yet used"
            
            # Check if we have enough information from tools
            # But require at least 3 iterations even with high confidence
            if current_iteration.tool_results and len(iterations) >= 3:
                # If we got good results and high confidence
                if current_iteration.confidence >= self.confidence_threshold:
                    return True, "High confidence with tool results after multiple iterations"
        
        # Check if agent decided to stop (but require at least 3 iterations)
        if not current_iteration.should_continue and len(iterations) >= 3:
            return True, "Agent determined answer is complete with sufficient iterations"
        
        # Check confidence threshold (only after minimum iterations)
        if current_iteration.confidence >= self.confidence_threshold and len(iterations) >= 4:
            return True, f"High confidence reached ({current_iteration.confidence:.2f})"
        
        # Don't converge too early - require at least 3 iterations for complex problems
        if len(iterations) < 3:
            return False, "Need more iterations for comprehensive analysis"
        
        return False, "Continue reasoning"


class AdaptiveChainOfThought:
    """
    Main adaptive Chain of Thought engine with tool support
    Implements Auto-CoT inspired approach with tool execution
    """
    
    def __init__(self):
        self.complexity_analyzer = ComplexityAnalyzer()
        self.demonstration_generator = DemonstrationGenerator()
        self.convergence_detector = ConvergenceDetector()
        self.intrinsic_executor = intrinsic_tools_executor
    
    async def execute(
        self,
        problem: str,
        context: Dict[str, Any],
        llm_profile: Any,
        conversation_history: List[Dict[str, Any]],
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]] = None,
        tool_executor = None
    ) -> ChainOfThoughtResult:
        """
        Execute adaptive Chain of Thought reasoning with tool support
        
        Args:
            problem: The problem/question to solve
            context: Full context including memory, tools, etc.
            llm_profile: LLM profile for making calls
            conversation_history: Previous conversation messages
            agent_config: Agent's 7D configuration
            tools: Available tools in OpenAI format
            tool_executor: Function to execute tools
            
        Returns:
            Complete CoT result with reasoning chain and tool results
        """
        # Validate inputs
        if conversation_history is not None and not isinstance(conversation_history, list):
            logger.warning(f"conversation_history should be a list, got {type(conversation_history)}. Converting to empty list.")
            conversation_history = []
        
        if tools is not None and not isinstance(tools, list):
            logger.warning(f"tools should be a list, got {type(tools)}. Converting to None.")
            tools = None
        
        # Log input types for debugging
        logger.debug(f"COT execute - conversation_history type: {type(conversation_history)}, len: {len(conversation_history) if conversation_history else 0}")
        logger.debug(f"COT execute - tools type: {type(tools)}, len: {len(tools) if tools else 0}")
        
        try:
            # Analyze problem complexity (now with LLM support)
            complexity = await self.complexity_analyzer.analyze_problem(
                problem, 
                context,
                llm_profile  # Pass LLM profile for intelligent analysis
            )
            
            logger.info(
                f"Problem complexity: {complexity.cluster.value}, "
                f"max iterations: {complexity.max_iterations}, "
                f"confidence threshold: {complexity.confidence_threshold}"
            )
            
            # Generate diverse reasoning demonstrations
            demonstrations = await self.demonstration_generator.generate_diverse_demonstrations(
                problem,
                complexity,
                context
            )
            
            # Merge intrinsic LLM tools with external tools
            # Intrinsic tools are always available for reasoning
            combined_tools = INTRINSIC_LLM_TOOLS.copy()
            if tools:
                # Add external MCP tools
                combined_tools.extend(tools)
            
            logger.info(f"Total tools available: {len(combined_tools)} ({len(INTRINSIC_LLM_TOOLS)} intrinsic + {len(tools) if tools else 0} external)")
            
            # Initialize reasoning chain
            iterations = []
            all_tool_results = []
            current_context = self._prepare_initial_context(
                problem,
                context,
                conversation_history,
                agent_config,
                demonstrations,
                combined_tools  # Use combined tools instead of just external tools
            )
            
            # Store the full context messages for use in all iterations
            # conversation_history contains all the system messages with agent config, memory, etc.
            if conversation_history and isinstance(conversation_history, list) and len(conversation_history) > 0:
                current_context['full_context_messages'] = conversation_history[:-1]
            else:
                current_context['full_context_messages'] = []
            
            logger.debug(f"full_context_messages set with {len(current_context['full_context_messages'])} messages")
            
            # Update convergence detector with dynamic confidence threshold from complexity analysis
            self.convergence_detector.confidence_threshold = complexity.confidence_threshold
            
            # Adjust max iterations if tool intensive
            adjusted_max_iterations = complexity.max_iterations
            if complexity.tool_intensive and combined_tools:
                adjusted_max_iterations = min(complexity.max_iterations + 2, 15)
                logger.info(f"Tool-intensive problem detected, adjusting max iterations to {adjusted_max_iterations}")
            
            # Main reasoning loop
            for iteration_num in range(1, adjusted_max_iterations + 1):
                # Execute one reasoning iteration
                iteration = await self._execute_iteration(
                    iteration_num,
                    problem,
                    current_context,
                    iterations,
                    complexity,
                    llm_profile,
                    agent_config,
                    combined_tools,  # Use combined tools
                    tool_executor
                )
                
                iterations.append(iteration)
                all_tool_results.extend(iteration.tool_results)
                
                # Check convergence (use adjusted max iterations)
                converged, reason = self.convergence_detector.check_convergence(
                    iterations,
                    adjusted_max_iterations,
                    has_tools=bool(combined_tools)  # Always true now with intrinsic tools
                )
                
                if converged:
                    logger.info(f"Reasoning converged: {reason}")
                    break
                
                # Update context for next iteration
                current_context = self._update_context(
                    current_context,
                    iteration
                )
            
            # Synthesize final answer from all iterations and tool results
            logger.info("=" * 50)
            logger.info("STARTING SYNTHESIS PHASE")
            logger.info(f"Number of tool results to synthesize: {len(all_tool_results)}")
            logger.info("=" * 50)
            
            final_answer = await self._synthesize_final_answer(
                problem,
                iterations,
                all_tool_results,
                current_context,  # Pass current_context which has full_context_messages
                llm_profile,
                agent_config
            )
            
            logger.info("=" * 50)
            logger.info("SYNTHESIS COMPLETE")
            logger.info(f"Final answer type: {type(final_answer)}")
            logger.info(f"Final answer starts with: {final_answer[:100] if final_answer else 'None'}...")
            logger.info("=" * 50)
            
            return ChainOfThoughtResult(
                final_answer=final_answer,
                iterations=iterations,
                total_iterations=len(iterations),
                complexity_profile=complexity,
                convergence_reason=reason if converged else "Max iterations reached",
                success=True,
                all_tool_results=all_tool_results
            )
            
        except Exception as e:
            logger.error(f"Chain of Thought execution failed: {str(e)}")
            return ChainOfThoughtResult(
                final_answer=f"Je n'ai pas pu compléter le raisonnement : {str(e)}",
                iterations=[],
                total_iterations=0,
                complexity_profile=None,
                convergence_reason="Error occurred",
                success=False,
                all_tool_results=[]
            )
    
    async def _execute_iteration(
        self,
        iteration_num: int,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration],
        complexity: ComplexityProfile,
        llm_profile: Any,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]],
        tool_executor
    ) -> ReasoningIteration:
        """Execute a single reasoning iteration with tool support and validation"""
        
        max_correction_attempts = 2  # Maximum number of correction attempts per iteration
        correction_attempt = 0
        validation_result = None
        
        while correction_attempt <= max_correction_attempts:
            # Build prompt for this iteration (or correction)
            if correction_attempt == 0:
                prompt = await self._build_iteration_prompt(
                    iteration_num,
                    problem,
                    context,
                    previous_iterations,
                    complexity,
                    agent_config,
                    tools
                )
            else:
                # Use correction prompt with validation feedback
                prompt = await self._correct_iteration(
                    iteration_num,
                    problem,
                    context,
                    previous_iterations,
                    complexity,
                    validation_result,
                    llm_profile,
                    agent_config,
                    tools
                )
            
            # Call LLM with full context messages if available and tools
            base_messages = context.get('full_context_messages')
            response = await self._call_llm(prompt, llm_profile, base_messages, tools)
            
            # Parse response
            thought, tool_calls, evaluation, confidence, should_continue, knowledge = \
                self._parse_iteration_response(response, iteration_num, complexity.reasoning_strategy)
            
            # Execute tools if requested
            tool_results = []
            if tool_calls:
                for tool_call in tool_calls:
                    try:
                        # Check if it's an intrinsic tool
                        if tool_call.tool_name in INTRINSIC_TOOL_NAMES:
                            # Execute intrinsic LLM tool
                            logger.debug(f"Executing intrinsic tool: {tool_call.tool_name}")
                            result_dict = await self.intrinsic_executor.execute(
                                tool_call.tool_name,
                                tool_call.arguments,
                                llm_profile,
                                context
                            )
                            
                            if result_dict["success"]:
                                tool_results.append(ToolResult(
                                    tool_name=tool_call.tool_name,
                                    result=result_dict["result"],
                                    success=True
                                ))
                            else:
                                tool_results.append(ToolResult(
                                    tool_name=tool_call.tool_name,
                                    result=None,
                                    success=False,
                                    error=result_dict.get("error", "Unknown error")
                                ))
                        elif tool_executor:
                            # Execute external MCP tool
                            logger.debug(f"Executing external tool: {tool_call.tool_name}")
                            result = await tool_executor(tool_call.tool_name, tool_call.arguments)
                            tool_results.append(ToolResult(
                                tool_name=tool_call.tool_name,
                                result=result,
                                success=True
                            ))
                        else:
                            logger.warning(f"External tool {tool_call.tool_name} called but no executor provided")
                            tool_results.append(ToolResult(
                                tool_name=tool_call.tool_name,
                                result=None,
                                success=False,
                                error="No tool executor available for external tools"
                            ))
                    except Exception as e:
                        logger.error(f"Tool execution failed: {tool_call.tool_name} - {str(e)}")
                        tool_results.append(ToolResult(
                            tool_name=tool_call.tool_name,
                            result=None,
                            success=False,
                            error=str(e)
                        ))
            
            # Create iteration object
            iteration = ReasoningIteration(
                iteration_number=iteration_num,
                reasoning_type=complexity.reasoning_strategy,
                thought=thought,
                tool_calls=tool_calls,
                tool_results=tool_results,
                evaluation=evaluation,
                confidence=confidence,
                should_continue=should_continue,
                knowledge_gathered=knowledge,
                correction_attempts=correction_attempt
            )
            
            # Validate the iteration (skip validation on very first iteration or if we're at max corrections)
            if iteration_num > 1 and correction_attempt < max_correction_attempts:
                validation_result = await self._validate_iteration(
                    iteration,
                    problem,
                    llm_profile
                )
                
                # Update iteration with validation results
                iteration.is_valid = validation_result.get("is_valid", True)
                iteration.validation_feedback = validation_result.get("feedback", "")
                iteration.relevance_score = validation_result.get("relevance_score", 1.0)
                iteration.progress_score = validation_result.get("progress_score", 1.0)
                iteration.correctness_score = validation_result.get("correctness_score", 1.0)
                
                # If invalid and we haven't exceeded corrections, try again
                if not iteration.is_valid:
                    correction_attempt += 1
                    logger.info(
                        f"Iteration {iteration_num} validation failed. "
                        f"Attempting correction {correction_attempt}/{max_correction_attempts}"
                    )
                    continue
                else:
                    # Valid iteration, we're done
                    logger.info(f"Iteration {iteration_num} validated successfully")
                    break
            else:
                # No validation needed (first iteration or max corrections reached)
                break
        
        # Log if we exhausted correction attempts
        if correction_attempt >= max_correction_attempts and not iteration.is_valid:
            logger.warning(
                f"Iteration {iteration_num} still invalid after {max_correction_attempts} corrections. "
                f"Proceeding anyway."
            )
        
        return iteration
    
    async def _build_iteration_prompt(
        self,
        iteration_num: int,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration],
        complexity: ComplexityProfile,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for a reasoning iteration with tool support"""
        
        # The full context (agent identity, memory, user context, etc.) is already in the base messages
        # We just need to add the iteration-specific instructions
        
        prompt = f"""## Chain of Thought Iteration {iteration_num}/{complexity.max_iterations}

You are now performing systematic reasoning to answer the user's question.
Remember all the context about the user (their name, preferences, etc.) from the system messages above.

💡 **Tool Usage Strategy**:
- You can and SHOULD use MULTIPLE tools per iteration when needed
- Start with memory_search() if relevant, then use other tools as needed
- Example of multiple tools in one iteration:
  memory_search(query="user preferences")
  exa_property_finder(city="Paris", rent_or_buy="rent", price_max=1500)
  web_search(query="Paris 11e neighborhood information")

"""
        
        # Add previous iterations - use summary for older iterations to save context
        if previous_iterations:
            # Strategy: Keep last 2 iterations complete, summarize the rest
            if len(previous_iterations) > 2:
                # Summarize older iterations
                older_iterations = previous_iterations[:-2]
                recent_iterations = previous_iterations[-2:]
                
                # Get summary of older iterations
                summary = await self._summarize_previous_iterations(older_iterations, problem)
                prompt += "## Previous iterations context:\n"
                prompt += summary + "\n\n"
                
                # Add recent iterations in full detail
                prompt += "## Recent iterations (detailed):\n"
                for prev in recent_iterations:
                    prompt += f"\n- Iteration {prev.iteration_number}:\n"
                    prompt += f"  Thought: {prev.thought}\n"
                    if prev.tool_results:
                        prompt += f"  Tools used: {', '.join([tr.tool_name for tr in prev.tool_results])}\n"
                        # Show actual results but limited to avoid context explosion
                        for tr in prev.tool_results:
                            if tr.success and tr.result:
                                result_str = str(tr.result)
                                if len(result_str) > 1000:
                                    result_str = result_str[:1000] + "... [see full in synthesis]"
                                prompt += f"    → {tr.tool_name} found: {result_str}\n"
                            else:
                                prompt += f"    → {tr.tool_name} FAILED: {tr.error}\n"
                    if prev.knowledge_gathered:
                        prompt += f"  Learned: {prev.knowledge_gathered}\n"
                    if hasattr(prev, 'validation_feedback') and prev.validation_feedback:
                        prompt += f"  Validation: {prev.validation_feedback}\n"
            else:
                # For first iterations, keep everything
                prompt += "Previous reasoning and findings:\n"
                for prev in previous_iterations:
                    prompt += f"\n- Iteration {prev.iteration_number}:\n"
                    prompt += f"  Thought: {prev.thought}\n"
                    if prev.tool_results:
                        prompt += f"  Tools used: {', '.join([tr.tool_name for tr in prev.tool_results])}\n"
                        for tr in prev.tool_results:
                            if tr.success and tr.result:
                                result_str = str(tr.result)
                                if len(result_str) > 2000:
                                    result_str = result_str[:2000] + "... [truncated]"
                                prompt += f"    → {tr.tool_name} found: {result_str}\n"
                    if prev.knowledge_gathered:
                        prompt += f"  Learned: {prev.knowledge_gathered}\n"
            prompt += "\n"
        
        # Add available tools - NO LIMIT, show ALL tools
        if tools and isinstance(tools, list):
            prompt += "Available tools:\n"
            
            # Prioritize memory tools - show them FIRST
            memory_tools = []
            other_tools = []
            
            for tool in tools:
                func = tool.get('function', {})
                tool_name = func.get('name', '')
                if tool_name in ['memory_search', 'memory_store', 'memory_analyze']:
                    memory_tools.append(tool)
                else:
                    other_tools.append(tool)
            
            # Show memory tools first but not too aggressively
            if memory_tools:
                prompt += "🧠 **Memory Tools (check existing knowledge):**\n"
                for tool in memory_tools:
                    func = tool.get('function', {})
                    prompt += f"- {func.get('name')}: {func.get('description', '')}\n"
                prompt += "\n"
            
            # Then show other tools with equal importance
            if other_tools:
                prompt += "🔧 **Action Tools (gather new information):**\n"
                for tool in other_tools:
                    func = tool.get('function', {})
                    prompt += f"- {func.get('name')}: {func.get('description', '')}\n"
            
            prompt += "\n"
        
        # Add context if available - NO TRUNCATION
        if context.get('memory_context'):
            prompt += f"Relevant memory: {context['memory_context']}\n\n"
        
        # Add accumulated facts to avoid repetition
        if context.get('accumulated_facts'):
            prompt += "📊 **Key facts discovered so far:**\n"
            # Show unique facts, avoiding duplicates
            seen_facts = set()
            for fact in context['accumulated_facts'][-10:]:  # Last 10 facts
                if fact not in seen_facts:
                    prompt += f"  • {fact}\n"
                    seen_facts.add(fact)
            prompt += "\n⚠️ Build on these facts, don't repeat the same searches!\n\n"
        
        # Request structured response
        prompt += """Perform the next reasoning step. You MUST provide your response in this EXACT format:

THOUGHT: [Your detailed reasoning for this step - what do you need to figure out?]

TOOL_CALLS: [List ALL tools you need, ONE PER LINE. You can use MULTIPLE tools!]
memory_search(query="what do I know about this topic")
exa_property_finder(city="Paris", rent_or_buy="rent", price_max=1500)
web_search(query="additional information needed")
[Leave empty if no tools needed this iteration]

EVALUATION: [Self-evaluation of your progress - what have you learned so far?]

CONFIDENCE: [A number between 0 and 1 indicating confidence in having enough information. Be conservative - only use high confidence (>0.8) after gathering comprehensive data from multiple sources]

SHOULD_CONTINUE: [true if you need more information/iterations, false if you have everything needed. For complex questions, gather data from at least 3-4 different angles]

KNOWLEDGE_GATHERED: [Brief summary of key facts/data gathered so far]

Important:
- 📋 **Tool Usage Best Practices**:
  1. Check memory first with memory_search() if the topic might be known
  2. Then use other tools to gather NEW information
  3. Use MULTIPLE tools in parallel when you need different types of information
  4. Store important findings with memory_store() at the end
- 🎯 **Be efficient**: Use multiple tools in one iteration to gather information faster
- 💾 **Memory is a tool, not the only tool**: Use it to complement, not replace other tools
- Focus on gathering ALL necessary information to answer the question
- Only set SHOULD_CONTINUE to false when you have all necessary information
- QUALITY MATTERS: Each step should directly contribute to solving the problem
- Your reasoning will be validated for relevance, progress, and correctness"""
        
        return prompt
    
    async def _call_llm(self, prompt: str, llm_profile: Any, base_messages: List[Dict[str, Any]] = None, tools: List[Dict[str, Any]] = None) -> str:
        """Make a call to the LLM with optional tools support"""
        try:
            # Validate and sanitize inputs
            if base_messages is not None and not isinstance(base_messages, list):
                logger.error(f"base_messages should be a list or None, got {type(base_messages)}")
                base_messages = []
            
            if tools is not None and not isinstance(tools, list):
                logger.error(f"tools should be a list or None, got {type(tools)}")
                tools = None
            
            # If tools are provided, use call_with_tools_iteration for proper tool support
            if tools and isinstance(tools, list) and len(tools) > 0:
                # Build messages list
                messages = base_messages.copy() if base_messages else []
                # Check if we need to add a system message
                if messages and not any(msg and isinstance(msg, dict) and msg.get('role') == 'system' for msg in messages):
                    messages.insert(0, {
                        "role": "system", 
                        "content": "You are performing systematic chain of thought reasoning. Use tools when needed to gather information."
                    })
                messages.append({"role": "user", "content": prompt})
                
                # Use tools-enabled call
                response = await llm_client.call_with_tools_iteration(
                    llm_profile=llm_profile,
                    messages=messages,
                    tools=tools,
                    temperature=getattr(llm_profile, 'temperature', 0.7),
                    max_tokens=getattr(llm_profile, 'max_tokens', 2000),
                    require_tool_use=False,  # Don't force tool use
                    timeout=60.0
                )
                
                # Extract content from response
                if response and "choices" in response and response["choices"]:
                    # Ensure content is never None
                    content = response["choices"][0]["message"].get("content") or ""
                    
                    # If the model called tools, format them in the response
                    tool_calls = response["choices"][0]["message"].get("tool_calls", [])
                    if tool_calls:
                        # Add tool calls to the content in the expected format
                        tool_calls_text = "\n\nTOOL_CALLS:\n"
                        for tc in tool_calls:
                            func = tc.get("function", {})
                            name = func.get("name", "unknown")
                            args = func.get("arguments", "{}")
                            # Parse arguments if they're a JSON string
                            try:
                                import json
                                args_dict = json.loads(args) if isinstance(args, str) else args
                                args_str = ", ".join([f'{k}="{v}"' for k, v in args_dict.items()])
                                tool_calls_text += f"{name}({args_str})\n"
                            except:
                                tool_calls_text += f"{name}({args})\n"
                        
                        # Insert tool calls into content if not already present
                        if content and "TOOL_CALLS:" not in content:
                            # Try to insert after THOUGHT section
                            if "THOUGHT:" in content and "EVALUATION:" in content:
                                parts = content.split("EVALUATION:")
                                content = parts[0] + tool_calls_text + "\nEVALUATION:" + "EVALUATION:".join(parts[1:])
                            else:
                                content = (content or "") + tool_calls_text
                    
                    if not content:
                        raise Exception("No content received from LLM")
                    return content
                else:
                    raise Exception("Invalid response structure from LLM")
            
            # Otherwise use the standard call_advanced without tools
            else:
                content = await llm_client.call_advanced(
                    llm_profile=llm_profile,
                    prompt=prompt,
                    base_messages=base_messages,
                    system_message="You are performing systematic chain of thought reasoning. Use tools when needed to gather information." if not base_messages else None,
                    temperature=getattr(llm_profile, 'temperature', 0.7),
                    max_tokens=getattr(llm_profile, 'max_tokens', 2000),
                    timeout=60.0,
                    json_mode=False,  # Force text mode for COT iterations (not JSON)
                    raise_on_error=True
                )
                
                if not content:
                    raise Exception("No content received from LLM")
                    
                return content
                
        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            raise
    
    def _parse_iteration_response(
        self,
        response: str,
        iteration_num: int,
        reasoning_type: str
    ) -> Tuple[str, List[ToolCall], str, float, bool, str]:
        """Parse LLM response into structured components"""
        
        # Default values
        thought = response
        tool_calls = []
        evaluation = "Reasoning step completed"
        confidence = 0.3  # Low default confidence
        should_continue = True  # Continue by default
        knowledge = ""
        
        # Parse structured response
        sections = {}
        current_section = None
        current_content = []
        
        for line in response.split('\n'):
            line = line.strip()
            
            # Check for section headers
            if line.startswith('THOUGHT:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = 'THOUGHT'
                current_content = [line[8:].strip()]
            elif line.startswith('TOOL_CALLS:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = 'TOOL_CALLS'
                current_content = [line[11:].strip()]
            elif line.startswith('EVALUATION:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = 'EVALUATION'
                current_content = [line[11:].strip()]
            elif line.startswith('CONFIDENCE:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = 'CONFIDENCE'
                current_content = [line[11:].strip()]
            elif line.startswith('SHOULD_CONTINUE:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = 'SHOULD_CONTINUE'
                current_content = [line[16:].strip()]
            elif line.startswith('KNOWLEDGE_GATHERED:'):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = 'KNOWLEDGE_GATHERED'
                current_content = [line[19:].strip()]
            elif current_section and line:
                current_content.append(line)
        
        # Add last section
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        # Extract values from sections
        if 'THOUGHT' in sections:
            thought = sections['THOUGHT'].strip()
        
        if 'TOOL_CALLS' in sections:
            tool_calls = self._parse_tool_calls(sections['TOOL_CALLS'])
        
        if 'EVALUATION' in sections:
            evaluation = sections['EVALUATION'].strip()
        
        if 'CONFIDENCE' in sections:
            try:
                conf_str = sections['CONFIDENCE'].strip()
                # Extract number from string like "0.7" or "0.7 - high confidence"
                conf_match = re.search(r'(\d*\.?\d+)', conf_str)
                if conf_match:
                    confidence = float(conf_match.group(1))
                    confidence = min(max(confidence, 0), 1)
            except:
                pass
        
        if 'SHOULD_CONTINUE' in sections:
            cont_str = sections['SHOULD_CONTINUE'].strip().lower()
            should_continue = 'true' in cont_str or 'yes' in cont_str
        
        if 'KNOWLEDGE_GATHERED' in sections:
            knowledge = sections['KNOWLEDGE_GATHERED'].strip()
        
        # If knowledge is empty or generic, extract from evaluation
        if not knowledge or knowledge in ["", "None", "N/A"]:
            if evaluation:
                # Use evaluation as knowledge if it contains insights
                knowledge = evaluation
        
        return thought, tool_calls, evaluation, confidence, should_continue, knowledge
    
    def _parse_tool_calls(self, tool_calls_str: str) -> List[ToolCall]:
        """Parse tool calls from string format"""
        tool_calls = []
        
        if not tool_calls_str or tool_calls_str.strip() == '':
            return tool_calls
        
        # Parse lines like: tool_name(arg1="value1", arg2="value2")
        lines = tool_calls_str.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith('['):
                continue
                
            # Match tool_name(args) - allow underscores in tool names
            match = re.match(r'([\w_]+)\((.*)\)', line)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                
                # Parse arguments
                arguments = {}
                if args_str:
                    # Try to handle different formats
                    # Format 1: key="value", key2="value2"
                    arg_matches = re.findall(r'(\w+)="([^"]*)"', args_str)
                    if arg_matches:
                        for key, value in arg_matches:
                            arguments[key] = value
                    # Format 2: Just a query string without key (for memory_search)
                    elif not '=' in args_str and args_str.strip():
                        # If it's just a string without key=value, assume it's the main parameter
                        # For memory_search, the parameter is "query"
                        if tool_name == "memory_search":
                            arguments["query"] = args_str.strip().strip('"\'')
                        else:
                            arguments["input"] = args_str.strip().strip('"\'')
                
                tool_calls.append(ToolCall(tool_name=tool_name, arguments=arguments))
        
        return tool_calls
    
    async def _validate_iteration(
        self,
        iteration: ReasoningIteration,
        problem: str,
        llm_profile: Any
    ) -> Dict[str, Any]:
        """Validate a reasoning iteration using self-evaluation"""
        
        # Load validation prompt template
        import os
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts", "cot", "validate_iteration.txt"
        )
        
        try:
            with open(prompt_path, 'r') as f:
                prompt_template = f.read()
        except Exception as e:
            logger.error(f"Failed to load validation prompt: {str(e)}")
            # Default to valid if we can't load the prompt
            return {
                "is_valid": True,
                "feedback": "Validation skipped - prompt not found"
            }
        
        # Format tool calls for display
        tool_calls_str = ""
        if iteration.tool_calls:
            formatted_calls = []
            for tc in iteration.tool_calls:
                args_str = ', '.join([f'{k}="{v}"' for k, v in tc.arguments.items()])
                formatted_calls.append(f"{tc.tool_name}({args_str})")
            tool_calls_str = "\n".join(formatted_calls)
        else:
            tool_calls_str = "None"
        
        # Build validation prompt
        validation_prompt = prompt_template.format(
            problem=problem,
            thought=iteration.thought,
            tool_calls=tool_calls_str,
            knowledge_gathered=iteration.knowledge_gathered or "None",
            confidence=iteration.confidence
        )
        
        try:
            # Call LLM for validation
            response = await self._call_llm(validation_prompt, llm_profile)
            
            # Parse validation response
            validation_result = self._parse_validation_response(response)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            # Default to valid if validation fails
            return {
                "is_valid": True,
                "feedback": f"Validation error: {str(e)}"
            }
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """Parse the validation response from LLM"""
        
        result = {
            "is_valid": True,  # Default to valid
            "relevance_score": 1.0,
            "progress_score": 1.0,
            "correctness_score": 1.0,
            "issues": [],
            "correction_needed": "",
            "suggested_approach": "",
            "feedback": ""
        }
        
        lines = response.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('VALIDATION_RESULT:'):
                val_str = line[18:].strip().upper()
                result["is_valid"] = "VALID" in val_str
            elif line.startswith('RELEVANCE_SCORE:'):
                try:
                    result["relevance_score"] = float(re.search(r'(\d*\.?\d+)', line[16:]).group(1))
                except:
                    pass
            elif line.startswith('PROGRESS_SCORE:'):
                try:
                    result["progress_score"] = float(re.search(r'(\d*\.?\d+)', line[15:]).group(1))
                except:
                    pass
            elif line.startswith('CORRECTNESS_SCORE:'):
                try:
                    result["correctness_score"] = float(re.search(r'(\d*\.?\d+)', line[18:]).group(1))
                except:
                    pass
            elif line.startswith('ISSUES:'):
                current_section = 'ISSUES'
                current_content = []
            elif line.startswith('CORRECTION_NEEDED:'):
                if current_section == 'ISSUES':
                    result["issues"] = [l.strip('- ') for l in current_content if l.strip().startswith('-')]
                current_section = 'CORRECTION'
                result["correction_needed"] = line[18:].strip()
            elif line.startswith('SUGGESTED_APPROACH:'):
                current_section = 'APPROACH'
                result["suggested_approach"] = line[19:].strip()
            elif line.startswith('VALIDATION_FEEDBACK:'):
                current_section = 'FEEDBACK'
                result["feedback"] = line[20:].strip()
            elif current_section and line:
                if current_section == 'ISSUES' and line.startswith('-'):
                    current_content.append(line)
                elif current_section == 'CORRECTION':
                    result["correction_needed"] += " " + line
                elif current_section == 'APPROACH':
                    result["suggested_approach"] += " " + line
                elif current_section == 'FEEDBACK':
                    result["feedback"] += " " + line
        
        # Process any remaining issues
        if current_section == 'ISSUES':
            result["issues"] = [l.strip('- ') for l in current_content if l.strip().startswith('-')]
        
        return result
    
    async def _correct_iteration(
        self,
        iteration_num: int,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration],
        complexity: ComplexityProfile,
        validation_result: Dict[str, Any],
        llm_profile: Any,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]]
    ) -> str:
        """Generate a corrected prompt based on validation feedback"""
        
        # Build corrected prompt with validation feedback
        prompt = f"""## Chain of Thought Iteration {iteration_num}/{complexity.max_iterations} - CORRECTION REQUIRED

Your previous reasoning step was not effective. Here's the feedback:

**Issues identified:**
{chr(10).join(['- ' + issue for issue in validation_result.get('issues', [])])}

**What needs correction:**
{validation_result.get('correction_needed', 'Improve relevance and focus on the problem')}

**Suggested approach:**
{validation_result.get('suggested_approach', 'Focus more directly on answering the question')}

**Scores from validation:**
- Relevance: {validation_result.get('relevance_score', 0):.1f}/1.0
- Progress: {validation_result.get('progress_score', 0):.1f}/1.0
- Correctness: {validation_result.get('correctness_score', 0):.1f}/1.0

Now, try again with a better approach. Focus on:
1. Directly addressing the problem
2. Making tangible progress toward the solution
3. Using tools effectively when needed
4. Avoiding circular reasoning or off-topic exploration

"""
        
        # Add the rest of the standard prompt structure
        base_prompt = await self._build_iteration_prompt(
            iteration_num,
            problem,
            context,
            previous_iterations,
            complexity,
            agent_config,
            tools
        )
        
        # Replace the header section with our correction prompt
        lines = base_prompt.split('\n')
        for i, line in enumerate(lines):
            if 'Previous reasoning and findings:' in line:
                # Insert correction prompt before previous iterations
                return prompt + '\n'.join(lines[i:])
        
        return prompt + base_prompt
    
    async def _synthesize_final_answer(
        self,
        problem: str,
        iterations: List[ReasoningIteration],
        all_tool_results: List[ToolResult],
        context: Dict[str, Any],
        llm_profile: Any,
        agent_config: Dict[str, Any]
    ) -> str:
        """Synthesize final answer from all iterations and tool results"""
        
        logger.info("_synthesize_final_answer called")
        logger.info(f"Problem: {problem[:100]}...")
        logger.info(f"Number of iterations: {len(iterations)}")
        logger.info(f"Number of tool results: {len(all_tool_results)}")
        
        # Load synthesis prompt template
        import os
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts", "cot", "synthesize_answer.txt"
        )
        
        try:
            with open(prompt_path, 'r') as f:
                prompt_template = f.read()
        except Exception as e:
            logger.error(f"Failed to load synthesis prompt: {str(e)}")
            # Fallback to inline prompt if file not found
            prompt_template = """Answer the question: {problem}
            
Using the following data:
{tool_results}

{insights}

Your response:"""
        
        # Build complete reasoning chain with iterations and tool results
        reasoning_chain_text = "## CHAIN OF THOUGHT REASONING PROCESS:\n\n"
        for iteration in iterations:
            reasoning_chain_text += f"### Iteration {iteration.iteration_number}\n"
            reasoning_chain_text += f"**Thought:** {iteration.thought}\n"
            reasoning_chain_text += f"**Confidence:** {iteration.confidence}%\n"
            
            # Add tool calls and results for this iteration
            if iteration.tool_calls:
                reasoning_chain_text += f"**Tools used:** {', '.join([tc.tool_name for tc in iteration.tool_calls])}\n"
                
            if iteration.tool_results:
                reasoning_chain_text += "**Tool Results:**\n"
                for tr in iteration.tool_results:
                    if tr.success and tr.result:
                        result_str = str(tr.result)
                        # If result is too long, summarize it with Summary LLM
                        if len(result_str) > 10000:
                            result_str = await self._summarize_tool_result(
                                tool_name=tr.tool_name,
                                result=result_str,
                                problem=problem,
                                iteration_thought=iteration.thought
                            )
                            reasoning_chain_text += f"- {tr.tool_name} (summarized from {len(str(tr.result))} chars):\n```\n{result_str}\n```\n"
                        else:
                            reasoning_chain_text += f"- {tr.tool_name}:\n```\n{result_str}\n```\n"
            
            if iteration.knowledge_gathered:
                reasoning_chain_text += f"**Knowledge gathered:** {iteration.knowledge_gathered}\n"
            reasoning_chain_text += "\n---\n\n"
        
        # Build consolidated tool results section  
        tool_results_text = "## ALL TOOL RESULTS:\n\n"
        logger.info(f"Building synthesis with {len(all_tool_results)} tool results")
        for i, tool_result in enumerate(all_tool_results):
            if tool_result.success and tool_result.result:
                result_str = str(tool_result.result)
                original_length = len(result_str)
                
                # If result is too long, summarize it with Summary LLM
                if len(result_str) > 10000:
                    # Find the corresponding iteration for context
                    iteration_thought = ""
                    for iteration in iterations:
                        if any(tr.tool_name == tool_result.tool_name for tr in iteration.tool_results):
                            iteration_thought = iteration.thought
                            break
                    
                    result_str = await self._summarize_tool_result(
                        tool_name=tool_result.tool_name,
                        result=result_str,
                        problem=problem,
                        iteration_thought=iteration_thought
                    )
                    tool_results_text += f"### {tool_result.tool_name} (summarized from {original_length} chars):\n```\n{result_str}\n```\n\n"
                    logger.debug(f"Added summarized tool result from {tool_result.tool_name} ({original_length} -> {len(result_str)} chars)")
                else:
                    tool_results_text += f"### {tool_result.tool_name}:\n```\n{result_str}\n```\n\n"
                    logger.debug(f"Added tool result from {tool_result.tool_name} (length: {len(result_str)})")
        
        # Build key insights section from all iterations
        insights_text = "## KEY INSIGHTS:\n\n"
        for iteration in iterations:
            if iteration.knowledge_gathered:
                insights_text += f"- **Iteration {iteration.iteration_number}:** {iteration.knowledge_gathered}\n"
        
        # Get communication style
        communication_style = agent_config.get('personality', {}).get('communication_style', 'clear and direct')
        
        # Format the prompt with all variables including reasoning chain
        synthesis_prompt = prompt_template.format(
            problem=problem,
            reasoning_chain=reasoning_chain_text,
            tool_results=tool_results_text,
            insights=insights_text,
            communication_style=json.dumps(communication_style)
        )
        
        try:
            # SYNTHESIS = SIMPLE TEXT GENERATION - NO COMPLEXITY!
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            logger.info(f"Calling LLM for synthesis - SIMPLE TEXT GENERATION")
            
            # Force text mode by temporarily modifying the profile
            import copy
            synthesis_profile = copy.deepcopy(llm_profile)
            synthesis_profile.mode = "text"  # FORCE TEXT MODE
            
            # Build messages with full context for synthesis
            synthesis_messages = []
            
            # Add all context messages (agent config, user context, memory, etc.)
            if context.get('full_context_messages'):
                synthesis_messages.extend(context.get('full_context_messages'))
                logger.info(f"Added {len(context.get('full_context_messages'))} context messages to synthesis")
            
            # Add synthesis system message
            synthesis_messages.append({
                "role": "system",
                "content": "You are creating the final answer. Transform all data into natural language. Never return JSON, always return prose."
            })
            
            # Add the synthesis prompt as user message
            synthesis_messages.append({
                "role": "user",
                "content": synthesis_prompt
            })
            
            # Use call_advanced with full context
            response = await llm_client.call_advanced(
                llm_profile=synthesis_profile,
                messages=synthesis_messages,
                temperature=getattr(synthesis_profile, 'temperature', 0.7)
            )
            
            logger.info(f"Synthesis response received, length: {len(response)}")
            logger.debug(f"Final answer preview: {response[:200]}...")
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to synthesize final answer: {str(e)}")
            logger.error(f"Using fallback for synthesis")
            # Fallback: return the best knowledge we have - NO TRUNCATION
            if all_tool_results:
                # Check if any result looks like JSON
                for tool_result in all_tool_results:
                    if tool_result.success and tool_result.result:
                        result_str = str(tool_result.result)
                        if result_str.strip().startswith('{'):
                            logger.warning(f"Tool {tool_result.tool_name} returned JSON: {result_str[:100]}...")
                
                result_summary = "Voici les informations trouvées:\n"
                for tool_result in all_tool_results:
                    if tool_result.success:
                        # Use complete result, no truncation
                        result_summary += f"\n{tool_result.tool_name}: {str(tool_result.result)}\n"
                return result_summary
            return "Je n'ai pas pu synthétiser une réponse complète."
    
    def _prepare_initial_context(
        self,
        problem: str,
        context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        agent_config: Dict[str, Any],
        demonstrations: List[ReasoningPath],
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare initial context for reasoning"""
        
        return {
            "problem": problem,
            "memory_context": context.get("memory_context", ""),
            "available_tools": [t.get('function', {}).get('name') for t in (tools or [])],
            "conversation_summary": self._summarize_conversation(conversation_history),
            "agent_config": agent_config,
            "demonstrations": demonstrations,
            "timestamp": datetime.now().isoformat()
        }
    
    def _update_context(
        self,
        context: Dict[str, Any],
        iteration: ReasoningIteration
    ) -> Dict[str, Any]:
        """Update context with iteration results"""
        
        updated = context.copy()
        
        # Add iteration to history
        if 'iteration_history' not in updated:
            updated['iteration_history'] = []
        
        updated['iteration_history'].append({
            "number": iteration.iteration_number,
            "thought": iteration.thought,
            "confidence": iteration.confidence,
            "tools_used": [tc.tool_name for tc in iteration.tool_calls],
            "knowledge": iteration.knowledge_gathered,
            "tool_results": [
                {
                    "tool": tr.tool_name,
                    "result": str(tr.result) if tr.success and tr.result else tr.error
                }
                for tr in iteration.tool_results
            ]
        })
        
        # Add accumulated facts from tool results
        if 'accumulated_facts' not in updated:
            updated['accumulated_facts'] = []
        
        # Extract key facts from this iteration's results
        for tr in iteration.tool_results:
            if tr.success and tr.result:
                # Extract important information (numbers, percentages, names, dates)
                facts = self._extract_key_facts(str(tr.result))
                updated['accumulated_facts'].extend(facts)
        
        # Also add the knowledge gathered as a fact
        if iteration.knowledge_gathered and iteration.knowledge_gathered not in ["", "None", "N/A"]:
            # NO TRUNCATION - use complete knowledge
            updated['accumulated_facts'].append(f"Iteration {iteration.iteration_number}: {iteration.knowledge_gathered}")
        
        # NO LIMIT on facts - let the LLM profile handle context size
        # The LLM's context window is the only limit
        # if len(updated['accumulated_facts']) > 20:
        #     updated['accumulated_facts'] = updated['accumulated_facts'][-20:]
        
        return updated
    
    async def _summarize_tool_result(
        self,
        tool_name: str,
        result: str,
        problem: str,
        iteration_thought: str
    ) -> str:
        """Summarize long tool results using Summary LLM Profile from settings"""
        try:
            # Get global settings
            settings = await settings_crud.get_or_create()
            if not settings or not settings.summary_llm_profile:
                logger.warning("No Summary LLM profile configured in settings")
                # Fallback to truncation
                return result[:10000] + "\n... [truncated to 10000 chars]"
            
            # Get the Summary LLM profile
            summary_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
            if not summary_profile or not summary_profile.active:
                logger.warning(f"Summary LLM profile '{settings.summary_llm_profile}' not found or inactive")
                # Fallback to truncation
                return result[:10000] + "\n... [truncated to 10000 chars]"
            
            # Force text mode for summary
            import copy
            summary_profile = copy.deepcopy(summary_profile)
            summary_profile.mode = "text"
            
            summary_prompt = f"""Summarize this tool result, keeping ONLY information relevant to answering the user's question.

USER'S QUESTION: {problem}

REASONING CONTEXT: {iteration_thought}

TOOL NAME: {tool_name}

FULL TOOL RESULT TO SUMMARIZE (length: {len(result)} characters):
{result}

INSTRUCTIONS:
- Extract ONLY data relevant to the user's question
- Keep ALL specific numbers, dates, names, facts, and data points
- Keep important URLs, references, and citations
- Remove redundant or irrelevant information
- Maintain the original data structure when possible (lists, key-value pairs)
- If the data contains search results, keep the most relevant ones
- Target output: ~5000 characters maximum

CONCISE SUMMARY (relevant data only):"""

            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            # Use higher max_tokens for summary as requested (8192)
            summary = await llm_client.call_advanced(
                llm_profile=summary_profile,
                prompt=summary_prompt,
                temperature=0.3,  # Low temperature for accurate summarization
                max_tokens=8192   # As requested by user
            )
            
            if summary:
                logger.info(f"Summarized {tool_name} result from {len(result)} to {len(summary)} characters")
                return summary.strip()
            else:
                logger.warning(f"Summary returned empty for {tool_name}")
                return result[:10000] + "\n... [truncated to 10000 chars]"
            
        except Exception as e:
            logger.error(f"Failed to summarize tool result: {e}")
            # Fallback to truncation
            return result[:10000] + "\n... [truncated to 10000 chars]"
    
    async def _summarize_previous_iterations(
        self,
        iterations: List[ReasoningIteration],
        problem: str
    ) -> str:
        """Summarize previous iterations to reduce context size"""
        try:
            # Get global settings
            settings = await settings_crud.get_or_create()
            if not settings or not settings.summary_llm_profile:
                logger.warning("No Summary LLM profile for iteration summary, using fallback")
                return self._fallback_iteration_summary(iterations)
            
            # Get the Summary LLM profile
            summary_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
            if not summary_profile or not summary_profile.active:
                logger.warning(f"Summary profile not active, using fallback")
                return self._fallback_iteration_summary(iterations)
            
            # Build detailed text of iterations to summarize
            iterations_text = ""
            for iteration in iterations:
                iterations_text += f"\nIteration {iteration.iteration_number}:\n"
                iterations_text += f"- Thought: {iteration.thought}\n"
                
                if iteration.tool_results:
                    iterations_text += f"- Tools used: {', '.join([tr.tool_name for tr in iteration.tool_results])}\n"
                    for tr in iteration.tool_results:
                        if tr.success:
                            # Include key results but limited
                            result_preview = str(tr.result)[:500]
                            iterations_text += f"  • {tr.tool_name} found: {result_preview}\n"
                        else:
                            iterations_text += f"  • {tr.tool_name} FAILED: {tr.error}\n"
                
                if iteration.knowledge_gathered:
                    iterations_text += f"- Knowledge: {iteration.knowledge_gathered}\n"
                
                iterations_text += f"- Confidence: {iteration.confidence}%\n"
            
            # Create summary prompt
            summary_prompt = f"""Summarize these Chain of Thought iterations for the next reasoning step.

USER'S QUESTION: {problem}

ITERATIONS TO SUMMARIZE:
{iterations_text}

CREATE A FUNCTIONAL SUMMARY that includes:
1. KEY FINDINGS: Most important facts and data discovered
2. FAILED ATTEMPTS: Tools that failed (to avoid repetition)  
3. ESTABLISHED FACTS: Confirmed information with specific data
4. CURRENT UNDERSTANDING: What we know so far about the question

Keep ONLY information useful for continuing the reasoning.
Remove redundancies and intermediate steps.
Preserve all important numbers, dates, names, and facts.

FUNCTIONAL SUMMARY:"""

            # Force text mode
            import copy
            summary_profile = copy.deepcopy(summary_profile)
            summary_profile.mode = "text"
            
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            summary = await llm_client.call_advanced(
                llm_profile=summary_profile,
                prompt=summary_prompt,
                temperature=0.3,
                max_tokens=8192
            )
            
            if summary:
                logger.info(f"Summarized {len(iterations)} iterations to {len(summary)} characters")
                return summary.strip()
            else:
                return self._fallback_iteration_summary(iterations)
                
        except Exception as e:
            logger.error(f"Failed to summarize iterations: {e}")
            return self._fallback_iteration_summary(iterations)
    
    def _fallback_iteration_summary(self, iterations: List[ReasoningIteration]) -> str:
        """Simple fallback summary if LLM summarization fails"""
        summary = "Previous iterations summary:\n"
        
        # Collect key findings
        key_findings = []
        failed_tools = set()
        
        for iteration in iterations:
            # Add knowledge gathered
            if iteration.knowledge_gathered:
                key_findings.append(f"Iter {iteration.iteration_number}: {iteration.knowledge_gathered[:1000]}")
            
            # Track failed tools
            for tr in iteration.tool_results:
                if not tr.success:
                    failed_tools.add(tr.tool_name)
        
        summary += "Key findings:\n"
        for finding in key_findings[-5:]:  # Last 5 findings
            summary += f"- {finding}\n"
        
        if failed_tools:
            summary += f"\nFailed tools (avoid): {', '.join(failed_tools)}\n"
        
        return summary
    
    def _extract_key_facts(self, text: str) -> List[str]:
        """Extract key facts from tool results"""
        import re
        facts = []
        
        # Extract percentages
        percentages = re.findall(r'\b\d+(?:\.\d+)?%', text)
        for pct in percentages:  # NO LIMIT - extract all percentages
            # Find context around percentage
            idx = text.find(pct)
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            context = text[start:end].strip()
            if context:
                facts.append(context)
        
        # Extract large numbers (e.g., statistics)
        numbers = re.findall(r'\b\d{4,}\b', text)
        for num in numbers:  # NO LIMIT - extract all numbers
            idx = text.find(num)
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            context = text[start:end].strip()
            if context:
                facts.append(context)
        
        # Extract dates (years)
        years = re.findall(r'\b20\d{2}\b', text)
        for year in set(years):  # NO LIMIT - extract all years
            idx = text.find(year)
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            context = text[start:end].strip()
            if context:
                facts.append(context)
        
        return facts  # NO LIMIT - return all extracted facts
    
    def _summarize_conversation(
        self,
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Create a brief summary of conversation history"""
        
        if not conversation_history:
            return "No previous conversation"
        
        recent = conversation_history[-6:]
        summary = "Recent conversation:\n"
        for msg in recent:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            summary += f"- {role}: {content}\n"
        
        return summary


# Create singleton instance
adaptive_cot_engine = AdaptiveChainOfThought()