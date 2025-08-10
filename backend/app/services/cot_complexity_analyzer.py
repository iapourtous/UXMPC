"""
Complexity Analyzer for Adaptive Chain of Thought
Inspired by Auto-CoT approach for automatic complexity detection
"""
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ProblemCluster(str, Enum):
    """Problem categories based on complexity and type"""
    SIMPLE = "simple"           # Direct questions, simple lookup
    ARITHMETIC = "arithmetic"   # Mathematical calculations
    LOGICAL = "logical"         # Logical reasoning, syllogisms
    MULTI_STEP = "multi_step"   # Complex multi-step problems
    CREATIVE = "creative"       # Open-ended creative tasks
    ANALYTICAL = "analytical"   # Data analysis, pattern recognition


@dataclass
class ComplexityProfile:
    """Profile describing problem complexity"""
    cluster: ProblemCluster
    estimated_steps: int
    max_iterations: int
    reasoning_strategy: str
    diversity_factor: float  # How many different approaches to try
    features: Dict[str, any]


class ComplexityAnalyzer:
    """
    Analyzes problem complexity to determine optimal reasoning approach
    Based on Auto-CoT's clustering approach
    """
    
    def __init__(self):
        # Keywords for different problem types
        self.logical_keywords = [
            'if', 'then', 'all', 'some', 'none', 'every', 'any',
            'implies', 'therefore', 'thus', 'hence', 'because',
            'consequences', 'implications', 'would', 'could', 'should',
            'assuming', 'given that', 'suppose', 'hypothetically'
        ]
        
        self.math_keywords = [
            'calculate', 'compute', 'solve', 'equation', 'sum', 'product',
            'divide', 'multiply', 'add', 'subtract', 'percent', 'ratio'
        ]
        
        self.creative_keywords = [
            'create', 'design', 'imagine', 'invent', 'suggest', 'brainstorm',
            'generate', 'write', 'compose', 'develop'
        ]
        
        self.analytical_keywords = [
            'analyze', 'compare', 'evaluate', 'assess', 'examine',
            'investigate', 'study', 'review', 'critique', 'explain',
            'why', 'how', 'relationship', 'interaction', 'affect',
            'impact', 'influence', 'cause', 'effect'
        ]
    
    async def analyze_problem(self, problem: str, context: Optional[Dict] = None) -> ComplexityProfile:
        """
        Main method to analyze problem complexity
        """
        features = self.extract_features(problem)
        cluster = self.cluster_problem(features)
        
        return ComplexityProfile(
            cluster=cluster,
            estimated_steps=self.estimate_steps(cluster, features),
            max_iterations=self.compute_max_iterations(features, cluster),
            reasoning_strategy=self.select_strategy(cluster),
            diversity_factor=self.compute_diversity_factor(features),
            features=features
        )
    
    def extract_features(self, problem: str) -> Dict[str, any]:
        """
        Extract features from the problem text
        """
        problem_lower = problem.lower()
        
        features = {
            'length': len(problem),
            'sentence_count': len(problem.split('.')),
            'question_marks': problem.count('?'),
            'has_math': any(keyword in problem_lower for keyword in self.math_keywords),
            'has_logical_operators': any(keyword in problem_lower for keyword in self.logical_keywords),
            'has_creative_task': any(keyword in problem_lower for keyword in self.creative_keywords),
            'has_analytical_task': any(keyword in problem_lower for keyword in self.analytical_keywords),
            'entity_count': self.count_entities(problem),
            'has_nested_conditions': self.detect_nested_conditions(problem_lower),
            'requires_calculation': self.detect_calculation_need(problem_lower),
            'has_constraints': 'must' in problem_lower or 'should' in problem_lower or 'cannot' in problem_lower,
            'is_comparison': 'compare' in problem_lower or 'difference' in problem_lower,
            'requires_memory': 'remember' in problem_lower or 'recall' in problem_lower or 'last time' in problem_lower,
            'has_numbers': bool(re.findall(r'\d+', problem)),
            'equation_count': len(re.findall(r'[+\-*/=]', problem))
        }
        
        return features
    
    def count_entities(self, text: str) -> int:
        """
        Count named entities in the text (simplified)
        """
        # Count capitalized words that aren't at sentence start
        sentences = text.split('.')
        entity_count = 0
        
        for sentence in sentences:
            words = sentence.strip().split()
            if len(words) > 1:
                # Count capitalized words after the first word
                entity_count += sum(1 for word in words[1:] if word and word[0].isupper())
        
        # Also count quoted items
        entity_count += len(re.findall(r'"[^"]*"', text))
        
        return entity_count
    
    def detect_nested_conditions(self, text: str) -> bool:
        """
        Detect if problem has nested conditional logic
        """
        # Look for multiple conditional keywords
        conditionals = ['if', 'when', 'unless', 'provided', 'given that']
        count = sum(1 for cond in conditionals if cond in text)
        return count > 1
    
    def detect_calculation_need(self, text: str) -> bool:
        """
        Detect if problem requires mathematical calculation
        """
        calc_patterns = [
            r'\d+\s*[+\-*/]\s*\d+',  # Basic arithmetic
            r'how many', r'how much',
            r'total', r'sum', r'difference',
            r'percentage', r'ratio'
        ]
        
        return any(re.search(pattern, text) for pattern in calc_patterns)
    
    def cluster_problem(self, features: Dict) -> ProblemCluster:
        """
        Classify problem into a cluster based on features
        Inspired by Auto-CoT's clustering approach
        """
        # Priority-based classification
        
        # Check for mathematical problems first
        if features['has_math'] and (features['equation_count'] > 0 or features['requires_calculation']):
            return ProblemCluster.ARITHMETIC
        
        # Check for logical reasoning (relaxed conditions)
        if features['has_logical_operators'] or features['has_nested_conditions']:
            return ProblemCluster.LOGICAL
        
        # Check for creative tasks
        if features['has_creative_task']:
            return ProblemCluster.CREATIVE
        
        # Check for analytical tasks
        if features['has_analytical_task'] or features['is_comparison']:
            return ProblemCluster.ANALYTICAL
        
        # Check for multi-step based on complexity (more sensitive)
        if (features['entity_count'] > 1 or 
            features['sentence_count'] > 1 or
            features['has_nested_conditions'] or
            features['length'] > 150):  # Longer questions are often complex
            return ProblemCluster.MULTI_STEP
        
        # Default to simple
        return ProblemCluster.SIMPLE
    
    def estimate_steps(self, cluster: ProblemCluster, features: Dict) -> int:
        """
        Estimate the number of reasoning steps needed
        """
        base_steps = {
            ProblemCluster.SIMPLE: 2,
            ProblemCluster.ARITHMETIC: 4,
            ProblemCluster.LOGICAL: 5,
            ProblemCluster.MULTI_STEP: 6,
            ProblemCluster.CREATIVE: 4,
            ProblemCluster.ANALYTICAL: 5
        }
        
        steps = base_steps.get(cluster, 3)
        
        # Adjust based on specific features
        if features['entity_count'] > 3:
            steps += 1
        
        if features['has_nested_conditions']:
            steps += 2
        
        if features['has_constraints']:
            steps += 1
        
        return steps
    
    def compute_max_iterations(self, features: Dict, cluster: ProblemCluster) -> int:
        """
        Compute maximum iterations allowed
        Adaptive based on problem complexity
        """
        # Base iterations by cluster
        base_iterations = {
            ProblemCluster.SIMPLE: 3,
            ProblemCluster.ARITHMETIC: 5,
            ProblemCluster.LOGICAL: 7,
            ProblemCluster.MULTI_STEP: 10,
            ProblemCluster.CREATIVE: 6,
            ProblemCluster.ANALYTICAL: 8
        }
        
        iterations = base_iterations.get(cluster, 5)
        
        # Add iterations for complexity indicators
        if features['entity_count'] > 2:
            iterations += features['entity_count'] - 2
        
        if features['has_nested_conditions']:
            iterations += 2
        
        if features['requires_calculation'] and features['has_numbers']:
            iterations += 1
        
        if features['length'] > 200:  # Long problems
            iterations += 2
        
        # Cap at reasonable maximum
        return min(iterations, 15)
    
    def select_strategy(self, cluster: ProblemCluster) -> str:
        """
        Select reasoning strategy based on problem cluster
        """
        strategies = {
            ProblemCluster.SIMPLE: "direct",
            ProblemCluster.ARITHMETIC: "step_by_step_calculation",
            ProblemCluster.LOGICAL: "logical_decomposition",
            ProblemCluster.MULTI_STEP: "hierarchical_decomposition",
            ProblemCluster.CREATIVE: "divergent_exploration",
            ProblemCluster.ANALYTICAL: "systematic_analysis"
        }
        
        return strategies.get(cluster, "standard")
    
    def compute_diversity_factor(self, features: Dict) -> float:
        """
        Compute how many different reasoning approaches to try
        Higher diversity for more complex/ambiguous problems
        """
        diversity = 1.0
        
        # Increase diversity for complex problems
        if features['has_nested_conditions']:
            diversity += 0.5
        
        if features['entity_count'] > 3:
            diversity += 0.3
        
        if features['has_creative_task']:
            diversity += 0.7  # Creative tasks benefit from diverse approaches
        
        if features['is_comparison']:
            diversity += 0.4  # Comparisons benefit from multiple perspectives
        
        # Cap diversity factor
        return min(diversity, 3.0)