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

from app.services.cot_complexity_analyzer import ComplexityAnalyzer, ComplexityProfile
from app.services.cot_demonstration_generator import DemonstrationGenerator, ReasoningPath
from app.services.llm_crud import llm_crud

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
        self.min_iterations_with_tools = 2  # At least 2 iterations if tools are available
        
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
            if current_iteration.tool_results:
                # If we got good results and high confidence
                if current_iteration.confidence >= self.confidence_threshold:
                    return True, "High confidence with tool results"
        
        # Check if agent decided to stop
        if not current_iteration.should_continue and len(iterations) >= 2:
            return True, "Agent determined answer is complete with sufficient iterations"
        
        # Check confidence threshold (only after minimum iterations)
        if current_iteration.confidence >= self.confidence_threshold and len(iterations) >= 3:
            return True, f"High confidence reached ({current_iteration.confidence:.2f})"
        
        # Don't converge too early
        if len(iterations) < 2:
            return False, "Need more iterations"
        
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
            
            # Initialize reasoning chain
            iterations = []
            all_tool_results = []
            current_context = self._prepare_initial_context(
                problem,
                context,
                conversation_history,
                agent_config,
                demonstrations,
                tools
            )
            
            # Store the full context messages for use in all iterations
            # conversation_history contains all the system messages with agent config, memory, etc.
            current_context['full_context_messages'] = conversation_history[:-1] if conversation_history else []
            
            # Update convergence detector with dynamic confidence threshold from complexity analysis
            self.convergence_detector.confidence_threshold = complexity.confidence_threshold
            
            # Adjust max iterations if tool intensive
            adjusted_max_iterations = complexity.max_iterations
            if complexity.tool_intensive and tools:
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
                    tools,
                    tool_executor
                )
                
                iterations.append(iteration)
                all_tool_results.extend(iteration.tool_results)
                
                # Check convergence (use adjusted max iterations)
                converged, reason = self.convergence_detector.check_convergence(
                    iterations,
                    adjusted_max_iterations,
                    has_tools=bool(tools)
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
            final_answer = await self._synthesize_final_answer(
                problem,
                iterations,
                all_tool_results,
                current_context,  # Pass current_context which has full_context_messages
                llm_profile,
                agent_config
            )
            
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
        """Execute a single reasoning iteration with tool support"""
        
        # Build prompt for this iteration
        prompt = self._build_iteration_prompt(
            iteration_num,
            problem,
            context,
            previous_iterations,
            complexity,
            agent_config,
            tools
        )
        
        # Call LLM with full context messages if available
        base_messages = context.get('full_context_messages')
        response = await self._call_llm(prompt, llm_profile, base_messages)
        
        # Parse response
        thought, tool_calls, evaluation, confidence, should_continue, knowledge = \
            self._parse_iteration_response(response, iteration_num, complexity.reasoning_strategy)
        
        # Execute tools if requested
        tool_results = []
        if tool_calls and tool_executor:
            for tool_call in tool_calls:
                try:
                    result = await tool_executor(tool_call.tool_name, tool_call.arguments)
                    tool_results.append(ToolResult(
                        tool_name=tool_call.tool_name,
                        result=result,
                        success=True
                    ))
                except Exception as e:
                    logger.error(f"Tool execution failed: {tool_call.tool_name} - {str(e)}")
                    tool_results.append(ToolResult(
                        tool_name=tool_call.tool_name,
                        result=None,
                        success=False,
                        error=str(e)
                    ))
        
        return ReasoningIteration(
            iteration_number=iteration_num,
            reasoning_type=complexity.reasoning_strategy,
            thought=thought,
            tool_calls=tool_calls,
            tool_results=tool_results,
            evaluation=evaluation,
            confidence=confidence,
            should_continue=should_continue,
            knowledge_gathered=knowledge
        )
    
    def _build_iteration_prompt(
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

"""
        
        # Add previous iterations summary
        if previous_iterations:
            prompt += "Previous reasoning and findings:\n"
            for prev in previous_iterations[-3:]:  # Show last 3 iterations
                prompt += f"\n- Iteration {prev.iteration_number}:\n"
                prompt += f"  Thought: {prev.thought[:200]}...\n"
                if prev.tool_results:
                    prompt += f"  Tools used: {', '.join([tr.tool_name for tr in prev.tool_results])}\n"
                if prev.knowledge_gathered:
                    prompt += f"  Learned: {prev.knowledge_gathered[:200]}...\n"
            prompt += "\n"
        
        # Add available tools
        if tools:
            prompt += "Available tools:\n"
            for tool in tools[:10]:  # Limit to avoid prompt overflow
                func = tool.get('function', {})
                prompt += f"- {func.get('name')}: {func.get('description', '')[:100]}\n"
            prompt += "\n"
        
        # Add context if available
        if context.get('memory_context'):
            prompt += f"Relevant memory: {context['memory_context'][:500]}\n\n"
        
        # Request structured response
        prompt += """Perform the next reasoning step. You MUST provide your response in this EXACT format:

THOUGHT: [Your detailed reasoning for this step - what do you need to figure out?]

TOOL_CALLS: [List any tools you need to call, one per line in format: tool_name(arg1="value1", arg2="value2")]
[Leave empty if no tools needed this iteration]

EVALUATION: [Self-evaluation of your progress - what have you learned so far?]

CONFIDENCE: [A number between 0 and 1 indicating confidence in having enough information]

SHOULD_CONTINUE: [true if you need more information/iterations, false if you have everything needed]

KNOWLEDGE_GATHERED: [Brief summary of key facts/data gathered so far]

Important:
- Use tools when you need to search for information, verify facts, or perform calculations
- Be thorough but concise
- Focus on gathering information before making conclusions
- Only set SHOULD_CONTINUE to false when you have all necessary information"""
        
        return prompt
    
    async def _call_llm(self, prompt: str, llm_profile: Any, base_messages: List[Dict[str, Any]] = None) -> str:
        """Make a call to the LLM"""
        import httpx
        
        try:
            endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            # Use base messages if provided (contains full context), otherwise create new
            if base_messages:
                # Use the full context messages and add our iteration prompt
                messages = base_messages.copy()
                messages.append({"role": "user", "content": prompt})
            else:
                messages = [
                    {"role": "system", "content": "You are performing systematic chain of thought reasoning. Use tools when needed to gather information."},
                    {"role": "user", "content": prompt}
                ]
            
            body = {
                "model": llm_profile.model,
                "messages": messages,
                "temperature": getattr(llm_profile, 'temperature', 0.7),
                "max_tokens": getattr(llm_profile, 'max_tokens', 2000)  # Use profile's max_tokens
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=body,
                    timeout=60.0
                )
                response.raise_for_status()
                
                result = response.json()
                return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
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
        
        # Build synthesis prompt
        synthesis_prompt = f"""Based on the following research and reasoning, provide a comprehensive answer to the question.

Original question: {problem}

Information gathered from tools:
"""
        
        # Add tool results
        for tool_result in all_tool_results:
            if tool_result.success and tool_result.result:
                synthesis_prompt += f"\n{tool_result.tool_name} result:\n{str(tool_result.result)[:1000]}\n"
        
        # Add key insights from iterations
        synthesis_prompt += "\nKey insights from reasoning:\n"
        for iteration in iterations:
            if iteration.knowledge_gathered:
                synthesis_prompt += f"- {iteration.knowledge_gathered}\n"
        
        synthesis_prompt += f"""
Agent personality: {agent_config.get('name', 'Assistant')}
Communication style: {json.dumps(agent_config.get('personality', {}).get('communication_style', 'clear and helpful'))}

Now provide a complete, well-structured answer that:
1. Directly answers the original question
2. Incorporates all the information gathered from tools
3. Is clear, comprehensive, and well-organized
4. Matches the agent's personality and expertise

Final answer:"""
        
        try:
            # Use the full context messages for synthesis too
            base_messages = context.get('full_context_messages')
            response = await self._call_llm(synthesis_prompt, llm_profile, base_messages)
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to synthesize final answer: {str(e)}")
            # Fallback: return the best knowledge we have
            if all_tool_results:
                result_summary = "Voici les informations trouvées:\n"
                for tool_result in all_tool_results:
                    if tool_result.success:
                        result_summary += f"\n{tool_result.tool_name}: {str(tool_result.result)[:500]}\n"
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
            "thought": iteration.thought[:200],
            "confidence": iteration.confidence,
            "tools_used": [tc.tool_name for tc in iteration.tool_calls],
            "knowledge": iteration.knowledge_gathered
        })
        
        return updated
    
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
            content = msg.get('content', '')[:100]
            summary += f"- {role}: {content}...\n"
        
        return summary


# Create singleton instance
adaptive_cot_engine = AdaptiveChainOfThought()