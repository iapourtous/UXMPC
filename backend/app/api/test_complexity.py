"""Test endpoint for complexity analyzer"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.cot_complexity_analyzer import ComplexityAnalyzer
from app.services.llm_crud import llm_crud
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class ComplexityTestRequest(BaseModel):
    problem: str
    context: Optional[Dict[str, Any]] = None
    llm_profile_name: Optional[str] = None
    llm_profile_id: Optional[str] = None


class ComplexityTestResponse(BaseModel):
    success: bool
    cluster: str
    estimated_steps: int
    max_iterations: int
    reasoning_strategy: str
    diversity_factor: float
    confidence_threshold: float
    needs_tools: bool
    tool_intensive: bool
    key_challenges: list
    ambiguities: list
    error: Optional[str] = None


@router.post("/test-complexity", response_model=ComplexityTestResponse)
async def test_complexity_analysis(request: ComplexityTestRequest):
    """
    Test endpoint for complexity analyzer
    
    Example:
    ```
    curl -X POST http://localhost:8000/api/test-complexity \
      -H "Content-Type: application/json" \
      -d '{
        "problem": "Quelle est la capitale de la France?",
        "llm_profile_name": "default"
      }'
    ```
    """
    try:
        # Get LLM profile if specified
        llm_profile = None
        if request.llm_profile_id:
            llm_profile = await llm_crud.get(request.llm_profile_id)
            if not llm_profile:
                return ComplexityTestResponse(
                    success=False,
                    cluster="unknown",
                    estimated_steps=0,
                    max_iterations=0,
                    reasoning_strategy="unknown",
                    diversity_factor=0,
                    confidence_threshold=0,
                    needs_tools=False,
                    tool_intensive=False,
                    key_challenges=[],
                    ambiguities=[],
                    error=f"LLM profile ID '{request.llm_profile_id}' not found"
                )
        elif request.llm_profile_name:
            llm_profile = await llm_crud.get_by_name(request.llm_profile_name)
            if not llm_profile:
                return ComplexityTestResponse(
                    success=False,
                    cluster="unknown",
                    estimated_steps=0,
                    max_iterations=0,
                    reasoning_strategy="unknown",
                    diversity_factor=0,
                    confidence_threshold=0,
                    needs_tools=False,
                    tool_intensive=False,
                    key_challenges=[],
                    ambiguities=[],
                    error=f"LLM profile '{request.llm_profile_name}' not found"
                )
        
        # Create analyzer and analyze
        analyzer = ComplexityAnalyzer()
        result = await analyzer.analyze_problem(
            problem=request.problem,
            context=request.context or {},
            llm_profile=llm_profile
        )
        
        # Return result
        return ComplexityTestResponse(
            success=True,
            cluster=result.cluster.value,
            estimated_steps=result.estimated_steps,
            max_iterations=result.max_iterations,
            reasoning_strategy=result.reasoning_strategy,
            diversity_factor=result.diversity_factor,
            confidence_threshold=result.confidence_threshold,
            needs_tools=result.needs_tools,
            tool_intensive=result.tool_intensive,
            key_challenges=result.key_challenges,
            ambiguities=result.ambiguities
        )
        
    except Exception as e:
        logger.error(f"Complexity test failed: {str(e)}", exc_info=True)
        return ComplexityTestResponse(
            success=False,
            cluster="unknown",
            estimated_steps=0,
            max_iterations=0,
            reasoning_strategy="unknown",
            diversity_factor=0,
            confidence_threshold=0,
            needs_tools=False,
            tool_intensive=False,
            key_challenges=[],
            ambiguities=[],
            error=str(e)
        )