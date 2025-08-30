"""
Convergence Detector for COT Adaptive Engine
Detects when reasoning has converged to a stable answer with cumulative confidence
"""
from typing import List, Tuple, Any, Optional
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


class ConvergenceDetector:
    """Detects when reasoning has converged to a stable answer"""
    
    def __init__(self):
        self.confidence_threshold = 0.90  # Changed from 0.85 to 0.90 to trigger recovery below 90%
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
        
        # Calculate cumulative confidence based on all iterations
        cumulative_confidence = self._calculate_cumulative_confidence(iterations)
        
        # Check max iterations - BUT check confidence first!
        if len(iterations) >= max_iterations:
            # Don't automatically converge - check if we actually have good CUMULATIVE confidence
            if cumulative_confidence >= self.confidence_threshold:
                return True, f"Reached maximum iterations ({max_iterations}) with good cumulative confidence ({cumulative_confidence:.0%})"
            else:
                # Return False to trigger recovery!
                return False, f"Reached maximum iterations ({max_iterations}) but low cumulative confidence ({cumulative_confidence:.0%})"
        
        # PRIORITY CHECK: Stop immediately if cumulative confidence > 90% (regardless of iteration count)
        if cumulative_confidence >= 0.90:
            return True, f"Very high cumulative confidence reached ({cumulative_confidence:.0%})"
        
        # If tools are available, ensure they've been used
        if has_tools:
            tool_calls_made = sum(len(it.tool_calls) for it in iterations)
            if tool_calls_made == 0 and len(iterations) < self.min_iterations_with_tools:
                return False, "Tools available but not yet used"
            
            # Check if we have enough information from tools
            # But require at least 3 iterations for moderate confidence
            if current_iteration.tool_results and len(iterations) >= 3:
                # If we got good results and high CUMULATIVE confidence
                if cumulative_confidence >= self.confidence_threshold:
                    return True, f"High cumulative confidence with tool results ({cumulative_confidence:.0%})"
        
        # Check if agent decided to stop (but require at least 3 iterations for moderate confidence)
        if not current_iteration.should_continue and len(iterations) >= 3:
            # Also check cumulative confidence
            if cumulative_confidence >= 0.75:  # Slightly lower threshold when agent wants to stop
                return True, f"Agent determined answer is complete with good cumulative confidence ({cumulative_confidence:.0%})"
        
        # Check confidence threshold (only after minimum iterations for moderate confidence)
        if cumulative_confidence >= self.confidence_threshold and len(iterations) >= 4:
            return True, f"High cumulative confidence reached ({cumulative_confidence:.0%})"
        
        # Don't converge too early - require at least 3 iterations for complex problems (unless confidence > 90%)
        if len(iterations) < 3 and cumulative_confidence < 0.90:
            return False, "Need more iterations for comprehensive analysis"
        
        return False, "Continue reasoning"
    
    def _calculate_cumulative_confidence(self, iterations: List[ReasoningIteration]) -> float:
        """
        Calculate cumulative confidence based on all iterations
        Takes into account:
        - Individual iteration confidences (weighted by recency)
        - Knowledge accumulation
        - Tool success rate
        - Consistency between iterations
        """
        if not iterations:
            return 0.0
        
        # 1. Weight recent iterations more heavily
        weights = []
        for i in range(len(iterations)):
            # Exponential decay: more recent = higher weight
            weight = 0.5 ** (len(iterations) - i - 1)
            weights.append(weight)
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # 2. Calculate weighted average of confidences
        weighted_confidence = sum(
            it.confidence * w 
            for it, w in zip(iterations, weights)
        )
        
        # 3. Boost for knowledge accumulation
        knowledge_boost = 0.0
        unique_knowledge = set()
        for it in iterations:
            if it.knowledge_gathered and it.knowledge_gathered != "None":
                unique_knowledge.add(it.knowledge_gathered[:100])  # Use first 100 chars as key
        
        # Each unique piece of knowledge adds a small boost
        knowledge_boost = min(len(unique_knowledge) * 0.03, 0.15)  # Max 15% boost
        
        # 4. Boost for successful tool usage
        tool_boost = 0.0
        total_tools = sum(len(it.tool_results) for it in iterations)
        successful_tools = sum(
            1 for it in iterations 
            for tr in it.tool_results 
            if tr.success
        )
        
        if total_tools > 0:
            tool_success_rate = successful_tools / total_tools
            tool_boost = tool_success_rate * 0.1  # Max 10% boost
        
        # 5. Penalty for contradictions or oscillations
        consistency_penalty = 0.0
        if len(iterations) > 2:
            # Check for large confidence swings
            confidences = [it.confidence for it in iterations]
            for i in range(1, len(confidences)):
                if abs(confidences[i] - confidences[i-1]) > 0.3:
                    consistency_penalty += 0.02  # 2% penalty per large swing
        
        consistency_penalty = min(consistency_penalty, 0.1)  # Max 10% penalty
        
        # 6. Combine all factors
        cumulative_confidence = weighted_confidence + knowledge_boost + tool_boost - consistency_penalty
        
        # 7. Apply minimum based on last iteration (can't be too much higher than recent confidence)
        # This prevents over-inflating confidence from old good iterations
        if iterations:
            recent_avg = sum(it.confidence for it in iterations[-3:]) / min(3, len(iterations))
            # Cumulative can be at most 20% higher than recent average
            cumulative_confidence = min(cumulative_confidence, recent_avg + 0.20)
        
        # Ensure in valid range [0, 1]
        return max(0.0, min(1.0, cumulative_confidence))