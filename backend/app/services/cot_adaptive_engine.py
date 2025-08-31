"""
Adaptive Chain of Thought Engine - Main Orchestrator
Coordinates COT reasoning using specialized components
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import logging
import uuid

from app.services.cot_complexity_analyzer import ComplexityAnalyzer, ComplexityProfile
from app.services.cot_demonstration_generator import DemonstrationGenerator
from app.services.cot_convergence_analyzer import ConvergenceAnalyzer
from app.services.cot_convergence_detector import ConvergenceDetector
from app.services.cot_recovery_manager import RecoveryManager
from app.services.cot_prompt_builder import PromptBuilder
from app.services.cot_iteration_executor import IterationExecutor, ReasoningIteration
from app.services.cot_answer_synthesizer import AnswerSynthesizer
from app.services.cot_context_manager import ContextManager
from app.services.cot_tool_executor import ToolResult
from app.services.unified_logger import UnifiedLogger
from app.services.intrinsic_llm_tools import INTRINSIC_LLM_TOOLS
from app.core.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


@dataclass
class ChainOfThoughtResult:
    """Result from Chain of Thought execution"""
    final_answer: str
    iterations: List[ReasoningIteration]
    total_iterations: int
    complexity_profile: Optional[ComplexityProfile]
    convergence_reason: str
    success: bool
    all_tool_results: Optional[List[ToolResult]] = None


class AdaptiveChainOfThought:
    """
    Main adaptive Chain of Thought orchestrator
    Coordinates all components for reasoning with tool support
    """
    
    def __init__(self):
        """Initialize all COT components"""
        self.complexity_analyzer = ComplexityAnalyzer()
        self.demonstration_generator = DemonstrationGenerator()
        self.convergence_detector = ConvergenceDetector()
        self.convergence_analyzer = ConvergenceAnalyzer()
        self.recovery_manager = RecoveryManager()
        self.prompt_builder = PromptBuilder()
        self.iteration_executor = IterationExecutor()
        self.answer_synthesizer = AnswerSynthesizer()
        self.context_manager = ContextManager()
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
        Execute adaptive Chain of Thought reasoning
        
        Args:
            problem: The problem/question to solve
            context: Initial context including memory, tools, etc.
            llm_profile: LLM profile for making calls
            conversation_history: Previous conversation messages
            agent_config: Agent's 7D configuration
            tools: Available tools in OpenAI format
            tool_executor: Function to execute tool calls
            execution_id: Unique execution ID for logging
            
        Returns:
            ChainOfThoughtResult with answer and reasoning details
        """
        # Initialize unified logger
        from app.core.database import get_database
        db = get_database()
        
        execution_id = execution_id or str(uuid.uuid4())
        unified_logger = UnifiedLogger(
            f"cot_{execution_id}",
            f"COT: {problem[:50]}...",
            execution_id,
            db=db
        )
        
        await unified_logger.info(
            f"Starting Chain of Thought reasoning",
            problem=problem[:200],
            has_tools=bool(tools),
            llm_profile=llm_profile.name if hasattr(llm_profile, 'name') else str(llm_profile)
        )
        
        try:
            # Analyze problem complexity
            complexity = await self.complexity_analyzer.analyze_problem(problem, context, llm_profile)
            await unified_logger.info(
                f"Complexity analysis complete",
                reasoning_strategy=complexity.reasoning_strategy,
                estimated_steps=complexity.estimated_steps,
                confidence_threshold=complexity.confidence_threshold
            )
            
            # Generate demonstrations if needed
            demonstrations = []
            # Check if we need demonstrations based on complexity
            if complexity.estimated_steps > 3 or complexity.diversity_factor > 0.7:
                demonstrations = await self.demonstration_generator.generate_diverse_demonstrations(
                    problem,
                    complexity,
                    context
                )
                await unified_logger.info(f"Generated {len(demonstrations)} demonstration examples")
            
            # Merge intrinsic and external tools
            combined_tools = INTRINSIC_LLM_TOOLS.copy()
            if tools:
                combined_tools.extend(tools)
            
            # DEBUG: Log tools details
            logger.warning(f"DEBUG COT - INTRINSIC_LLM_TOOLS count: {len(INTRINSIC_LLM_TOOLS)}")
            logger.warning(f"DEBUG COT - External tools count: {len(tools) if tools else 0}")
            logger.warning(f"DEBUG COT - Combined tools count: {len(combined_tools)}")
            if combined_tools:
                logger.warning(f"DEBUG COT - First tool: {combined_tools[0].get('function', {}).get('name')}")
            
            await unified_logger.info(
                f"Tools prepared",
                intrinsic_tools=len(INTRINSIC_LLM_TOOLS),
                external_tools=len(tools) if tools else 0,
                total_tools=len(combined_tools)
            )
            
            # Initialize context
            current_context = self.context_manager.initialize_context(
                problem,
                context,
                conversation_history,
                agent_config,
                demonstrations,
                combined_tools  # Pass combined tools to context
            )
            
            # Update convergence detector threshold
            self.convergence_detector.confidence_threshold = complexity.confidence_threshold
            
            # Adjust max iterations for tool-intensive problems
            adjusted_max_iterations = complexity.max_iterations
            if complexity.tool_intensive and combined_tools:
                adjusted_max_iterations = min(complexity.max_iterations + 2, 15)
            
            # Main reasoning loop
            iterations = []
            all_tool_results = []
            converged = False
            reason = "Not started"
            
            for iteration_num in range(1, adjusted_max_iterations + 1):
                # Debug tools before passing to iteration
                await unified_logger.debug(
                    f"About to execute iteration {iteration_num}",
                    combined_tools_count=len(combined_tools) if combined_tools else 0,
                    combined_tools_type=type(combined_tools).__name__,
                    first_tool_name=combined_tools[0].get('function', {}).get('name') if combined_tools and len(combined_tools) > 0 else None,
                    has_tool_executor=tool_executor is not None
                )
                
                # Execute one reasoning iteration
                iteration = await self.iteration_executor.execute_iteration(
                    iteration_num,
                    problem,
                    current_context,
                    iterations,
                    complexity,
                    llm_profile,
                    agent_config,
                    combined_tools,
                    tool_executor,
                    unified_logger
                )
                
                iterations.append(iteration)
                all_tool_results.extend(iteration.tool_results)
                
                # Check convergence
                converged, reason = self.convergence_detector.check_convergence(
                    iterations,
                    adjusted_max_iterations,
                    has_tools=bool(combined_tools)
                )
                
                if converged:
                    await unified_logger.info(f"Convergence achieved: {reason}")
                    break
                
                # Update context for next iteration
                current_context = self.context_manager.update_context(
                    current_context,
                    iteration
                )
            
            await unified_logger.info(
                f"Main loop completed",
                converged=converged,
                reason=reason,
                iterations_count=len(iterations),
                max_iterations=adjusted_max_iterations
            )
            
            # Check if recovery is needed
            cumulative_confidence = self.convergence_detector._calculate_cumulative_confidence(iterations)
            if not converged and cumulative_confidence < 0.90:
                # Analyze failure and execute recovery
                failure_analysis = await self.convergence_analyzer.analyze_failure(
                    iterations, problem, llm_profile
                )
                
                await unified_logger.warning(
                    f"Convergence failed, attempting recovery",
                    strategy=failure_analysis['suggested_strategy'],
                    failure_type=failure_analysis['failure_type'],
                    cumulative_confidence=cumulative_confidence
                )
                
                # Execute recovery iterations
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
                    self.iteration_executor.execute_iteration
                )
                
                iterations.extend(recovery_iterations)
                all_tool_results.extend([
                    tr for it in recovery_iterations 
                    for tr in it.tool_results
                ])
                
                # Re-check convergence after recovery
                converged, reason = self.convergence_detector.check_convergence(
                    iterations,
                    adjusted_max_iterations + 5,
                    has_tools=bool(combined_tools)
                )
            
            # Synthesize final answer
            await unified_logger.info("Starting answer synthesis")
            
            # Pass the full current_context like the old code did, not a filtered version
            final_answer = await self.answer_synthesizer.synthesize_final_answer(
                problem,
                iterations,
                all_tool_results,
                current_context,  # Pass current_context which has full_context_messages
                llm_profile,
                agent_config
            )
            
            await unified_logger.info(
                "Chain of Thought completed successfully",
                total_iterations=len(iterations),
                convergence_reason=reason,
                answer_length=len(final_answer)
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
            logger.error(f"Chain of Thought execution failed: {str(e)}", exc_info=True)
            await unified_logger.error(
                f"Chain of Thought failed",
                error=str(e)
            )
            
            return ChainOfThoughtResult(
                final_answer=f"Je n'ai pas pu compléter le raisonnement : {str(e)}",
                iterations=[],
                total_iterations=0,
                complexity_profile=None,
                convergence_reason="Error occurred",
                success=False,
                all_tool_results=[]
            )


# Create an instance for backward compatibility
adaptive_cot_engine = AdaptiveChainOfThought()