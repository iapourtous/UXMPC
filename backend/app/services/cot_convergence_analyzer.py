"""
Convergence Analyzer for COT Adaptive Engine
Analyzes why convergence failed and suggests recovery strategies
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
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


class ConvergenceAnalyzer:
    """Analyzes why convergence failed and suggests recovery strategies"""
    
    def __init__(self):
        self.failure_patterns = {
            'contradictory_info': 0,
            'tool_failures': 0,
            'ambiguous_question': 0,
            'insufficient_data': 0,
            'oscillating_confidence': 0,
            'stuck_reasoning': 0
        }
    
    async def analyze_failure(
        self,
        iterations: List[ReasoningIteration],
        problem: str,
        llm_profile: Any
    ) -> Dict[str, Any]:
        """Analyze why convergence failed
        
        Returns:
            Analysis with failure type and suggested strategy
        """
        analysis = {
            'failure_type': None,
            'confidence_trend': [],
            'tool_failure_rate': 0,
            'reasoning_patterns': [],
            'suggested_strategy': None,
            'details': {}
        }
        
        # Analyze confidence trend
        confidences = [it.confidence for it in iterations]
        analysis['confidence_trend'] = confidences
        
        # Check for oscillating confidence (up and down pattern)
        if len(confidences) > 3:
            changes = [confidences[i+1] - confidences[i] for i in range(len(confidences)-1)]
            sign_changes = sum(1 for i in range(len(changes)-1) if changes[i] * changes[i+1] < 0)
            if sign_changes >= 2:
                self.failure_patterns['oscillating_confidence'] += 1
                analysis['failure_type'] = 'oscillating_confidence'
        
        # Check for stuck reasoning (confidence not improving)
        if len(confidences) > 3:
            recent_confidences = confidences[-3:]
            if max(recent_confidences) - min(recent_confidences) < 0.05:
                self.failure_patterns['stuck_reasoning'] += 1
                analysis['failure_type'] = 'stuck_reasoning'
        
        # Analyze tool failures
        total_tool_calls = sum(len(it.tool_calls) for it in iterations)
        failed_tool_calls = sum(
            1 for it in iterations 
            for tr in it.tool_results 
            if not tr.success
        )
        
        if total_tool_calls > 0:
            analysis['tool_failure_rate'] = failed_tool_calls / total_tool_calls
            if analysis['tool_failure_rate'] > 0.5:
                self.failure_patterns['tool_failures'] += 1
                analysis['failure_type'] = 'tool_failures'
        
        # Check for contradictory information
        thoughts = [it.thought for it in iterations]
        if self._has_contradictions(thoughts):
            self.failure_patterns['contradictory_info'] += 1
            analysis['failure_type'] = 'contradictory_info'
        
        # Check if question might be ambiguous (low initial confidence)
        if iterations and iterations[0].confidence < 0.5:
            self.failure_patterns['ambiguous_question'] += 1
            analysis['failure_type'] = 'ambiguous_question'
        
        # Check for insufficient data (tools not finding info)
        if total_tool_calls > 3 and all(it.confidence < 0.7 for it in iterations):
            self.failure_patterns['insufficient_data'] += 1
            analysis['failure_type'] = 'insufficient_data'
        
        # Determine recovery strategy based on failure type
        analysis['suggested_strategy'] = self._suggest_strategy(analysis['failure_type'])
        
        return analysis
    
    def _has_contradictions(self, thoughts: List[str]) -> bool:
        """Check if thoughts contain contradictory statements"""
        # Simple heuristic: look for contradiction keywords
        contradiction_keywords = [
            'however', 'but', 'contrary', 'opposite', 'conflict',
            'contradict', 'disagree', 'inconsistent', 'paradox'
        ]
        
        combined_text = ' '.join(thoughts).lower()
        contradiction_count = sum(
            1 for keyword in contradiction_keywords 
            if keyword in combined_text
        )
        
        return contradiction_count >= 3
    
    def _suggest_strategy(self, failure_type: str) -> str:
        """Suggest recovery strategy based on failure type"""
        strategies = {
            'oscillating_confidence': 'consensus',
            'stuck_reasoning': 'deep_dive',
            'tool_failures': 'fallback',
            'contradictory_info': 'consensus',
            'ambiguous_question': 'clarification',
            'insufficient_data': 'deep_dive'
        }
        
        return strategies.get(failure_type, 'deep_dive')