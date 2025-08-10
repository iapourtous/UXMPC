"""
Demonstration Generator for diverse reasoning paths
Inspired by Auto-CoT's approach to generate varied demonstrations
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from app.services.cot_complexity_analyzer import ComplexityProfile, ProblemCluster


@dataclass
class ReasoningPath:
    """Represents a single reasoning path/demonstration"""
    strategy: str
    steps: List[str]
    confidence: float
    complexity_handled: float
    is_complete: bool


class DemonstrationGenerator:
    """
    Generates diverse reasoning demonstrations
    Based on Auto-CoT's diversity principle
    """
    
    def __init__(self):
        # Templates for different reasoning strategies
        self.templates = self._init_templates()
    
    def _init_templates(self) -> Dict[str, List[str]]:
        """Initialize reasoning templates for different strategies"""
        return {
            "decomposition": [
                "Let's break this problem into smaller parts:",
                "First, identify the main components:",
                "Now, analyze each component:",
                "Combine the insights:",
                "Form the conclusion:"
            ],
            "backward": [
                "Let's work backwards from what we want to find:",
                "What would need to be true for this?",
                "What conditions must be met?",
                "Trace back to the given information:",
                "Verify the reasoning chain:"
            ],
            "analogy": [
                "This problem is similar to:",
                "The key pattern here is:",
                "Applying the same logic:",
                "Adapting to this specific case:",
                "Therefore, the answer is:"
            ],
            "systematic": [
                "Let's examine this systematically:",
                "Step 1: Understand the requirements",
                "Step 2: Identify constraints",
                "Step 3: Generate possible solutions",
                "Step 4: Evaluate and select"
            ],
            "hypothesis": [
                "Let's form a hypothesis:",
                "Evidence supporting this:",
                "Evidence against this:",
                "Testing the hypothesis:",
                "Conclusion based on evidence:"
            ]
        }
    
    async def generate_diverse_demonstrations(
        self,
        problem: str,
        complexity: ComplexityProfile,
        context: Optional[Dict] = None
    ) -> List[ReasoningPath]:
        """
        Generate multiple diverse reasoning paths
        Key principle from Auto-CoT: diversity reduces error propagation
        """
        paths = []
        
        # Always start with decomposition (most general)
        paths.append(await self.generate_decomposition_path(problem, complexity))
        
        # Add strategy based on problem cluster
        if complexity.cluster == ProblemCluster.ARITHMETIC:
            paths.append(await self.generate_calculation_path(problem, complexity))
            if complexity.features.get('has_constraints'):
                paths.append(await self.generate_constraint_path(problem, complexity))
        
        elif complexity.cluster == ProblemCluster.LOGICAL:
            paths.append(await self.generate_logical_path(problem, complexity))
            paths.append(await self.generate_backward_reasoning(problem, complexity))
        
        elif complexity.cluster == ProblemCluster.CREATIVE:
            paths.append(await self.generate_analogy_path(problem, complexity))
            paths.append(await self.generate_brainstorm_path(problem, complexity))
        
        elif complexity.cluster == ProblemCluster.ANALYTICAL:
            paths.append(await self.generate_systematic_path(problem, complexity))
            paths.append(await self.generate_hypothesis_path(problem, complexity))
        
        elif complexity.cluster == ProblemCluster.MULTI_STEP:
            paths.append(await self.generate_hierarchical_path(problem, complexity))
            # Add backward reasoning for complex problems
            if complexity.features.get('has_nested_conditions'):
                paths.append(await self.generate_backward_reasoning(problem, complexity))
        
        # Filter and rank paths
        return self.select_best_paths(paths, complexity.diversity_factor)
    
    async def generate_decomposition_path(
        self, 
        problem: str, 
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate standard decomposition reasoning path"""
        steps = []
        template = self.templates["decomposition"]
        
        steps.append(f"{template[0]}\nProblem: {problem}")
        
        # Identify components based on complexity
        if complexity.features.get('entity_count', 0) > 0:
            steps.append(f"{template[1]}\n- Entities involved: [to be identified]")
        
        if complexity.features.get('has_constraints'):
            steps.append("- Constraints to consider: [to be identified]")
        
        if complexity.features.get('requires_calculation'):
            steps.append("- Calculations needed: [to be identified]")
        
        steps.append(template[2])
        steps.append(template[3])
        steps.append(template[4])
        
        return ReasoningPath(
            strategy="decomposition",
            steps=steps,
            confidence=0.8,
            complexity_handled=0.7,
            is_complete=False
        )
    
    async def generate_backward_reasoning(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate backward reasoning path"""
        steps = []
        template = self.templates["backward"]
        
        steps.append(f"{template[0]}\nProblem: {problem}")
        steps.append(template[1])
        
        if complexity.features.get('has_logical_operators'):
            steps.append("- Logical conditions that must hold")
        
        steps.extend(template[2:])
        
        return ReasoningPath(
            strategy="backward",
            steps=steps,
            confidence=0.75,
            complexity_handled=0.8,
            is_complete=False
        )
    
    async def generate_calculation_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate calculation-focused reasoning path"""
        steps = [
            f"Let's solve this step by step:\nProblem: {problem}",
            "1. Identify the numbers and operations:",
            "2. Set up the calculation:",
            "3. Perform the computation:",
            "4. Verify the result:",
            "5. State the final answer:"
        ]
        
        return ReasoningPath(
            strategy="calculation",
            steps=steps,
            confidence=0.85,
            complexity_handled=0.9,
            is_complete=False
        )
    
    async def generate_logical_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate logical reasoning path"""
        steps = [
            f"Let's analyze this logically:\nProblem: {problem}",
            "1. Identify the premises:",
            "2. Identify the logical relationships:",
            "3. Apply logical rules:",
            "4. Check for validity:",
            "5. Draw conclusion:"
        ]
        
        return ReasoningPath(
            strategy="logical",
            steps=steps,
            confidence=0.8,
            complexity_handled=0.85,
            is_complete=False
        )
    
    async def generate_constraint_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate constraint-based reasoning path"""
        steps = [
            f"Let's identify and work with constraints:\nProblem: {problem}",
            "1. List all constraints:",
            "2. Check constraint compatibility:",
            "3. Find solution space:",
            "4. Apply constraints to narrow down:",
            "5. Identify valid solution:"
        ]
        
        return ReasoningPath(
            strategy="constraint",
            steps=steps,
            confidence=0.75,
            complexity_handled=0.8,
            is_complete=False
        )
    
    async def generate_analogy_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate analogy-based reasoning path"""
        steps = []
        template = self.templates["analogy"]
        
        steps.append(f"{template[0]}\nProblem: {problem}")
        steps.extend(template[1:])
        
        return ReasoningPath(
            strategy="analogy",
            steps=steps,
            confidence=0.7,
            complexity_handled=0.6,
            is_complete=False
        )
    
    async def generate_brainstorm_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate brainstorming path for creative problems"""
        steps = [
            f"Let's brainstorm solutions:\nProblem: {problem}",
            "1. Generate multiple ideas:",
            "2. Consider unconventional approaches:",
            "3. Combine different concepts:",
            "4. Evaluate feasibility:",
            "5. Select best approach:"
        ]
        
        return ReasoningPath(
            strategy="brainstorm",
            steps=steps,
            confidence=0.65,
            complexity_handled=0.7,
            is_complete=False
        )
    
    async def generate_systematic_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate systematic analysis path"""
        steps = []
        template = self.templates["systematic"]
        
        steps.append(f"{template[0]}\nProblem: {problem}")
        steps.extend(template[1:])
        
        return ReasoningPath(
            strategy="systematic",
            steps=steps,
            confidence=0.8,
            complexity_handled=0.75,
            is_complete=False
        )
    
    async def generate_hypothesis_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate hypothesis-testing path"""
        steps = []
        template = self.templates["hypothesis"]
        
        steps.append(f"{template[0]}\nProblem: {problem}")
        steps.extend(template[1:])
        
        return ReasoningPath(
            strategy="hypothesis",
            steps=steps,
            confidence=0.75,
            complexity_handled=0.8,
            is_complete=False
        )
    
    async def generate_hierarchical_path(
        self,
        problem: str,
        complexity: ComplexityProfile
    ) -> ReasoningPath:
        """Generate hierarchical decomposition for complex multi-step problems"""
        steps = [
            f"Let's tackle this complex problem hierarchically:\nProblem: {problem}",
            "1. High-level breakdown:",
            "   a. Main goal:",
            "   b. Sub-goals:",
            "2. Dependencies between parts:",
            "3. Solve sub-problems:",
            "   a. Sub-problem 1:",
            "   b. Sub-problem 2:",
            "4. Integrate solutions:",
            "5. Verify overall solution:"
        ]
        
        return ReasoningPath(
            strategy="hierarchical",
            steps=steps,
            confidence=0.75,
            complexity_handled=0.85,
            is_complete=False
        )
    
    def select_best_paths(
        self,
        paths: List[ReasoningPath],
        diversity_factor: float
    ) -> List[ReasoningPath]:
        """
        Select the best paths based on diversity factor
        Key insight from Auto-CoT: diversity helps mitigate errors
        """
        # Sort by confidence * complexity_handled
        paths.sort(key=lambda p: p.confidence * p.complexity_handled, reverse=True)
        
        # Determine how many paths to keep based on diversity factor
        num_paths = min(int(diversity_factor + 0.5), len(paths))
        num_paths = max(1, num_paths)  # At least one path
        
        # If we want high diversity, also ensure different strategies
        if diversity_factor > 1.5 and len(paths) > 2:
            # Keep best path and add diverse strategies
            selected = [paths[0]]
            seen_strategies = {paths[0].strategy}
            
            for path in paths[1:]:
                if len(selected) >= num_paths:
                    break
                if path.strategy not in seen_strategies:
                    selected.append(path)
                    seen_strategies.add(path.strategy)
            
            # Fill remaining slots with best paths
            for path in paths[1:]:
                if len(selected) >= num_paths:
                    break
                if path not in selected:
                    selected.append(path)
            
            return selected
        else:
            # Simply take the top paths
            return paths[:num_paths]