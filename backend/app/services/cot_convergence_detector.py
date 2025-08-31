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
        
        # PRIORITY 1: Check if current iteration confidence >= 90% - STOP IMMEDIATELY!
        if current_iteration.confidence >= 0.90:
            return True, f"High confidence reached ({current_iteration.confidence:.0%})"
        
        # PRIORITY 2: Check cumulative confidence
        if cumulative_confidence >= 0.90:
            return True, f"High cumulative confidence reached ({cumulative_confidence:.0%})"
        
        # Check max iterations - BUT check confidence first!
        if len(iterations) >= max_iterations:
            # Don't automatically converge - check if we actually have good CUMULATIVE confidence
            if cumulative_confidence >= self.confidence_threshold:
                return True, f"Reached maximum iterations ({max_iterations}) with good cumulative confidence ({cumulative_confidence:.0%})"
            else:
                # Return False to trigger recovery!
                return False, f"Reached maximum iterations ({max_iterations}) but low cumulative confidence ({cumulative_confidence:.0%})"
        
        # Already checked above - remove duplicate check
        
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
        
        # Check if agent decided to stop
        if not current_iteration.should_continue:
            # If confidence >= 90%, stop immediately
            if current_iteration.confidence >= 0.90:
                return True, f"Agent decided to stop with high confidence ({current_iteration.confidence:.0%})"
            # Otherwise check cumulative
            elif cumulative_confidence >= 0.90:
                return True, f"Agent determined answer is complete with high cumulative confidence ({cumulative_confidence:.0%})"
            # If confidence < 90%, don't converge even if agent wants to stop
        
        # Check confidence threshold (only after minimum iterations for moderate confidence)
        if cumulative_confidence >= self.confidence_threshold and len(iterations) >= 4:
            return True, f"High cumulative confidence reached ({cumulative_confidence:.0%})"
        
        # Don't converge too early - require at least 3 iterations for complex problems (unless confidence > 90%)
        if len(iterations) < 3 and cumulative_confidence < 0.90:
            return False, "Need more iterations for comprehensive analysis"
        
        return False, "Continue reasoning"
    
    def _calculate_cumulative_confidence(self, iterations: List[ReasoningIteration]) -> float:
        """
        Evaluate overall confidence based on ALL work done
        This is an EVALUATION, not an accumulation
        
        The confidence represents: "How confident are we that we have a good answer
        based on everything we've explored?"
        """
        if not iterations:
            return 0.0
        
        # Get the most recent iteration's confidence as the base
        # (it has the most complete view of all previous work)
        latest_confidence = iterations[-1].confidence
        
        # Evaluate the quality of the overall exploration
        quality_factors = []
        
        # 1. Did we gather substantial information?
        has_knowledge = any(
            it.knowledge_gathered and it.knowledge_gathered != "None" 
            for it in iterations
        )
        quality_factors.append(1.0 if has_knowledge else 0.5)
        
        # 2. Did tools provide useful results?
        successful_tools = sum(
            1 for it in iterations 
            for tr in it.tool_results 
            if tr.success
        )
        has_tool_success = successful_tools > 0
        quality_factors.append(1.0 if has_tool_success else 0.7)
        
        # 3. Is the reasoning consistent (not oscillating)?
        if len(iterations) >= 3:
            recent_confidences = [it.confidence for it in iterations[-3:]]
            variance = max(recent_confidences) - min(recent_confidences)
            is_stable = variance < 0.3  # Not oscillating wildly
            quality_factors.append(1.0 if is_stable else 0.8)
        else:
            quality_factors.append(0.9)  # Neutral for few iterations
        
        # 4. Have we explored enough iterations?
        exploration_completeness = min(len(iterations) / 5.0, 1.0)  # Up to 5 iterations is good
        quality_factors.append(exploration_completeness)
        
        # Calculate overall quality multiplier
        quality_multiplier = sum(quality_factors) / len(quality_factors)
        
        # Final confidence is the latest confidence adjusted by quality
        overall_confidence = latest_confidence * quality_multiplier
        
        # Ensure we stay within bounds [0, 1]
        return min(max(overall_confidence, 0.0), 1.0)