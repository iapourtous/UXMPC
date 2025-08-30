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
from app.services.cot_convergence_analyzer import ConvergenceAnalyzer
from app.services.cot_convergence_detector import ConvergenceDetector
from app.services.cot_recovery_manager import RecoveryManager
from app.services.cot_prompt_builder import PromptBuilder
from app.services.cot_tool_executor import ToolExecutor
from app.services.llm_crud import llm_crud
from app.services.settings_crud import settings_crud
from app.services.intrinsic_llm_tools import (
    INTRINSIC_LLM_TOOLS,
    INTRINSIC_TOOL_NAMES,
    intrinsic_tools_executor
)
from app.services.unified_logger import UnifiedLogger
from app.core.prompt_loader import PromptLoader
import uuid

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


class AdaptiveChainOfThought:
    """
    Main adaptive Chain of Thought engine with tool support
    Implements Auto-CoT inspired approach with tool execution
    """
    
    def __init__(self):
        self.complexity_analyzer = ComplexityAnalyzer()
        self.demonstration_generator = DemonstrationGenerator()
        self.convergence_detector = ConvergenceDetector()
        self.convergence_analyzer = ConvergenceAnalyzer()
        self.recovery_manager = RecoveryManager()
        self.prompt_builder = PromptBuilder()
        self.tool_executor = ToolExecutor()
        self.intrinsic_executor = intrinsic_tools_executor
        self.prompt_loader = PromptLoader()
    
    async def execute(
        self,
        problem: str,
        context: Dict[str, Any],
        llm_profile: Any,
        conversation_history: List[Dict[str, Any]],
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]] = None,
        tool_executor = None,
        execution_id: Optional[str] = None
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
        # Initialize unified logger
        execution_id = execution_id or str(uuid.uuid4())
        unified_logger = UnifiedLogger("cot_engine", "Chain of Thought Engine", execution_id)
        
        # Validate inputs
        if conversation_history is not None and not isinstance(conversation_history, list):
            # Type mismatch handled silently
            await unified_logger.warning(f"conversation_history type mismatch: {type(conversation_history)}")
            conversation_history = []
        
        if tools is not None and not isinstance(tools, list):
            # Type mismatch handled silently
            await unified_logger.warning(f"tools type mismatch: {type(tools)}")
            tools = None
        
        # Log input types for debugging (removed verbose logging)
        await unified_logger.debug("COT execution started", 
                                   conversation_length=len(conversation_history) if conversation_history else 0,
                                   tools_count=len(tools) if tools else 0)
        
        try:
            # Analyze problem complexity (now with LLM support)
            complexity = await self.complexity_analyzer.analyze_problem(
                problem, 
                context,
                llm_profile  # Pass LLM profile for intelligent analysis
            )
            
            # Log complexity to MongoDB only, not terminal
            # Complexity logged to MongoDB only
            await unified_logger.info(
                f"Problem complexity analyzed: {complexity.cluster.value}",
                max_iterations=complexity.max_iterations,
                confidence_threshold=complexity.confidence_threshold
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
            
            # Log tools count to MongoDB only
            # Tools count logged to MongoDB only
            await unified_logger.info(
                "Tools configured",
                intrinsic_tools=len(INTRINSIC_LLM_TOOLS),
                external_tools=len(tools) if tools else 0,
                total_tools=len(combined_tools)
            )
            
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
            
            # Context size logged to MongoDB only
            
            # Update convergence detector with dynamic confidence threshold from complexity analysis
            self.convergence_detector.confidence_threshold = complexity.confidence_threshold
            
            # Adjust max iterations if tool intensive
            adjusted_max_iterations = complexity.max_iterations
            if complexity.tool_intensive and combined_tools:
                adjusted_max_iterations = min(complexity.max_iterations + 2, 15)
                # Max iterations logged to MongoDB only
            
            # Main reasoning loop
            converged = False  # Initialize converged flag
            reason = "Not started"
            
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
                    tool_executor,
                    unified_logger
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
                    # Convergence logged to MongoDB only
                    break
                
                # Update context for next iteration
                current_context = self._update_context(
                    current_context,
                    iteration
                )
            
            # Log the final convergence status for debugging
            await unified_logger.info(
                f"Main loop completed - Converged: {converged}, Reason: {reason}",
                iterations_count=len(iterations),
                max_iterations=adjusted_max_iterations
            )
            
            # Check if we need recovery iterations
            # Use cumulative confidence instead of just the last iteration
            cumulative_confidence = self.convergence_detector._calculate_cumulative_confidence(iterations)
            if not converged and cumulative_confidence < 0.90:
                # Analyze why convergence failed
                failure_analysis = await self.convergence_analyzer.analyze_failure(
                    iterations, problem, llm_profile
                )
                
                await unified_logger.warning(
                    f"Convergence failed, attempting recovery strategy: {failure_analysis['suggested_strategy']}",
                    failure_type=failure_analysis['failure_type'],
                    cumulative_confidence=cumulative_confidence
                )
                
                # Execute recovery iterations using RecoveryManager
                recovery_iterations = await self.recovery_manager.execute_recovery_iterations(
                    failure_analysis['suggested_strategy'],
                    iterations,
                    problem,
                    current_context,
                    complexity,
                    llm_profile,
                    agent_config,
                    combined_tools,
                    tool_executor,
                    unified_logger,
                    self._execute_iteration  # Pass the iteration execution method as callback
                )
                
                # Add recovery iterations to main chain
                iterations.extend(recovery_iterations)
                all_tool_results.extend(
                    tr for it in recovery_iterations for tr in it.tool_results
                )
                
                # Update convergence status after recovery
                converged, reason = self.convergence_detector.check_convergence(
                    iterations,
                    adjusted_max_iterations + 5,  # Allow 5 more iterations
                    has_tools=bool(combined_tools)
                )
            
            # Synthesize final answer from all iterations and tool results
            # Synthesis phase (logging to MongoDB only)
            # Synthesis start logged to MongoDB only
            
            final_answer = await self._synthesize_final_answer(
                problem,
                iterations,
                all_tool_results,
                current_context,  # Pass current_context which has full_context_messages
                llm_profile,
                agent_config
            )
            
            # Synthesis complete (logging to MongoDB only)
            # Synthesis completion logged to MongoDB only
            
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
        tool_executor,
        unified_logger: UnifiedLogger
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
                await self._parse_iteration_response(response, iteration_num, complexity.reasoning_strategy, tools)
            
            # Execute tools if requested
            tool_results = []
            if tool_calls:
                for tool_call in tool_calls:
                    try:
                        # Check if it's an intrinsic tool
                        if tool_call.tool_name in INTRINSIC_TOOL_NAMES:
                            # Execute intrinsic LLM tool
                            # Tool execution logged to MongoDB only
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
                            # External tool execution logged to MongoDB only
                            result = await tool_executor(tool_call.tool_name, tool_call.arguments)
                            tool_results.append(ToolResult(
                                tool_name=tool_call.tool_name,
                                result=result,
                                success=True
                            ))
                        else:
                            # Warning logged to MongoDB only
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
                    logger.debug(
                        f"Iteration {iteration_num} validation failed. "
                        f"Attempting correction {correction_attempt}/{max_correction_attempts}"
                    )
                    await unified_logger.log_validation(
                        validation_type=f"iteration_{iteration_num}",
                        is_valid=False,
                        feedback=iteration.validation_feedback,
                        scores={
                            "relevance": iteration.relevance_score,
                            "progress": iteration.progress_score,
                            "correctness": iteration.correctness_score
                        }
                    )
                    continue
                else:
                    # Valid iteration, we're done
                    # Validation success logged to MongoDB only
                    await unified_logger.log_validation(
                        validation_type=f"iteration_{iteration_num}",
                        is_valid=True,
                        feedback=iteration.validation_feedback,
                        scores={
                            "relevance": iteration.relevance_score,
                            "progress": iteration.progress_score,
                            "correctness": iteration.correctness_score
                        }
                    )
                    break
            else:
                # No validation needed (first iteration or max corrections reached)
                break
        
        # Log if we exhausted correction attempts
        if correction_attempt >= max_correction_attempts and not iteration.is_valid:
            logger.debug(
                f"Iteration {iteration_num} still invalid after {max_correction_attempts} corrections. "
                f"Proceeding anyway."
            )
            await unified_logger.warning(
                f"Iteration {iteration_num} still invalid after corrections",
                correction_attempts=max_correction_attempts,
                validation_feedback=iteration.validation_feedback
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
        
        # Check if we're in recovery mode
        if context.get('recovery_mode') and context.get('recovery_prompt'):
            # Return recovery-specific prompt directly
            return context['recovery_prompt']
        
        # The full context (agent identity, memory, user context, etc.) is already in the base messages
        # We just need to add the iteration-specific instructions
        
        # Build previous context
        previous_context = await self._build_previous_context(previous_iterations, problem)
        
        # Build additional guidance
        additional_guidance = self._build_iteration_guidance(context, tools, complexity, agent_config)
        
        # Load and format the prompt
        prompt = self.prompt_loader.load_prompt('cot/iteration_prompt.txt', {
            'iteration_num': iteration_num,
            'max_iterations': complexity.max_iterations,
            'problem': problem,
            'previous_context': previous_context,
            'additional_guidance': additional_guidance
        })
        
        return prompt
    
    async def _build_previous_context(self, previous_iterations: List[ReasoningIteration], problem: str) -> str:
        """Build context from previous iterations"""
        if not previous_iterations:
            return ""
        
        context_parts = []
        
        if previous_iterations:
            # Strategy: Keep last 2 iterations complete, summarize the rest
            if len(previous_iterations) > 2:
                # Summarize older iterations
                older_iterations = previous_iterations[:-2]
                recent_iterations = previous_iterations[-2:]
                
                # Get summary of older iterations
                summary = await self._summarize_previous_iterations(older_iterations, problem)
                context_parts.append("## Previous iterations context:")
                context_parts.append(summary)
                
                # Add recent iterations in full detail
                context_parts.append("## Recent iterations (detailed):")
                for prev in recent_iterations:
                    context_parts.append(f"\n- Iteration {prev.iteration_number}:")
                    context_parts.append(f"  Thought: {prev.thought}")
                    if prev.tool_results:
                        context_parts.append(f"  Tools used: {', '.join([tr.tool_name for tr in prev.tool_results])}")
                        # Show actual results but limited to avoid context explosion
                        for tr in prev.tool_results:
                            if tr.success and tr.result:
                                result_str = str(tr.result)
                                if len(result_str) > 1000:
                                    result_str = result_str[:1000] + "... [see full in synthesis]"
                                context_parts.append(f"    → {tr.tool_name} found: {result_str}")
                            else:
                                context_parts.append(f"    → {tr.tool_name} FAILED: {tr.error}")
                    if prev.knowledge_gathered:
                        context_parts.append(f"  Learned: {prev.knowledge_gathered}")
                    if hasattr(prev, 'validation_feedback') and prev.validation_feedback:
                        context_parts.append(f"  Validation: {prev.validation_feedback}")
            else:
                # For first iterations, keep everything
                context_parts.append("Previous reasoning and findings:")
                for prev in previous_iterations:
                    context_parts.append(f"\n- Iteration {prev.iteration_number}:")
                    context_parts.append(f"  Thought: {prev.thought}")
                    if prev.tool_results:
                        context_parts.append(f"  Tools used: {', '.join([tr.tool_name for tr in prev.tool_results])}")
                        for tr in prev.tool_results:
                            if tr.success and tr.result:
                                result_str = str(tr.result)
                                if len(result_str) > 2000:
                                    result_str = result_str[:2000] + "... [truncated]"
                                context_parts.append(f"    → {tr.tool_name} found: {result_str}")
                    if prev.knowledge_gathered:
                        context_parts.append(f"  Learned: {prev.knowledge_gathered}")
        
        return "\n".join(context_parts)
    
    def _build_iteration_guidance(self, context: Dict[str, Any], tools: List[Dict[str, Any]], complexity: ComplexityProfile, agent_config: Dict[str, Any]) -> str:
        """Build additional guidance for iteration"""
        guidance_parts = []
        
        # Add available tools - NO LIMIT, show ALL tools
        if tools and isinstance(tools, list):
            guidance_parts.append("Available tools:")
            
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
                guidance_parts.append("🧠 **Memory Tools (check existing knowledge):**")
                for tool in memory_tools:
                    func = tool.get('function', {})
                    guidance_parts.append(f"- {func.get('name')}: {func.get('description', '')}")
                guidance_parts.append("")
            
            # Then show other tools with equal importance
            if other_tools:
                guidance_parts.append("🔧 **Action Tools (gather new information):**")
                for tool in other_tools:
                    func = tool.get('function', {})
                    guidance_parts.append(f"- {func.get('name')}: {func.get('description', '')}")
            
            guidance_parts.append("")
        
        # Add context if available - NO TRUNCATION
        if context.get('memory_context'):
            guidance_parts.append(f"Relevant memory: {context['memory_context']}")
            guidance_parts.append("")
        
        # Add accumulated facts to avoid repetition
        if context.get('accumulated_facts'):
            guidance_parts.append("📊 **Key facts discovered so far:**")
            # Show unique facts, avoiding duplicates
            seen_facts = set()
            for fact in context['accumulated_facts'][-10:]:  # Last 10 facts
                if fact not in seen_facts:
                    guidance_parts.append(f"  • {fact}")
                    seen_facts.add(fact)
            guidance_parts.append("")
            guidance_parts.append("⚠️ Build on these facts, don't repeat the same searches!")
            guidance_parts.append("")
        
        # Request structured response
        guidance_parts.append("""Perform the next reasoning step. You MUST provide your response in this EXACT format:

THOUGHT: [Your detailed reasoning for this step - what do you need to figure out?]

TOOL_CALLS: [List ALL tools you need, ONE PER LINE. You can use MULTIPLE tools!]
memory_search(query="what do I know about this topic")
memory_search(query="user preferences", filter_type="preference")
exa_property_finder(city="Paris", rent_or_buy="rent", price_max=1500)
web_search(query="additional information needed")
[Leave empty if no tools needed this iteration]
NOTE: For memory_search, omit filter_type to search all types, or use: "user_message", "agent_response", "preference", "stored_knowledge"

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
- Your reasoning will be validated for relevance, progress, and correctness""")
        
        return "\n".join(guidance_parts)
    
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
                
                # Force text mode for tools (JSON mode is incompatible with function calling)
                import copy
                text_mode_profile = copy.copy(llm_profile)
                text_mode_profile.mode = "text"
                
                # LLM call details logged to MongoDB only via unified_logger
                
                # Message content logged to MongoDB only
                
                # Use tools-enabled call with text mode
                response = await llm_client.call_with_tools_iteration(
                    llm_profile=text_mode_profile,
                    messages=messages,
                    tools=tools,
                    temperature=getattr(llm_profile, 'temperature', 0.7),
                    max_tokens=getattr(llm_profile, 'max_tokens', 2000),
                    require_tool_use=False,  # Don't force tool use
                    timeout=60.0
                )
                
                # Response structure debug logging removed - details in MongoDB
                
                # Extract content from response
                if response and "choices" in response and response["choices"]:
                    # Ensure content is never None
                    content = response["choices"][0]["message"].get("content") or ""
                    
                    # If the model called tools, format them in the response
                    tool_calls = response["choices"][0]["message"].get("tool_calls", [])
                    if tool_calls:
                        # Add tool calls to the content in the expected format
                        tool_calls_text = "\nTOOL_CALLS:\n"
                        for tc in tool_calls:
                            func = tc.get("function", {})
                            name = func.get("name", "unknown")
                            args = func.get("arguments", "{}")
                            # Parse arguments if they're a JSON string
                            try:
                                args_dict = json.loads(args) if isinstance(args, str) else args
                                # Build arguments string with proper formatting
                                arg_parts = []
                                for k, v in args_dict.items():
                                    if isinstance(v, str):
                                        # Escape quotes in string values
                                        v_escaped = v.replace('"', '\\"')
                                        arg_parts.append(f'{k}="{v_escaped}"')
                                    elif isinstance(v, (list, dict)):
                                        # Serialize complex types to JSON
                                        v_json = json.dumps(v)
                                        arg_parts.append(f'{k}={v_json}')
                                    elif isinstance(v, bool):
                                        arg_parts.append(f'{k}={str(v).lower()}')
                                    elif v is None:
                                        arg_parts.append(f'{k}=null')
                                    else:
                                        # Numbers and other simple types
                                        arg_parts.append(f'{k}={v}')
                                args_str = ", ".join(arg_parts)
                                tool_calls_text += f"{name}({args_str})\n"
                            except Exception as e:
                                logger.debug(f"Error formatting tool call {name}: {e}")
                                tool_calls_text += f"{name}({args})\n"
                        
                        # If we have tool calls but no content, create a minimal valid response
                        if not content:
                            # Tool call response logged to MongoDB only
                            content = f"THOUGHT: I need to use tools to gather information.{tool_calls_text}\nEVALUATION: Gathering information.\nCONFIDENCE: 0.3\nSHOULD_CONTINUE: true\nKNOWLEDGE_GATHERED: Processing..."
                        elif "TOOL_CALLS:" not in content:
                            # Insert tool calls into existing content
                            if "THOUGHT:" in content and "EVALUATION:" in content:
                                parts = content.split("EVALUATION:")
                                content = parts[0] + tool_calls_text + "\nEVALUATION:" + "EVALUATION:".join(parts[1:])
                            else:
                                content = content + "\n" + tool_calls_text
                    
                    # If still no content and no tool calls, create a default response
                    if not content:
                        # No content from LLM - logged to MongoDB only
                        content = "THOUGHT: Processing the request.\n\nTOOL_CALLS:\n\nEVALUATION: Need to continue analysis.\nCONFIDENCE: 0.2\nSHOULD_CONTINUE: true\nKNOWLEDGE_GATHERED: Starting analysis..."
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
            
            # Log error briefly
            if "400" in str(e):
                logger.error(f"LLM call failed (400): {str(e)[:200]}")
            
            raise
    
    async def _parse_iteration_response(
        self,
        response: str,
        iteration_num: int,
        reasoning_type: str,
        tools: List[Dict[str, Any]] = None
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
            # Use the tool executor to parse tool calls
            tool_calls = await self.tool_executor.parse_tool_calls(
                sections['TOOL_CALLS'], 
                tools if tools else []
            )
        
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
        
        # Synthesis called - details logged to MongoDB only
        # Problem logged to MongoDB only
        # Iterations count logged to MongoDB only
        # Tool results count logged to MongoDB only
        
        # Initialize URL collection
        all_urls = []
        
        # Load synthesis prompt template using PromptLoader
        try:
            prompt_template = self.prompt_loader.load_prompt('cot/synthesize_answer.txt')
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
                            summary_result = await self._summarize_tool_result(
                                tool_name=tr.tool_name,
                                result=result_str,
                                problem=problem,
                                iteration_thought=iteration.thought
                            )
                            # Handle new format
                            if isinstance(summary_result, dict):
                                result_str = summary_result.get("summary", result_str[:10000])
                                # Collect URLs for later
                                all_urls.extend(summary_result.get("urls", []))
                            else:
                                result_str = summary_result  # Fallback for old format
                            reasoning_chain_text += f"- {tr.tool_name} (summarized from {len(str(tr.result))} chars):\n```\n{result_str}\n```\n"
                        else:
                            reasoning_chain_text += f"- {tr.tool_name}:\n```\n{result_str}\n```\n"
                            # Also extract URLs from non-summarized results
                            extracted = self._extract_urls(result_str)
                            all_urls.extend(extracted)
            
            if iteration.knowledge_gathered:
                reasoning_chain_text += f"**Knowledge gathered:** {iteration.knowledge_gathered}\n"
            reasoning_chain_text += "\n---\n\n"
        
        # Build consolidated tool results section  
        tool_results_text = "## ALL TOOL RESULTS:\n\n"
        # Building synthesis - logged to MongoDB only
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
                    
                    summary_result = await self._summarize_tool_result(
                        tool_name=tool_result.tool_name,
                        result=result_str,
                        problem=problem,
                        iteration_thought=iteration_thought
                    )
                    # Handle new format
                    if isinstance(summary_result, dict):
                        result_str = summary_result.get("summary", result_str[:10000])
                        # Collect URLs for later
                        all_urls.extend(summary_result.get("urls", []))
                    else:
                        result_str = summary_result  # Fallback for old format
                    tool_results_text += f"### {tool_result.tool_name} (summarized from {original_length} chars):\n```\n{result_str}\n```\n\n"
                    logger.debug(f"Added summarized tool result from {tool_result.tool_name} ({original_length} -> {len(result_str)} chars)")
                else:
                    tool_results_text += f"### {tool_result.tool_name}:\n```\n{result_str}\n```\n\n"
                    logger.debug(f"Added tool result from {tool_result.tool_name} (length: {len(result_str)})")
                    # Also extract URLs from non-summarized results
                    extracted = self._extract_urls(result_str)
                    all_urls.extend(extracted)
        
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
            
            # LLM synthesis call - logged to MongoDB only
            
            # Force text mode by temporarily modifying the profile
            import copy
            synthesis_profile = copy.deepcopy(llm_profile)
            synthesis_profile.mode = "text"  # FORCE TEXT MODE
            
            # Build messages with full context for synthesis
            synthesis_messages = []
            
            # Collect all system messages to merge them
            system_contents = []
            other_messages = []
            
            # Process existing context messages
            if context.get('full_context_messages'):
                for msg in context['full_context_messages']:
                    if msg['role'] == 'system':
                        # Collect system message content
                        system_contents.append(msg['content'])
                    else:
                        # Keep non-system messages as-is
                        other_messages.append(msg)
            
            # Add synthesis-specific system content with markdown capabilities
            # Markdown capabilities are ONLY added here for the final synthesis
            try:
                markdown_capabilities = self.prompt_loader.load_prompt('markdown_capabilities.txt')
                synthesis_system_content = """You are creating the final answer. Transform all data into natural language. Never return JSON, always return prose.

## Enhanced Markdown Capabilities Available:
""" + markdown_capabilities
            except Exception:
                # Fallback if markdown capabilities file not found
                synthesis_system_content = "You are creating the final answer. Transform all data into natural language. Never return JSON, always return prose."
            
            system_contents.append(synthesis_system_content)
            
            # Create a single merged system message
            if system_contents:
                merged_system_content = "\n\n---\n\n".join(system_contents)
                synthesis_messages.append({
                    "role": "system",
                    "content": merged_system_content
                })
            
            # Add all non-system messages after the merged system message
            synthesis_messages.extend(other_messages)
            
            # Add the synthesis prompt as user message
            synthesis_messages.append({
                "role": "user",
                "content": synthesis_prompt
            })
            
            # Save synthesis_messages to /tmp/prompt.txt for debugging
            try:
                import os
                tmp_dir = "/tmp"
                if os.path.exists(tmp_dir):
                    prompt_file_path = os.path.join(tmp_dir, "prompt.txt")
                    with open(prompt_file_path, "w", encoding="utf-8") as f:
                        # Write synthesis_messages as formatted JSON for readability
                        json.dump(synthesis_messages, f, indent=2, ensure_ascii=False)
                    logger.info(f"Synthesis messages saved to {prompt_file_path}")
            except Exception as e:
                logger.warning(f"Could not save synthesis messages to /tmp/prompt.txt: {e}")
            
            # Use call_advanced with full context
            response = await llm_client.call_advanced(
                llm_profile=synthesis_profile,
                messages=synthesis_messages,
                temperature=getattr(synthesis_profile, 'temperature', 0.7)
            )
            
            # Synthesis response logged to MongoDB only
            logger.debug(f"Final answer preview: {response[:200]}...")
            
            # Add URLs section if we found any (after synthesis to avoid hallucination)
            if all_urls:
                # Deduplicate URLs
                seen_urls = set()
                unique_urls = []
                for url_info in all_urls:
                    if url_info['url'] not in seen_urls:
                        seen_urls.add(url_info['url'])
                        unique_urls.append(url_info)
                
                if unique_urls:
                    # Filter and select most relevant URLs
                    relevant_urls = await self._filter_relevant_urls(unique_urls, problem, llm_profile)
                    
                    if relevant_urls:
                        # Generate descriptions for filtered URLs
                        urls_with_descriptions = await self._describe_urls_with_llm(relevant_urls, llm_profile)
                        
                        # Add URLs section
                        url_section = "\n\n---\n\n## 📎 Liens et références\n\n"
                        for url_info in urls_with_descriptions:
                            description = url_info.get('description', f"Lien vers {url_info['url'].split('/')[2]}")
                            url_section += f"- [{description}]({url_info['url']})\n"
                        
                        response = response.strip() + url_section
            
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
                            pass  # Tool JSON result logged to MongoDB only
                
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
    
    def _extract_urls(self, text: str) -> List[Dict[str, str]]:
        """Extract all URLs from text with their surrounding context
        
        Args:
            text: Text to extract URLs from
            
        Returns:
            List of dicts with 'url' and 'context' keys
        """
        # Regex pattern for URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+(?:[.,;](?=[^\s])|[^\s.,;])*'
        
        urls_with_context = []
        seen_urls = set()
        
        # Patterns to exclude (internal/debug URLs)
        exclude_patterns = [
            r'localhost',
            r'127\.0\.0\.1',
            r'0\.0\.0\.0',
            r'192\.168\.',
            r'10\.0\.',
            r'172\.16\.',
            r'\.local/',
            r'example\.com',
            r'test\.com'
        ]
        
        # Find all URLs
        for match in re.finditer(url_pattern, text):
            url = match.group(0)
            
            # Clean trailing punctuation AND quotes/apostrophes
            # Remove common ending characters that are not part of URLs
            url = url.rstrip('.,;:!?\'"')
            
            # Also remove trailing parentheses if not balanced
            if url.endswith(')') and '(' not in url:
                url = url.rstrip(')')
            
            # Skip internal/debug URLs
            if any(re.search(pattern, url, re.IGNORECASE) for pattern in exclude_patterns):
                continue
            
            # Skip if we've already seen this URL
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Get context around the URL (50 chars before and after)
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()
            
            # Clean up context
            context = context.replace('\n', ' ').replace('\r', ' ')
            context = ' '.join(context.split())  # Normalize whitespace
            
            urls_with_context.append({
                "url": url,
                "context": context
            })
        
        return urls_with_context
    
    async def _describe_urls_with_llm(
        self,
        urls: List[Dict[str, str]],
        llm_profile: Any
    ) -> List[Dict[str, str]]:
        """Generate short descriptions for URLs using LLM
        
        Args:
            urls: List of URL dicts with 'url' and 'context'
            llm_profile: LLM profile to use
            
        Returns:
            List of URL dicts with added 'description' field
        """
        if not urls:
            return urls
        
        try:
            # Build prompt for URL descriptions
            prompt = "Pour chaque URL suivante, génère une description courte (1 phrase) basée sur le contexte fourni:\n\n"
            
            for i, url_info in enumerate(urls, 1):
                prompt += f"{i}. URL: {url_info['url']}\n"
                prompt += f"   Contexte: {url_info['context'][:200]}\n\n"
            
            prompt += """Format de réponse attendu (une ligne par URL):
1. [Description courte et claire]
2. [Description courte et claire]
etc.

Descriptions (une par ligne):"""
            
            # Use LLM to generate descriptions
            from app.core.llm_client import LLMClient
            client = LLMClient()
            
            import copy
            text_profile = copy.deepcopy(llm_profile)
            text_profile.mode = "text"
            
            response = await client.call_advanced(
                llm_profile=text_profile,
                prompt=prompt,
                temperature=0.3,
                max_tokens=1000
            )
            
            if response:
                # Parse descriptions
                lines = response.strip().split('\n')
                for i, line in enumerate(lines):
                    if i < len(urls):
                        # Remove numbering if present
                        desc = re.sub(r'^\d+\.\s*', '', line.strip())
                        urls[i]['description'] = desc if desc else f"Lien vers {urls[i]['url'].split('/')[2]}"
            
            # Add fallback descriptions for any missing ones
            for url_info in urls:
                if 'description' not in url_info:
                    # Extract domain as fallback
                    domain = url_info['url'].split('/')[2] if len(url_info['url'].split('/')) > 2 else 'ressource'
                    url_info['description'] = f"Lien vers {domain}"
                    
        except Exception as e:
            logger.error(f"Failed to generate URL descriptions: {e}")
            # Add fallback descriptions
            for url_info in urls:
                domain = url_info['url'].split('/')[2] if len(url_info['url'].split('/')) > 2 else 'ressource'
                url_info['description'] = f"Lien vers {domain}"
        
        return urls
    
    async def _filter_relevant_urls(
        self,
        urls: List[Dict[str, str]],
        problem: str,
        llm_profile: Any,
        max_urls: int = 5
    ) -> List[Dict[str, str]]:
        """Filter and select only the most relevant URLs for the user's question
        
        Args:
            urls: List of URL dicts with 'url' and 'context'
            problem: The user's original question
            llm_profile: LLM profile to use
            max_urls: Maximum number of URLs to keep
            
        Returns:
            Filtered list of most relevant URLs
        """
        if not urls:
            return []
        
        # If we have few URLs, keep them all
        if len(urls) <= max_urls:
            return urls
        
        try:
            # Build prompt for URL relevance scoring
            prompt = f"""Question de l'utilisateur: {problem}

URLs trouvées dans les résultats:
"""
            for i, url_info in enumerate(urls, 1):
                prompt += f"\n{i}. URL: {url_info['url']}"
                if url_info.get('context'):
                    prompt += f"\n   Contexte: {url_info['context'][:100]}"
            
            prompt += f"""

Sélectionne les {max_urls} URLs les PLUS PERTINENTES et UTILES pour répondre à la question.
Critères de sélection:
- Pertinence directe avec la question
- Sources officielles ou de référence
- Informations complémentaires utiles
- Éviter les doublons de contenu

Retourne UNIQUEMENT les numéros des URLs sélectionnées, séparés par des virgules.
Exemple de format: 1,3,5,7,9

URLs sélectionnées (numéros uniquement):"""
            
            # Use LLM to select relevant URLs
            from app.core.llm_client import LLMClient
            client = LLMClient()
            
            import copy
            text_profile = copy.deepcopy(llm_profile)
            text_profile.mode = "text"
            
            response = await client.call_advanced(
                llm_profile=text_profile,
                prompt=prompt,
                temperature=0.3,
                max_tokens=100
            )
            
            if response:
                # Parse selected indices
                selected_indices = []
                try:
                    # Extract numbers from response
                    import re
                    numbers = re.findall(r'\d+', response.strip())
                    for num_str in numbers[:max_urls]:  # Limit to max_urls
                        idx = int(num_str) - 1  # Convert to 0-based index
                        if 0 <= idx < len(urls):
                            selected_indices.append(idx)
                except:
                    pass
                
                # Return selected URLs
                if selected_indices:
                    return [urls[i] for i in selected_indices]
                
            # Fallback: return first max_urls
            return urls[:max_urls]
            
        except Exception as e:
            logger.error(f"Failed to filter URLs: {e}")
            # Fallback: return first max_urls
            return urls[:max_urls]
    
    async def _summarize_tool_result(
        self,
        tool_name: str,
        result: str,
        problem: str,
        iteration_thought: str
    ) -> Dict[str, Any]:
        """Summarize long tool results using Summary LLM Profile from settings, preserving URLs"""
        # First, extract all URLs from the result (reliable method)
        extracted_urls = self._extract_urls(result)
        
        try:
            # Get global settings
            settings = await settings_crud.get_or_create()
            if not settings or not settings.summary_llm_profile:
                logger.debug("No Summary LLM profile configured in settings")
                # Fallback to truncation but preserve URLs
                truncated = result[:10000] + "\n... [truncated to 10000 chars]"
                return {
                    "summary": truncated,
                    "urls": extracted_urls
                }
            
            # Get the Summary LLM profile
            summary_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
            if not summary_profile or not summary_profile.active:
                logger.debug(f"Summary LLM profile '{settings.summary_llm_profile}' not found or inactive")
                # Fallback to truncation but preserve URLs
                truncated = result[:10000] + "\n... [truncated to 10000 chars]"
                return {
                    "summary": truncated,
                    "urls": extracted_urls
                }
            
            # Force text mode for summary
            import copy
            summary_profile = copy.deepcopy(summary_profile)
            summary_profile.mode = "text"
            
            # Build list of URLs to force inclusion
            urls_list = "\n".join([f"- {url['url']}" for url in extracted_urls]) if extracted_urls else "Aucune URL trouvée"
            
            summary_prompt = f"""Summarize this tool result, keeping information relevant to answering the user's question.

USER'S QUESTION: {problem}

REASONING CONTEXT: {iteration_thought}

TOOL NAME: {tool_name}

FULL TOOL RESULT TO SUMMARIZE (length: {len(result)} characters):
{result[:30000] if len(result) > 30000 else result}

INSTRUCTIONS:
- Extract data relevant to the user's question
- Keep specific numbers, dates, names, facts, and key data points
- DO NOT include URLs in your summary (they are extracted separately)
- Remove redundant or irrelevant information
- Keep the data structure when possible (lists, key-value pairs)
- If the data contains search results, keep the most relevant 5-10
- Target output: 2000-3000 characters maximum
- Focus on factual information that helps answer the question

CONCISE SUMMARY (without URLs):"""

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
                # Tool result summary logged to MongoDB only
                return {
                    "summary": summary.strip(),
                    "urls": extracted_urls
                }
            else:
                logger.debug(f"Summary returned empty for {tool_name}")
                truncated = result[:10000] + "\n... [truncated to 10000 chars]"
                return {
                    "summary": truncated,
                    "urls": extracted_urls
                }
            
        except Exception as e:
            logger.error(f"Failed to summarize tool result: {e}")
            # Fallback to truncation but preserve URLs
            truncated = result[:10000] + "\n... [truncated to 10000 chars]"
            return {
                "summary": truncated,
                "urls": extracted_urls
            }
    
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
                logger.debug("No Summary LLM profile for iteration summary, using fallback")
                return self._fallback_iteration_summary(iterations)
            
            # Get the Summary LLM profile
            summary_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
            if not summary_profile or not summary_profile.active:
                logger.debug(f"Summary profile not active, using fallback")
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
            
            # Create summary using prompt template
            summary_prompt = self.prompt_loader.load_prompt('cot/summarize_iterations.txt', {
                'problem': problem,
                'iterations_text': iterations_text
            })

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
                # Iterations summary logged to MongoDB only
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