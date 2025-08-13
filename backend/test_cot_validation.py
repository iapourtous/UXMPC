#!/usr/bin/env python3
"""
Test script for the COT validation system
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.cot_adaptive_engine import AdaptiveChainOfThought
from app.services.cot_complexity_analyzer import ComplexityProfile
from app.models.llm_profile import LLMProfile
from dataclasses import dataclass

# Mock LLM Profile for testing
@dataclass
class MockLLMProfile:
    name: str = "Test LLM"
    model: str = "gpt-4"
    api_key: str = "test-key"
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    temperature: float = 0.7
    max_tokens: int = 2000

async def test_validation():
    """Test the COT validation system"""
    
    print("Testing COT Validation System")
    print("=" * 50)
    
    # Initialize the engine
    engine = AdaptiveChainOfThought()
    
    # Create a test problem
    problem = "What is the capital of France and what is 2+2?"
    
    # Create mock context
    context = {
        "memory_context": "",
        "available_tools": ["memory_search", "calculate"],
        "has_memory": False
    }
    
    # Create mock LLM profile
    llm_profile = MockLLMProfile()
    
    # Create mock agent config
    agent_config = {
        "name": "Test Agent",
        "personality": {
            "communication_style": "clear and helpful"
        }
    }
    
    # Mock tools
    tools = [
        {
            "function": {
                "name": "memory_search",
                "description": "Search memory for information"
            }
        },
        {
            "function": {
                "name": "calculate",
                "description": "Perform calculations"
            }
        }
    ]
    
    # Mock tool executor
    async def mock_tool_executor(tool_name, arguments):
        if tool_name == "memory_search":
            return {"result": "Paris is the capital of France"}
        elif tool_name == "calculate":
            return {"result": 4}
        return {"error": "Unknown tool"}
    
    try:
        # Execute COT with validation
        result = await engine.execute(
            problem=problem,
            context=context,
            llm_profile=llm_profile,
            conversation_history=[],
            agent_config=agent_config,
            tools=tools,
            tool_executor=mock_tool_executor
        )
        
        print(f"\nCompleted in {result.total_iterations} iterations")
        print(f"Convergence reason: {result.convergence_reason}")
        print(f"Success: {result.success}")
        
        # Display iteration details
        print("\nIteration Details:")
        for iteration in result.iterations:
            print(f"\n  Iteration {iteration.iteration_number}:")
            print(f"    Valid: {iteration.is_valid}")
            print(f"    Correction attempts: {iteration.correction_attempts}")
            print(f"    Relevance: {iteration.relevance_score:.2f}")
            print(f"    Progress: {iteration.progress_score:.2f}")
            print(f"    Correctness: {iteration.correctness_score:.2f}")
            if iteration.validation_feedback:
                print(f"    Feedback: {iteration.validation_feedback[:100]}...")
        
        print(f"\nFinal Answer: {result.final_answer[:200]}...")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_validation())