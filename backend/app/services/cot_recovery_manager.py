"""
Recovery Manager for COT Adaptive Engine
Handles recovery iterations when convergence fails
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from app.core.prompt_loader import PromptLoader
from app.services.unified_logger import UnifiedLogger

logger = logging.getLogger(__name__)


@dataclass
class ReasoningIteration:
    """Single iteration in the reasoning chain"""
    iteration_number: int
    reasoning_type: str
    thought: str
    tool_calls: List[Any]
    tool_results: List[Any]
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


class RecoveryManager:
    """Manages recovery iterations with specific strategies"""
    
    def __init__(self, prompt_loader: PromptLoader = None):
        """Initialize recovery manager"""
        self.prompt_loader = prompt_loader or PromptLoader()
    
    async def execute_recovery_iterations(
        self,
        strategy: str,
        previous_iterations: List[ReasoningIteration],
        problem: str,
        context: Dict[str, Any],
        complexity: Any,
        llm_profile: Any,
        agent_config: Dict[str, Any],
        tools: List[Dict[str, Any]],
        tool_executor,
        unified_logger: UnifiedLogger,
        execute_iteration_callback
    ) -> List[ReasoningIteration]:
        """Execute recovery iterations with a specific strategy
        
        Args:
            strategy: Recovery strategy to use
            previous_iterations: Previous failed iterations
            problem: Original problem
            context: Current context
            complexity: Complexity profile
            llm_profile: LLM profile
            agent_config: Agent configuration
            tools: Available tools
            tool_executor: Tool executor function
            unified_logger: Logger
            execute_iteration_callback: Callback to execute single iteration
            
        Returns:
            List of recovery iterations
        """
        recovery_iterations = []
        max_recovery = 5  # Maximum recovery iterations
        
        # Build recovery context based on strategy
        recovery_context = await self._build_recovery_context(
            strategy, previous_iterations, problem, context
        )
        
        # Update context with recovery information
        enhanced_context = {**context}
        enhanced_context['recovery_mode'] = True
        enhanced_context['recovery_strategy'] = strategy
        enhanced_context['recovery_context'] = recovery_context
        
        # Determine number of recovery iterations based on strategy
        recovery_count = {
            'clarification': 3,
            'deep_dive': 5,
            'consensus': 3,
            'fallback': 2
        }.get(strategy, 3)
        
        recovery_count = min(recovery_count, max_recovery)
        
        await unified_logger.info(
            f"Starting {recovery_count} recovery iterations with {strategy} strategy"
        )
        
        # Execute recovery iterations
        for i in range(1, recovery_count + 1):
            iteration_num = len(previous_iterations) + len(recovery_iterations) + 1
            
            # Build recovery-specific prompt
            recovery_prompt = await self._build_recovery_prompt(
                strategy,
                problem,
                previous_iterations + recovery_iterations,
                recovery_context
            )
            
            # Inject recovery prompt into context
            enhanced_context['recovery_prompt'] = recovery_prompt
            
            # Execute iteration with recovery context (using callback)
            iteration = await execute_iteration_callback(
                iteration_num,
                problem,
                enhanced_context,
                previous_iterations + recovery_iterations,
                complexity,
                llm_profile,
                agent_config,
                tools,
                tool_executor,
                unified_logger
            )
            
            # Mark as recovery iteration
            iteration.reasoning_type = f"recovery_{strategy}"
            recovery_iterations.append(iteration)
            
            # Check if recovery is succeeding
            if iteration.confidence >= 0.90:
                await unified_logger.info(
                    f"Recovery successful after {i} iterations",
                    confidence=iteration.confidence
                )
                break
            
            # Update context for next recovery iteration
            enhanced_context = self._update_context(enhanced_context, iteration)
        
        return recovery_iterations
    
    async def _build_recovery_context(
        self,
        strategy: str,
        iterations: List[ReasoningIteration],
        problem: str,
        context: Dict[str, Any]
    ) -> str:
        """Build context for recovery strategy"""
        
        context_parts = []
        
        if strategy == 'clarification':
            context_parts.append("## Recovery Strategy: CLARIFICATION")
            context_parts.append("The question seems ambiguous. Focus on:")
            context_parts.append("- Identifying specific aspects that need clarification")
            context_parts.append("- Breaking down the question into clear sub-questions")
            context_parts.append("- Making reasonable assumptions explicitly")
            
        elif strategy == 'deep_dive':
            context_parts.append("## Recovery Strategy: DEEP DIVE")
            context_parts.append("Insufficient information found. Focus on:")
            context_parts.append("- Exploring alternative information sources")
            context_parts.append("- Using different search terms or approaches")
            context_parts.append("- Combining partial information creatively")
            
        elif strategy == 'consensus':
            context_parts.append("## Recovery Strategy: CONSENSUS")
            context_parts.append("Contradictory information detected. Focus on:")
            context_parts.append("- Identifying the contradictions explicitly")
            context_parts.append("- Evaluating source reliability")
            context_parts.append("- Finding a balanced, nuanced answer")
            
        elif strategy == 'fallback':
            context_parts.append("## Recovery Strategy: FALLBACK")
            context_parts.append("Tool failures detected. Focus on:")
            context_parts.append("- Using general knowledge and reasoning")
            context_parts.append("- Working with available information only")
            context_parts.append("- Providing best-effort answer with caveats")
        
        # Add summary of previous attempts
        context_parts.append("\n## Previous Attempts Summary:")
        for i, it in enumerate(iterations[-3:], 1):  # Last 3 iterations
            context_parts.append(f"{i}. Confidence: {it.confidence:.0%} - {it.thought[:100]}...")
        
        return "\n".join(context_parts)
    
    async def _build_recovery_prompt(
        self,
        strategy: str,
        problem: str,
        iterations: List[ReasoningIteration],
        recovery_context: str
    ) -> str:
        """Build recovery-specific prompt from template files"""
        
        # Try to load recovery prompt from file using PromptLoader
        try:
            prompt_template = self.prompt_loader.load_prompt(f'cot/recovery_{strategy}.txt')
            
            # Build previous summary for the template
            previous_summary = self._build_recovery_summary(iterations)
            
            # Format the template with context
            prompt = prompt_template.format(
                previous_summary=previous_summary
            )
            
            # Add the original question
            prompt += f"\n\n## Original Question:\n{problem}\n\n"
            
            # Add what has already been tried to avoid repetition
            prompt += "\n## ⚠️ IMPORTANT - Already Attempted (DO NOT REPEAT):\n"
            for it in iterations[-5:]:  # Last 5 iterations
                if it.tool_calls:
                    for tc in it.tool_calls:
                        args_str = ', '.join([f'{k}={v}' for k,v in tc.arguments.items()])
                        prompt += f"- {tc.tool_name}({args_str})\n"
            prompt += "\nYou MUST try different approaches or parameters.\n"
            
            prompt += "Your response:"
            
            return prompt
            
        except Exception as e:
            logger.debug(f"Failed to load recovery prompt template: {e}")
            # Fallback to inline prompt
            return self._build_fallback_recovery_prompt(
                strategy, problem, iterations, recovery_context
            )
    
    def _build_recovery_summary(self, iterations: List[ReasoningIteration]) -> str:
        """Build summary of previous iterations for recovery context"""
        if not iterations:
            return "No previous iterations"
        
        summary_parts = []
        
        # Add confidence trend
        confidences = [it.confidence for it in iterations]
        summary_parts.append(f"Confidence trend: {' → '.join([f'{c:.0%}' for c in confidences[-5:]])}")
        
        # Add recent thoughts
        summary_parts.append("\nRecent reasoning attempts:")
        for i, it in enumerate(iterations[-3:], 1):
            summary_parts.append(f"{i}. (Conf: {it.confidence:.0%}) {it.thought[:150]}...")
        
        # Add tool usage summary
        tool_usage = {}
        for it in iterations:
            for tc in it.tool_calls:
                tool_usage[tc.tool_name] = tool_usage.get(tc.tool_name, 0) + 1
        
        if tool_usage:
            summary_parts.append(f"\nTools used: {', '.join([f'{name}({count}x)' for name, count in tool_usage.items()])}")
        
        # Add failed attempts details
        summary_parts.append("\n⚠️ Failed attempts (DO NOT repeat these exact calls):")
        for it in iterations[-5:]:
            if it.tool_calls:
                for tc in it.tool_calls:
                    args_str = ', '.join([f'{k}={v}' for k,v in tc.arguments.items()])
                    summary_parts.append(f"  ❌ {tc.tool_name}({args_str})")
        
        return "\n".join(summary_parts)
    
    def _build_fallback_recovery_prompt(
        self,
        strategy: str,
        problem: str,
        iterations: List[ReasoningIteration],
        recovery_context: str
    ) -> str:
        """Fallback inline recovery prompt if file not found"""
        
        return f"""
{recovery_context}

## Original Question:
{problem}

## Recovery Strategy: {strategy.upper()}

You are in recovery mode. Your previous {len(iterations)} attempts have not reached sufficient confidence.
The highest confidence achieved was {max(it.confidence for it in iterations):.0%}.

Apply the {strategy} recovery strategy to achieve breakthrough:
- Be systematic and thorough
- Address identified issues
- Aim for >90% confidence
- Use different approaches than before

Think step by step and solve this problem.
"""
    
    def _update_context(self, context: Dict[str, Any], iteration: ReasoningIteration) -> Dict[str, Any]:
        """Update context after an iteration"""
        updated = {**context}
        
        # Add knowledge to accumulated facts
        if iteration.knowledge_gathered and iteration.knowledge_gathered != "None":
            if 'accumulated_facts' not in updated:
                updated['accumulated_facts'] = []
            updated['accumulated_facts'].append(iteration.knowledge_gathered)
        
        return updated