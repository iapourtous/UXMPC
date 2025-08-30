"""
Prompt Builder for COT Adaptive Engine
Handles complex prompt construction and formatting
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from app.core.prompt_loader import PromptLoader
import logging

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


class PromptBuilder:
    """Handles all prompt construction for COT Adaptive Engine"""
    
    def __init__(self, prompt_loader: PromptLoader = None):
        """Initialize prompt builder"""
        self.prompt_loader = prompt_loader or PromptLoader()
    
    async def build_correction_prompt(
        self,
        original_response: str,
        validation_feedback: str,
        problem: str,
        attempt_number: int
    ) -> str:
        """Build prompt for correcting invalid reasoning"""
        
        prompt = self.prompt_loader.load_prompt('cot/correction_prompt.txt', {
            'original_response': original_response,
            'validation_feedback': validation_feedback,
            'problem': problem,
            'attempt_number': attempt_number
        })
        
        return prompt
    
    async def build_validation_prompt(
        self,
        response: str,
        problem: str,
        context: Dict[str, Any],
        previous_iterations: List[ReasoningIteration]
    ) -> str:
        """Build prompt for validating reasoning"""
        
        # Build context summary
        context_summary = ""
        if previous_iterations:
            context_summary = f"Previous {len(previous_iterations)} iterations completed."
            if len(previous_iterations) > 0:
                last_confidence = previous_iterations[-1].confidence
                context_summary += f" Last confidence: {last_confidence:.0%}"
        
        prompt = f"""## Validation Task

You are validating a reasoning step for the following problem:
{problem}

{context_summary}

## Response to Validate:
{response}

## Validation Criteria:
1. **Format**: Does the response follow the required format with THOUGHT, TOOL_CALLS, EVALUATION, CONFIDENCE, SHOULD_CONTINUE, and KNOWLEDGE_GATHERED sections?
2. **Relevance**: Is the reasoning relevant to solving the problem?
3. **Progress**: Does this step make meaningful progress?
4. **Correctness**: Is the reasoning logically sound?

Provide your validation in this format:

IS_VALID: [true/false]
RELEVANCE_SCORE: [0.0-1.0]
PROGRESS_SCORE: [0.0-1.0]
CORRECTNESS_SCORE: [0.0-1.0]
FEEDBACK: [If invalid or scores < 0.7, explain what needs improvement]
"""
        
        return prompt
    
    async def build_synthesis_prompt(
        self,
        problem: str,
        iterations: List[ReasoningIteration],
        tool_results: List[Any],
        context: Dict[str, Any],
        agent_config: Dict[str, Any]
    ) -> str:
        """Build prompt for final answer synthesis"""
        
        # Try to load from file first
        try:
            # Build iterations summary
            iterations_summary = await self._build_iterations_summary(iterations)
            
            # Build tool results summary
            tool_results_summary = await self._build_tool_results_summary(tool_results)
            
            prompt = self.prompt_loader.load_prompt('cot/synthesize_answer.txt', {
                'problem': problem,
                'iterations_summary': iterations_summary,
                'tool_results_summary': tool_results_summary
            })
            
            return prompt
            
        except FileNotFoundError:
            # Fallback to inline prompt
            return await self._build_inline_synthesis_prompt(
                problem, iterations, tool_results, context, agent_config
            )
    
    async def _build_iterations_summary(self, iterations: List[ReasoningIteration]) -> str:
        """Build summary of iterations for synthesis"""
        if not iterations:
            return "No iterations performed"
        
        summary_parts = []
        for it in iterations:
            summary_parts.append(f"Iteration {it.iteration_number} (Confidence: {it.confidence:.0%}):")
            summary_parts.append(f"  - {it.thought[:200]}...")
            if it.knowledge_gathered and it.knowledge_gathered != "None":
                summary_parts.append(f"  - Learned: {it.knowledge_gathered}")
        
        return "\n".join(summary_parts)
    
    async def _build_tool_results_summary(self, tool_results: List[Any]) -> str:
        """Build summary of tool results for synthesis"""
        if not tool_results:
            return "No tools were used"
        
        summary_parts = []
        tool_usage = {}
        
        for tr in tool_results:
            tool_name = tr.tool_name
            if tool_name not in tool_usage:
                tool_usage[tool_name] = []
            
            if tr.success and tr.result:
                result_str = str(tr.result)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "..."
                tool_usage[tool_name].append(result_str)
        
        for tool_name, results in tool_usage.items():
            summary_parts.append(f"{tool_name}:")
            for i, result in enumerate(results[:3], 1):  # Limit to 3 results per tool
                summary_parts.append(f"  {i}. {result}")
        
        return "\n".join(summary_parts)
    
    async def _build_inline_synthesis_prompt(
        self,
        problem: str,
        iterations: List[ReasoningIteration],
        tool_results: List[Any],
        context: Dict[str, Any],
        agent_config: Dict[str, Any]
    ) -> str:
        """Fallback inline synthesis prompt"""
        
        prompt = f"""## Synthesis Task

Based on the following reasoning chain and tool results, provide a comprehensive answer to the original question.

## Original Question:
{problem}

## Reasoning Summary:
{await self._build_iterations_summary(iterations)}

## Tool Results:
{await self._build_tool_results_summary(tool_results)}

## Instructions:
1. Synthesize all information gathered
2. Provide a clear, comprehensive answer
3. Include relevant details from tools
4. Be concise but complete

Your synthesized answer:"""
        
        return prompt
    
    def build_tool_execution_format(self) -> str:
        """Return the expected format for tool execution responses"""
        return """THOUGHT: [Your detailed reasoning for this step - what do you need to figure out?]

TOOL_CALLS: [List ALL tools you need, ONE PER LINE. You can use MULTIPLE tools!]
tool_name(arg1="value1", arg2="value2")
another_tool(param="value")
[Leave empty if no tools needed this iteration]

EVALUATION: [Self-evaluation of your progress - what have you learned so far?]

CONFIDENCE: [A number between 0 and 1 indicating confidence in having enough information]

SHOULD_CONTINUE: [true if you need more information/iterations, false if you have everything needed]

KNOWLEDGE_GATHERED: [Brief summary of key facts/data gathered so far]"""