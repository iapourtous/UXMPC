"""
Complexity Analyzer for Adaptive Chain of Thought
Pure LLM-based analysis for intelligent complexity detection
"""
import json
import logging
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)


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
    # Core fields (backward compatible)
    cluster: ProblemCluster
    estimated_steps: int
    max_iterations: int
    reasoning_strategy: str
    diversity_factor: float
    
    # Enhanced fields for LLM-based analysis
    confidence_threshold: float = 0.90  # Changed from 0.85 to trigger recovery below 90%
    needs_tools: bool = False
    tool_intensive: bool = False
    key_challenges: list = field(default_factory=list)
    ambiguities: list = field(default_factory=list)
    
    # Legacy field for compatibility (always empty dict now)
    features: Dict[str, Any] = field(default_factory=dict)


class ComplexityAnalyzer:
    """
    LLM-based complexity analyzer for intelligent problem assessment
    Simple, efficient, and accurate
    """
    
    def __init__(self):
        self.analysis_cache = {}  # Simple cache for recent analyses
        self.cache_ttl = 300  # 5 minutes TTL
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load the analysis prompt template"""
        try:
            prompt_path = os.path.join(
                os.path.dirname(__file__),
                "..", "prompts", "cot", "analyze_complexity.txt"
            )
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"Could not load prompt template: {e}")
            # Fallback prompt if file not found
            return """Analyze this problem's complexity. Problem: {problem}
Context: {available_tools}, {has_memory}, {conversation_length}
Return JSON with: cluster, estimated_steps, max_iterations, reasoning_strategy, 
diversity_factor, confidence_threshold, needs_tools, tool_intensive, key_challenges, ambiguities"""
    
    async def analyze_problem(
        self, 
        problem: str, 
        context: Optional[Dict] = None,
        llm_profile: Optional[Any] = None
    ) -> ComplexityProfile:
        """
        Main method to analyze problem complexity using LLM
        
        Args:
            problem: The problem/question to analyze
            context: Additional context (tools, memory, etc.)
            llm_profile: LLM profile for making the analysis call
            
        Returns:
            ComplexityProfile with detailed analysis
        """
        # Check cache first
        cache_key = self._get_cache_key(problem)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.info("Using cached complexity analysis")
            return cached_result
        
        # If no LLM profile, return intelligent default
        if not llm_profile:
            logger.warning("No LLM profile provided, using default complexity profile")
            return self._get_default_profile()
        
        try:
            # Perform LLM analysis
            analysis = await self._llm_analyze(problem, context or {}, llm_profile)
            
            # Cache the result
            self._add_to_cache(cache_key, analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"LLM complexity analysis failed: {str(e)}", exc_info=True)
            return self._get_default_profile()
    
    async def _llm_analyze(
        self, 
        problem: str, 
        context: Dict,
        llm_profile: Any
    ) -> ComplexityProfile:
        """Perform LLM-based complexity analysis"""
        
        # Build the analysis prompt
        prompt = self._build_analysis_prompt(problem, context)
        
        # Make LLM call with optimized parameters
        response = await self._call_llm(
            prompt,
            llm_profile,
            temperature=0.3,  # Low temperature for consistent analysis
            max_tokens=None   # Use the model's default/configured max_tokens
        )
        
        # Parse the response using JSON extractor
        try:
            from app.core.json_extractor import extract_json_from_text
            
            # Extract JSON from the text response
            analysis = extract_json_from_text(response)
            
            if not analysis:
                # Try the legacy parsing as fallback
                logger.warning("Could not extract JSON using extractor, trying legacy parsing")
                # Sometimes the response starts with explanatory text
                if "{" in response:
                    json_start = response.index("{")
                    json_end = response.rindex("}") + 1
                    json_str = response[json_start:json_end]
                    analysis = json.loads(json_str)
                else:
                    logger.error(f"Could not extract JSON from response: {response[:500]}")
                    return self._get_default_profile()
            
            # Handle both dict and list responses
            if isinstance(analysis, list):
                # If it's a list, take the first item or create a default
                if analysis and isinstance(analysis[0], dict):
                    analysis = analysis[0]
                else:
                    logger.error(f"Unexpected list format in analysis: {analysis}")
                    return self._get_default_profile()
            elif not isinstance(analysis, dict):
                logger.error(f"Unexpected analysis type: {type(analysis)}")
                return self._get_default_profile()
            
            # Convert cluster string to enum
            cluster_str = analysis.get("cluster", "multi_step")
            # Normalize cluster string
            cluster_str = cluster_str.lower().replace("-", "_").replace(" ", "_")
            
            # Map to enum with all possible variations
            cluster_map = {
                "simple": ProblemCluster.SIMPLE,
                "arithmetic": ProblemCluster.ARITHMETIC,
                "logical": ProblemCluster.LOGICAL,
                "multi_step": ProblemCluster.MULTI_STEP,
                "multistep": ProblemCluster.MULTI_STEP,
                "multi step": ProblemCluster.MULTI_STEP,
                "creative": ProblemCluster.CREATIVE,
                "analytical": ProblemCluster.ANALYTICAL
            }
            cluster = cluster_map.get(cluster_str, ProblemCluster.MULTI_STEP)
            
            # Create ComplexityProfile with parsed data
            return ComplexityProfile(
                cluster=cluster,
                estimated_steps=int(analysis.get("estimated_steps", 5)),
                max_iterations=int(analysis.get("max_iterations", 7)),
                reasoning_strategy=str(analysis.get("reasoning_strategy", "decomposition")),
                diversity_factor=float(analysis.get("diversity_factor", 1.5)),
                confidence_threshold=float(analysis.get("confidence_threshold", 0.90)),
                needs_tools=bool(analysis.get("needs_tools", False)),
                tool_intensive=bool(analysis.get("tool_intensive", False)),
                key_challenges=list(analysis.get("key_challenges", [])),
                ambiguities=list(analysis.get("ambiguities", []))
            )
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            logger.error(f"Response was: {response[:500] if response else 'None'}")
            return self._get_default_profile()
    
    def _build_analysis_prompt(self, problem: str, context: Dict) -> str:
        """Build the analysis prompt with context"""
        
        # Extract context information
        available_tools = context.get("available_tools", [])
        has_memory = bool(context.get("memory_context"))
        conversation_length = len(context.get("conversation_history", []))
        
        # Format tools list
        tools_str = ", ".join(available_tools[:10]) if available_tools else "none"
        
        # Fill in the prompt template
        prompt = self.prompt_template.format(
            problem=problem,
            available_tools=tools_str,
            has_memory="yes" if has_memory else "no",
            conversation_length=conversation_length
        )
        
        return prompt
    
    async def _call_llm(
        self, 
        prompt: str, 
        llm_profile: Any,
        temperature: float = 0.3,
        max_tokens: int = None
    ) -> str:
        """Make a call to the LLM for analysis"""
        try:
            # Add explicit JSON formatting instructions
            enhanced_prompt = prompt + """

