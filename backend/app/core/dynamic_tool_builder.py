"""
Dynamic tool builder for FastMCP that creates properly typed functions
"""
import inspect
from typing import Dict, Any, Optional, get_type_hints
from pydantic import create_model, Field
from app.models.service import Service, ServiceParam


def create_dynamic_tool_function(service: Service):
    """
    Create a dynamic function with proper type annotations for FastMCP
    This allows FastMCP to generate correct input schemas
    """
    
    # Build parameter annotations dynamically
    params_dict = {}
    annotations = {}
    
    for param in service.params:
        # Map service param types to Python types
        python_type = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }.get(param.type, str)
        
        # Add to annotations
        if param.required:
            annotations[param.name] = python_type
            params_dict[param.name] = inspect.Parameter(
                param.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=python_type
            )
        else:
            annotations[param.name] = Optional[python_type]
            params_dict[param.name] = inspect.Parameter(
                param.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Optional[python_type],
                default=None
            )
    
    # Create a dynamic function with proper signature
    async def dynamic_handler(**kwargs):
        # This will be replaced by the actual execution
        pass
    
    # Update function signature
    sig = inspect.Signature(parameters=list(params_dict.values()))
    dynamic_handler.__signature__ = sig
    dynamic_handler.__annotations__ = annotations
    
    # Set function name and docstring
    dynamic_handler.__name__ = f"{service.name}_handler"
    dynamic_handler.__doc__ = service.description or f"Handler for {service.name}"
    
    return dynamic_handler


