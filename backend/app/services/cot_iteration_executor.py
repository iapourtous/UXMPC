"""
COT Iteration Executor
Handles execution and validation of individual reasoning iterations
"""
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
import logging
import re
import asyncio
from app.services.cot_tool_executor import ToolExecutor, ToolCall, ToolResult
from app.services.unified_logger import UnifiedLogger
from app.core.prompt_loader import PromptLoader
from app.services.intrinsic_llm_tools import (
    INTRINSIC_TOOL_NAMES,
    intrinsic_tools_executor
)

logger = logging.getLogger(__name__)


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
    knowledge_gathered: str
    # Validation fields
    is_valid: bool = True
    validation_feedback: Optional[str] = None
    correction_attempts: int = 0
    relevance_score: float = 1.0
    progress_score: float = 1.0
    correctness_score: float = 1.0


class IterationExecutor:
    """Executes and validates individual reasoning iterations"""
    
    def __init__(self):
        """Initialize iteration executor"""
        self.tool_executor = ToolExecutor()
        self.intrinsic_executor = intrinsic_tools_executor
        self.prompt_loader = PromptLoader()
    
    async def _detect_stagnation(
        self,
        iterations: List[ReasoningIteration]
    ) -> Tuple[bool, str]:
        """Detect if reasoning is stagnating or regressing"""
        if len(iterations) < 3:
            return False, "not_enough_data"
        
        # Check if we already did a strategic pivot recently (within last 3 iterations)
        recent_pivots = [it for it in iterations[-3:] if it.reasoning_type == "strategic_pivot"]
        if recent_pivots:
            return False, "recent_pivot_active"
        
        # Get last 3 iterations' confidence
        recent_confidences = [it.confidence for it in iterations[-3:]]
        
        # Check for regression (confidence dropping)
        if recent_confidences[0] > recent_confidences[-1] + 0.10:
            return True, "regressing"
        
        # Check for stagnation (confidence not improving)
        confidence_variance = max(recent_confidences) - min(recent_confidences)
        avg_confidence = sum(recent_confidences) / len(recent_confidences)
        
        if confidence_variance < 0.05 and avg_confidence < 0.70:
            return True, "stagnating_low"
        
        # Check for oscillation
        if len(iterations) >= 4:
            last_4 = [it.confidence for it in iterations[-4:]]
            if (last_4[0] > last_4[1] < last_4[2] > last_4[3] or
                last_4[0] < last_4[1] > last_4[2] < last_4[3]):
                return True, "oscillating"
        
        return False, "progressing"
    
    async def execute_iteration(
        self,
        iteration_num: int,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration],
        complexity: Any,
        llm_profile: Any,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]],
        tool_executor,
        unified_logger: UnifiedLogger
    ) -> ReasoningIteration:
        """Execute a single reasoning iteration with tool support"""
        
        # Check for stagnation/regression after 3+ iterations
        # But avoid checking if we're already in recovery or strategic analysis mode
        if (len(previous_iterations) >= 3 and 
            not context.get('in_strategic_analysis', False) and
            not context.get('recovery_mode', False)):
            is_stagnant, stagnation_type = await self._detect_stagnation(previous_iterations)
            
            if is_stagnant:
                # Execute strategic analysis iteration
                unified_logger.info(f"Stagnation detected: {stagnation_type}. Triggering strategic analysis.")
                return await self._execute_strategic_analysis(
                    iteration_num,
                    problem,
                    context,
                    previous_iterations,
                    stagnation_type,
                    complexity,
                    llm_profile,
                    agent_config,
                    tools,
                    tool_executor,
                    unified_logger
                )
        
        # Debug tools at entry
        await unified_logger.debug(
            f"execute_iteration called for iteration {iteration_num}",
            has_tools=tools is not None,
            tools_count=len(tools) if tools else 0,
            tools_type=type(tools).__name__,
            first_tool=tools[0].get('function', {}).get('name') if tools and len(tools) > 0 else None
        )
        
        max_correction_attempts = 2  # Maximum number of correction attempts per iteration
        correction_attempt = 0
        
        while correction_attempt <= max_correction_attempts:
            # Build the prompt for this iteration
            prompt = await self._build_iteration_prompt(
                iteration_num,
                problem,
                context,
                previous_iterations,
                complexity,
                agent_config,
                tools,
                correction_attempt
            )
            
            # Execute LLM call (use global instance like old version)
            from app.core.llm_client import llm_client
            
            # If tools are provided, use call_with_tools_iteration for proper tool support
            if tools and isinstance(tools, list) and len(tools) > 0:
                logger.info(f"TOOLS AVAILABLE: {len(tools)} tools for iteration {iteration_num}")
                await unified_logger.debug(
                    f"Using tools-enabled call for iteration {iteration_num}",
                    tools_count=len(tools),
                    tool_names=[t.get('function', {}).get('name') for t in tools[:5]]
                )
                
                # Build messages list with context
                base_messages = context.get('full_context_messages')
                messages = base_messages.copy() if base_messages else []
                
                # Check if we need to add a system message (exactly like old version)
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
                
                # Use tools-enabled call with text mode
                response_dict = await llm_client.call_with_tools_iteration(
                    llm_profile=text_mode_profile,
                    messages=messages,
                    tools=tools,
                    temperature=getattr(llm_profile, 'temperature', 0.7),
                    max_tokens=getattr(llm_profile, 'max_tokens', 2000),
                    require_tool_use=False,  # Don't force tool use
                    timeout=60.0
                )
                
                # Extract content from response
                if response_dict and "choices" in response_dict and response_dict["choices"]:
                    # Ensure content is never None
                    response = response_dict["choices"][0]["message"].get("content") or ""
                    
                    # If the model called tools, format them in the response
                    tool_calls = response_dict["choices"][0]["message"].get("tool_calls", [])
                    if tool_calls:
                        # Add tool calls to the content in the expected format
                        tool_calls_text = "\nTOOL_CALLS:\n"
                        for tc in tool_calls:
                            func = tc.get("function", {})
                            name = func.get("name", "unknown")
                            args = func.get("arguments", "{}")
                            tool_calls_text += f"{name}({args})\n"
                        response = response + tool_calls_text
                else:
                    response = ""
            else:
                # No tools, use simple call
                logger.warning(f"NO TOOLS AVAILABLE for iteration {iteration_num} - tools={tools}")
                response = await llm_client.call_advanced(
                    llm_profile=llm_profile,
                    prompt=prompt,
                    temperature=getattr(llm_profile, 'temperature', 0.7)
                )
            
            await unified_logger.debug(
                f"Iteration {iteration_num} LLM response preview",
                response_preview=response[:500] if response else None
            )
            
            # Parse the response
            thought, tool_calls, evaluation, confidence, should_continue, knowledge = \
                await self._parse_iteration_response(response, tools if tools else [])
            
            # Execute tools if any
            tool_results = []
            if tool_calls:
                await unified_logger.info(
                    f"Executing {len(tool_calls)} tools in parallel in iteration {iteration_num}",
                    tools=[tc.tool_name for tc in tool_calls]
                )
                
                # Create async tasks for parallel execution
                async def execute_and_summarize_tool(tool_call: ToolCall) -> ToolResult:
                    """Execute a single tool and optionally summarize its result"""
                    try:
                        # First, execute the tool
                        if tool_call.tool_name in INTRINSIC_TOOL_NAMES:
                            result_dict = await self.intrinsic_executor.execute(
                                tool_call.tool_name,
                                tool_call.arguments,
                                llm_profile,
                                context
                            )
                            
                            if result_dict["success"]:
                                raw_result = result_dict["result"]
                            else:
                                return ToolResult(
                                    tool_name=tool_call.tool_name,
                                    result=None,
                                    success=False,
                                    error=result_dict.get("error", "Unknown error")
                                )
                        elif tool_executor:
                            # Execute external MCP tool
                            raw_result = await tool_executor(tool_call.tool_name, tool_call.arguments)
                        else:
                            return ToolResult(
                                tool_name=tool_call.tool_name,
                                result=None,
                                success=False,
                                error="No tool executor available for external tools"
                            )
                        
                        # Check if result needs summarization (>10000 chars)
                        # Convert result to string properly
                        import json
                        if isinstance(raw_result, dict) or isinstance(raw_result, list):
                            result_str = json.dumps(raw_result, indent=2, default=str)
                        else:
                            result_str = str(raw_result)
                        if len(result_str) > 10000:
                            # Summarize long results immediately after execution
                            try:
                                from app.services.cot_answer_synthesizer import AnswerSynthesizer
                                synthesizer = AnswerSynthesizer()
                                
                                summary_result = await synthesizer.summarize_tool_result(
                                    tool_name=tool_call.tool_name,
                                    result=result_str,
                                    problem=problem,
                                    iteration_thought=thought  # Use current iteration's thought
                                )
                                
                                # Store both original and summary in the result
                                if isinstance(summary_result, dict):
                                    summarized_text = summary_result.get("summary", result_str[:10000])
                                    urls = summary_result.get("urls", [])
                                else:
                                    summarized_text = summary_result
                                    urls = []
                                
                                # Store the summarized result in agent's memory
                                if context and context.get('agent_id'):
                                    try:
                                        from app.core.agent_memory_tools import memory_store
                                        
                                        # Determine importance based on content length and tool type
                                        importance = min(0.9, 0.7 + (len(result_str) / 50000))  # Higher importance for longer content
                                        
                                        # Convert everything to simple text
                                        if isinstance(summarized_text, dict) or isinstance(summarized_text, list):
                                            summarized_text = json.dumps(summarized_text, indent=2, default=str)
                                        else:
                                            summarized_text = str(summarized_text)
                                        
                                        # Simple text format for memory
                                        memory_content = f"Tool: {tool_call.tool_name}\n\n{summarized_text}"
                                        
                                        await memory_store(
                                            agent_id=context['agent_id'],
                                            content=memory_content,
                                            importance=importance,
                                            tags=["tool_result", tool_call.tool_name, "summarized"],
                                            conversation_id=context.get('conversation_id')
                                        )
                                        
                                        logger.debug(f"Stored summarized result from {tool_call.tool_name} in agent memory")
                                    except Exception as mem_error:
                                        logger.warning(f"Failed to store result in memory: {mem_error}")
                                
                                # Return enriched result with summary
                                return ToolResult(
                                    tool_name=tool_call.tool_name,
                                    result={
                                        "original": raw_result,
                                        "summary": summarized_text,
                                        "urls": urls,
                                        "was_summarized": True
                                    },
                                    success=True
                                )
                            except Exception as e:
                                logger.warning(f"Summarization failed for {tool_call.tool_name}: {e}")
                                # Return original result if summarization fails
                                return ToolResult(
                                    tool_name=tool_call.tool_name,
                                    result=raw_result,
                                    success=True
                                )
                        else:
                            # No summarization needed but still store important results in memory
                            if context and context.get('agent_id') and len(result_str) > 500:
                                try:
                                    from app.core.agent_memory_tools import memory_store
                                    
                                    # For shorter results, store them as-is (they're already manageable)
                                    importance = min(0.7, 0.5 + (len(result_str) / 10000))
                                    
                                    # Simple text conversion
                                    if isinstance(raw_result, dict) or isinstance(raw_result, list):
                                        result_text = json.dumps(raw_result, indent=2, default=str)
                                    else:
                                        result_text = str(raw_result)
                                    
                                    # Simple text format for memory
                                    memory_content = f"Tool: {tool_call.tool_name}\n\n{result_text}"
                                    
                                    await memory_store(
                                        agent_id=context['agent_id'],
                                        content=memory_content,
                                        importance=importance,
                                        tags=["tool_result", tool_call.tool_name],
                                        conversation_id=context.get('conversation_id')
                                    )
                                    
                                    logger.debug(f"Stored result from {tool_call.tool_name} in agent memory")
                                except Exception as mem_error:
                                    logger.warning(f"Failed to store result in memory: {mem_error}")
                            
                            # No summarization needed
                            return ToolResult(
                                tool_name=tool_call.tool_name,
                                result=raw_result,
                                success=True
                            )
                            
                    except Exception as e:
                        logger.error(f"Tool execution failed: {tool_call.tool_name} - {str(e)}")
                        return ToolResult(
                            tool_name=tool_call.tool_name,
                            result=None,
                            success=False,
                            error=str(e)
                        )
                
                # Execute all tools in parallel (with summarization if needed)
                tasks = [execute_and_summarize_tool(tool_call) for tool_call in tool_calls]
                tool_results = await asyncio.gather(*tasks)
                
                # Log execution completion
                successful_tools = [r.tool_name for r in tool_results if r.success]
                failed_tools = [r.tool_name for r in tool_results if not r.success]
                
                if successful_tools:
                    await unified_logger.debug(
                        f"Successfully executed {len(successful_tools)} tools in parallel",
                        tools=successful_tools
                    )
                
                if failed_tools:
                    await unified_logger.warning(
                        f"Failed to execute {len(failed_tools)} tools",
                        tools=failed_tools
                    )
            
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
            
            # Check if auto_correct_errors is enabled in agent's decision policies
            auto_correct_errors = agent_config.get('decision_policies', {}).get('auto_correct_errors', True)
            
            # Validate the iteration only if auto_correct_errors is True
            # (skip validation on very first iteration or if we're at max corrections)
            if auto_correct_errors and iteration_num > 1 and correction_attempt < max_correction_attempts:
                validation_result = await self.validate_iteration(
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
                    break
            else:
                # No validation needed (auto_correct_errors=False) or max attempts reached
                if not auto_correct_errors:
                    logger.debug(f"Skipping iteration validation - auto_correct_errors is disabled")
                break
        
        return iteration
    
    async def _build_iteration_prompt(
        self,
        iteration_num: int,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration],
        complexity: Any,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]],
        correction_attempt: int
    ) -> str:
        """Build prompt for a single iteration"""
        
        prompt_parts = []
        
        # Add recovery context if in recovery mode
        if context.get('recovery_mode'):
            prompt_parts.append(context.get('recovery_prompt', ''))
        
        # Add strategic pivot context if we just did a strategic analysis
        if context.get('strategic_pivot'):
            pivot = context['strategic_pivot']
            prompt_parts.append(f"\\n## 🎯 STRATEGIC PIVOT ACTIVE:")
            prompt_parts.append(f"Root cause of stagnation: {pivot.get('root_cause', 'Unknown')}")
            prompt_parts.append(f"New strategy to follow: {pivot.get('new_strategy', 'Alternative approach')}")
            prompt_parts.append(f"Key insight: {pivot.get('key_insight', 'Change approach')}")
            prompt_parts.append("⚡ Apply this new strategy in your reasoning!\\n")
        
        # Add main problem
        prompt_parts.append(f"## Problem to Solve:\n{problem}\n")
        
        # Add previous iterations summary if any
        if previous_iterations:
            prompt_parts.append("\n## Previous Reasoning:")
            for prev in previous_iterations[-3:]:  # Last 3 iterations
                prompt_parts.append(f"\nIteration {prev.iteration_number}:")
                prompt_parts.append(f"- Thought: {prev.thought[:200]}...")
                if prev.tool_results:
                    prompt_parts.append(f"- Tools used: {', '.join([tr.tool_name for tr in prev.tool_results])}")
                prompt_parts.append(f"- Confidence: {prev.confidence:.0%}")
            
            # Add anti-repetition warning if we see the same tools being used
            tool_usage = {}
            for prev in previous_iterations:
                for tc in prev.tool_calls:
                    key = f"{tc.tool_name}_{str(tc.arguments)}"
                    tool_usage[key] = tool_usage.get(key, 0) + 1
            
            repeated_tools = [k for k, v in tool_usage.items() if v > 1]
            if repeated_tools:
                prompt_parts.append("\n⚠️ WARNING: You have already used these tool calls:")
                for tool_key in repeated_tools[:5]:
                    prompt_parts.append(f"  ❌ {tool_key.split('_')[0]} (used {tool_usage[tool_key]} times)")
                prompt_parts.append("⚠️ DO NOT REPEAT! Try different approaches or parameters!")
        
        # Add accumulated facts to avoid repetition
        if context.get('accumulated_facts'):
            prompt_parts.append("\n## 📊 Key facts discovered so far:")
            seen_facts = set()
            for fact in context['accumulated_facts'][-10:]:  # Last 10 facts
                if fact not in seen_facts:
                    prompt_parts.append(f"  • {fact[:200]}...")
                    seen_facts.add(fact)
            prompt_parts.append("⚠️ Build on these facts, don't repeat the same searches!")
        
        # Add correction feedback if this is a correction attempt
        if correction_attempt > 0 and previous_iterations:
            last_attempt = previous_iterations[-1]
            if hasattr(last_attempt, 'validation_feedback'):
                prompt_parts.append(f"\n## ⚠️ Correction Required:")
                prompt_parts.append(f"Previous attempt failed validation: {last_attempt.validation_feedback}")
                prompt_parts.append("Please address these issues in your response.")
        
        # Add available tools - SHOW ALL like old version
        if tools and isinstance(tools, list):
            prompt_parts.append("\n## Available Tools:")
            
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
            
            # Show memory tools first
            if memory_tools:
                prompt_parts.append("🧠 **Memory Tools (check existing knowledge):**")
                for tool in memory_tools:
                    func = tool.get('function', {})
                    prompt_parts.append(f"- {func.get('name')}: {func.get('description', '')}")
                prompt_parts.append("")
            
            # Then show other tools
            if other_tools:
                prompt_parts.append("🔧 **Action Tools (gather new information):**")
                for tool in other_tools:  # NO LIMIT - show ALL tools
                    func = tool.get('function', {})
                    prompt_parts.append(f"- {func.get('name')}: {func.get('description', '')}")
            
            prompt_parts.append("")
        
        # Add reasoning instructions
        prompt_parts.append("\n## Instructions:")
        prompt_parts.append("1. Think step by step about the problem")
        prompt_parts.append("2. Use tools when needed to gather information")
        prompt_parts.append("3. Evaluate your progress and confidence")
        prompt_parts.append("4. Decide if more iterations are needed")
        
        # Add output format with detailed tool examples like old version
        prompt_parts.append("\n## Required Output Format:")
        prompt_parts.append("Perform the next reasoning step. You MUST provide your response in this EXACT format:")
        prompt_parts.append("")
        prompt_parts.append("THOUGHT: [Your detailed reasoning for this step - what do you need to figure out?]")
        prompt_parts.append("")
        prompt_parts.append("TOOL_CALLS: [List ALL tools you need, ONE PER LINE. You can use MULTIPLE tools!]")
        prompt_parts.append("memory_search(query=\"what do I know about this topic\")")
        prompt_parts.append("memory_search(query=\"user preferences\", filter_type=\"preference\")")
        prompt_parts.append("web_search(query=\"additional information needed\")")
        prompt_parts.append("[Leave empty or write 'None' if no tools needed this iteration]")
        prompt_parts.append("")
        prompt_parts.append("EVALUATION: [Self-evaluation of your progress - what have you learned so far?]")
        prompt_parts.append("")
        prompt_parts.append("CONFIDENCE: [A number between 0 and 1 indicating confidence. Be conservative - only use high confidence (>0.8) after comprehensive data]")
        prompt_parts.append("")
        prompt_parts.append("SHOULD_CONTINUE: [true if you need more information/iterations, false if you have everything needed]")
        prompt_parts.append("")
        prompt_parts.append("KNOWLEDGE_GATHERED: [Brief summary of key facts/data gathered so far]")
        
        return "\n".join(prompt_parts)
    
    async def _parse_iteration_response(
        self,
        response: str,
        tools: List[Dict[str, Any]]
    ) -> Tuple[str, List[ToolCall], str, float, bool, str]:
        """Parse structured response from LLM"""
        
        # Extract sections using regex
        sections = self._extract_response_sections(response)
        
        # Parse each section
        thought = sections.get('thought', 'No thought provided')
        evaluation = sections.get('evaluation', 'No evaluation provided')
        confidence = sections.get('confidence', 0.5)
        should_continue = sections.get('should_continue', True)
        knowledge = sections.get('knowledge_gathered', '')
        
        # Parse tool calls
        tool_calls = []
        if sections.get('tool_calls_text'):
            tool_calls = await self.tool_executor.parse_tool_calls(
                sections['tool_calls_text'],
                tools if tools else []
            )
        
        return thought, tool_calls, evaluation, confidence, should_continue, knowledge
    
    def _extract_response_sections(self, text: str) -> Dict[str, Any]:
        """Extract structured sections from LLM response"""
        
        sections = {
            'thought': None,
            'tool_calls_text': None,
            'evaluation': None,
            'confidence': 0.5,
            'should_continue': True,
            'knowledge_gathered': None
        }
        
        # Extract THOUGHT
        thought_match = re.search(r'THOUGHT:\s*(.*?)(?=\n(?:TOOL_CALLS|EVALUATION|CONFIDENCE|SHOULD_CONTINUE|KNOWLEDGE_GATHERED|$))', 
                                 text, re.DOTALL | re.IGNORECASE)
        if thought_match:
            sections['thought'] = thought_match.group(1).strip()
        
        # Extract TOOL_CALLS
        tool_match = re.search(r'TOOL_CALLS:\s*(.*?)(?=\n(?:EVALUATION|CONFIDENCE|SHOULD_CONTINUE|KNOWLEDGE_GATHERED|$))', 
                              text, re.DOTALL | re.IGNORECASE)
        if tool_match:
            sections['tool_calls_text'] = tool_match.group(1).strip()
        
        # Extract EVALUATION
        eval_match = re.search(r'EVALUATION:\s*(.*?)(?=\n(?:CONFIDENCE|SHOULD_CONTINUE|KNOWLEDGE_GATHERED|$))', 
                              text, re.DOTALL | re.IGNORECASE)
        if eval_match:
            sections['evaluation'] = eval_match.group(1).strip()
        
        # Extract CONFIDENCE
        conf_match = re.search(r'CONFIDENCE:\s*([\d.]+)', text, re.IGNORECASE)
        if conf_match:
            try:
                sections['confidence'] = float(conf_match.group(1))
            except:
                sections['confidence'] = 0.5
        
        # Extract SHOULD_CONTINUE
        continue_match = re.search(r'SHOULD_CONTINUE:\s*(true|false|yes|no)', text, re.IGNORECASE)
        if continue_match:
            sections['should_continue'] = continue_match.group(1).lower() in ['true', 'yes']
        
        # Extract KNOWLEDGE_GATHERED
        knowledge_match = re.search(r'KNOWLEDGE_GATHERED:\s*(.*?)(?=\n(?:$))', 
                                   text, re.DOTALL | re.IGNORECASE)
        if knowledge_match:
            sections['knowledge_gathered'] = knowledge_match.group(1).strip()
        
        return sections
    
    async def validate_iteration(
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
            # Call LLM for validation (use global instance)
            from app.core.llm_client import llm_client
            
            response = await llm_client.call_advanced(
                llm_profile=llm_profile,
                prompt=validation_prompt,
                temperature=0.3
            )
            
            # Parse validation response
            validation_result = self._parse_validation_response(response)
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return {
                "is_valid": True,
                "feedback": f"Validation error: {str(e)}"
            }
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """Parse the validation response from LLM"""
        
        result = {
            "is_valid": True,
            "feedback": "",
            "relevance_score": 1.0,
            "progress_score": 1.0,
            "correctness_score": 1.0
        }
        
        # Check for explicit validation result
        if "VALID: NO" in response.upper() or "INVALID" in response.upper():
            result["is_valid"] = False
        
        # Extract feedback
        feedback_match = re.search(r'FEEDBACK:\s*(.*?)(?=\n(?:RELEVANCE|PROGRESS|CORRECTNESS|$))', 
                                  response, re.DOTALL | re.IGNORECASE)
        if feedback_match:
            result["feedback"] = feedback_match.group(1).strip()
        
        # Extract scores
        relevance_match = re.search(r'RELEVANCE.*?:\s*([\d.]+)', response, re.IGNORECASE)
        if relevance_match:
            try:
                result["relevance_score"] = float(relevance_match.group(1))
            except:
                pass
        
        progress_match = re.search(r'PROGRESS.*?:\s*([\d.]+)', response, re.IGNORECASE)
        if progress_match:
            try:
                result["progress_score"] = float(progress_match.group(1))
            except:
                pass
        
        correctness_match = re.search(r'CORRECTNESS.*?:\s*([\d.]+)', response, re.IGNORECASE)
        if correctness_match:
            try:
                result["correctness_score"] = float(correctness_match.group(1))
            except:
                pass
        
        # Determine validity based on scores if not explicitly stated
        if result["is_valid"] and (
            result["relevance_score"] < 0.3 or 
            result["progress_score"] < 0.2 or 
            result["correctness_score"] < 0.3
        ):
            result["is_valid"] = False
            if not result["feedback"]:
                result["feedback"] = "Low scores indicate issues with the iteration"
        
        return result
    
    async def _execute_strategic_analysis(
        self,
        iteration_num: int,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration],
        stagnation_type: str,
        complexity: Any,
        llm_profile: Any,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]],
        tool_executor: Any,
        unified_logger: UnifiedLogger
    ) -> ReasoningIteration:
        """Execute a special strategic analysis iteration when stagnant"""
        
        # Mark that we're in strategic analysis to prevent recursion
        context['in_strategic_analysis'] = True
        
        # Load strategic analysis prompt from file without variable substitution
        import os
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts", "cot", "strategic_analysis.txt"
        )
        
        try:
            with open(prompt_path, 'r') as f:
                prompt_template = f.read()
        except Exception as e:
            unified_logger.error(f"Failed to load strategic analysis prompt: {e}")
            # Fallback to embedded prompt if file fails
            prompt_template = self._get_fallback_strategic_prompt()
        
        # Prepare variables for prompt
        confidence_trend = ", ".join([f"{it.confidence:.0%}" for it in previous_iterations[-5:]])
        tools_used = list(set(
            tc.tool_name for it in previous_iterations 
            for tc in it.tool_calls if it.tool_calls
        ))
        tools_used_str = ", ".join(tools_used) if tools_used else "None"
        
        key_facts = context.get('accumulated_facts', [])[-5:]
        key_facts_str = "; ".join(key_facts) if key_facts else "None discovered yet"
        
        # Manually replace variables to avoid issues with JSON examples in prompt
        strategic_prompt = prompt_template
        strategic_prompt = strategic_prompt.replace("{iteration_count}", str(len(previous_iterations)))
        strategic_prompt = strategic_prompt.replace("{problem}", problem)
        strategic_prompt = strategic_prompt.replace("{confidence_trend}", confidence_trend)
        strategic_prompt = strategic_prompt.replace("{tools_used}", tools_used_str)
        strategic_prompt = strategic_prompt.replace("{key_facts}", key_facts_str)
        strategic_prompt = strategic_prompt.replace("{stagnation_type}", stagnation_type)
        
        # Call LLM for strategic analysis
        try:
            from app.core.llm_client import llm_client
            
            await unified_logger.debug("Calling LLM for strategic analysis")
            
            # Use JSON mode to ensure we get valid JSON
            import copy
            json_mode_profile = copy.copy(llm_profile)
            json_mode_profile.mode = "json"
            
            analysis_response = await llm_client.call_advanced(
                llm_profile=json_mode_profile,
                prompt=strategic_prompt,
                temperature=0.7,
                max_tokens=1500
            )
            
            await unified_logger.debug(
                "Strategic analysis response received",
                response_preview=analysis_response[:500] if analysis_response else None
            )
            
            # Parse the strategic analysis
            import json
            from app.core.json_extractor import extract_json_from_text
            
            analysis = extract_json_from_text(analysis_response)
            
            # Validate that we got a proper analysis
            if not analysis or not isinstance(analysis, dict):
                await unified_logger.warning("Strategic analysis returned invalid format, using defaults")
                analysis = {
                    'root_cause': 'Unable to determine - analysis format invalid',
                    'failed_patterns': ['Previous approaches not working'],
                    'new_strategy': 'Try simpler, more direct approach',
                    'key_insight': 'Need to simplify the problem',
                    'next_actions': [],
                    'confidence_in_pivot': 0.6
                }
            
            # Create a special iteration with the new strategy
            strategic_thought = f"""STRATEGIC PIVOT ANALYSIS:

Root Cause: {analysis.get('root_cause', 'Unknown')}

New Strategy: {analysis.get('new_strategy', 'Trying different approach')}

Key Insight: {analysis.get('key_insight', 'Need to change approach')}

I will now execute this new strategy with the following actions:
{json.dumps(analysis.get('next_actions', []), indent=2)}"""
            
            # For now, don't try to execute tools from strategic analysis
            # Just use the analysis to guide the next iteration
            tool_calls = []
            tool_results = []
            
            # Create strategic iteration with new direction
            # Reset context to allow normal iterations after this
            context['in_strategic_analysis'] = False
            
            # Store the new strategy in context for next iterations
            context['strategic_pivot'] = {
                'new_strategy': analysis.get('new_strategy'),
                'key_insight': analysis.get('key_insight'),
                'root_cause': analysis.get('root_cause')
            }
            
            iteration = ReasoningIteration(
                iteration_number=iteration_num,
                reasoning_type="strategic_pivot",
                thought=strategic_thought,
                tool_calls=tool_calls,
                tool_results=tool_results,
                evaluation=f"Strategic pivot: {analysis.get('new_strategy', 'alternative approach')}",
                confidence=max(0.5, analysis.get('confidence_in_pivot', 0.5)),  # At least 50% confidence in pivot
                should_continue=True,
                knowledge_gathered=analysis.get('key_insight', '')
            )
            
            await unified_logger.info(
                f"Strategic pivot executed",
                new_strategy=analysis.get('new_strategy'),
                confidence_in_pivot=analysis.get('confidence_in_pivot', 0.5)
            )
            
            return iteration
            
        except Exception as e:
            import traceback
            await unified_logger.error(
                f"Strategic analysis failed: {e}",
                error_type=type(e).__name__,
                traceback=traceback.format_exc()
            )
            # Mark that we're no longer in strategic analysis
            context['in_strategic_analysis'] = False
            context['force_new_approach'] = True
            
            # Create a simple fallback iteration instead of recursing
            return ReasoningIteration(
                iteration_number=iteration_num,
                reasoning_type="fallback_after_strategic_failure",
                thought="Strategic analysis failed. Continuing with simplified approach to avoid getting stuck.",
                tool_calls=[],
                tool_results=[],
                evaluation="Need to continue with available information",
                confidence=0.4,
                should_continue=True,
                knowledge_gathered="Strategic analysis unavailable"
            )
    
    def _get_fallback_strategic_prompt(self) -> str:
        """Get fallback strategic prompt if file loading fails"""
        return """## Strategic Analysis Required

You've been working on this problem for {iteration_count} iterations, but progress has stagnated.

### Current Situation:
- Problem: {problem}
- Confidence trend: {confidence_trend}
- Tools used so far: {tools_used}
- Key facts discovered: {key_facts}
- Stagnation type: {stagnation_type}

### Your Task: Diagnose and Pivot

**1. ROOT CAUSE ANALYSIS**
Identify WHY you're stuck:
- Are you asking the wrong questions?
- Are you using inappropriate tools?
- Is there a fundamental misunderstanding?
- Are you overthinking a simple problem?
- Is critical information missing?
- Are your assumptions incorrect?

**2. PATTERN RECOGNITION**
What patterns do you see in your previous attempts:
- Repeated failures with specific tools?
- Circular reasoning?
- Missing a key insight?
- Approaching from the wrong angle?

**3. STRATEGIC PIVOT**
Based on your analysis, define a NEW approach:
- What completely different angle could you try?
- What assumptions should you challenge?
- What tools haven't you used that might help?
- Should you simplify or break down the problem differently?
- Is there an analogy or similar problem you could leverage?

**4. CONCRETE NEXT STEPS**
Propose your next 2-3 specific actions using this new strategy:
- Be specific about which tools and parameters
- Explain why this approach is fundamentally different
- Set a clear success metric

### Output Format:
Return a JSON object with the following structure:
- root_cause: Brief explanation of why you're stuck
- failed_patterns: Array of patterns that aren't working
- new_strategy: Description of your new approach
- key_insight: What you realized that changes everything
- next_actions: Array of action objects, each with:
  - tool: The tool name to use
  - purpose: Why this will work differently
  - expected_outcome: What you expect to learn
- confidence_in_pivot: Number between 0.0 and 1.0

Remember: Einstein said "Insanity is doing the same thing over and over and expecting different results." 
Time to try something genuinely different!"""