Please respond with a JSON object in the following format:
```json
{
    "cluster": "simple|arithmetic|logical|multi_step|creative|analytical",
    "estimated_steps": 5,
    "max_iterations": 7,
    "reasoning_strategy": "decomposition",
    "diversity_factor": 1.5,
    "confidence_threshold": 0.90,
    "needs_tools": false,
    "tool_intensive": false,
    "key_challenges": [],
    "ambiguities": []
}
```

IMPORTANT: Wrap your JSON response in a markdown code block as shown above."""
            
            # Use the model's configured max_tokens if not specified
            actual_max_tokens = max_tokens or llm_profile.max_tokens
            
            content = await llm_client.call_advanced(
                llm_profile=llm_profile,
                prompt=enhanced_prompt,
                system_message="You are an expert at analyzing problem complexity. Respond with valid JSON in a markdown code block.",
                temperature=temperature,
                max_tokens=actual_max_tokens,
                json_mode=False,  # Always use text mode
                timeout=10.0,
                raise_on_error=True
            )
            
            if not content:
                raise Exception("No content received from LLM")
                
            return content
                
        except Exception as e:
            logger.error(f"LLM call failed: {str(e)}")
            raise
    
    def _get_default_profile(self) -> ComplexityProfile:
        """Get a reasonable default complexity profile"""
        return ComplexityProfile(
            cluster=ProblemCluster.MULTI_STEP,
            estimated_steps=5,
            max_iterations=7,
            reasoning_strategy="decomposition",
            diversity_factor=1.5,
            confidence_threshold=0.90,
            needs_tools=True,
            tool_intensive=False,
            key_challenges=["Unknown problem complexity - using defaults"],
            ambiguities=[]
        )
    
    def _get_cache_key(self, problem: str) -> str:
        """Generate cache key for a problem"""
        # Use first 100 chars of problem for key
        return str(hash(problem[:100]))
    
    def _get_from_cache(self, cache_key: str) -> Optional[ComplexityProfile]:
        """Get analysis from cache if still valid"""
        if cache_key in self.analysis_cache:
            cached = self.analysis_cache[cache_key]
            if cached['expires'] > datetime.now():
                return cached['profile']
            else:
                # Expired, remove from cache
                del self.analysis_cache[cache_key]
        return None
    
    def _add_to_cache(self, cache_key: str, profile: ComplexityProfile):
        """Add analysis to cache with TTL"""
        self.analysis_cache[cache_key] = {
            'profile': profile,
            'expires': datetime.now() + timedelta(seconds=self.cache_ttl)
        }
        
        # Clean old entries if cache is getting large
        if len(self.analysis_cache) > 100:
            self._clean_cache()
    
    def _clean_cache(self):
        """Remove expired entries from cache"""
        now = datetime.now()
        expired_keys = [
            key for key, value in self.analysis_cache.items()
            if value['expires'] <= now
        ]
        for key in expired_keys:
            del self.analysis_cache[key]