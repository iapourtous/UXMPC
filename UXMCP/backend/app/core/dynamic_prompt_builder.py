from app.models.service import Service
import inspect

def create_dynamic_prompt_function(service: Service):
    """Create a dynamic function with proper parameters for FastMCP prompts"""
    
    # Build parameter list from prompt_args
    params = []
    param_defaults = []
    annotations = {}
    
    for arg in service.prompt_args:
        param_name = arg.name
        
        # Map types
        python_type = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
        }.get(arg.type, str)
        
        annotations[param_name] = python_type
        
        # Create Parameter object
        if arg.required:
            params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=python_type
            ))
        else:
            params.append(inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=None,
                annotation=python_type
            ))
    
    # Create function with proper signature
    async def dynamic_prompt(**kwargs):
        """Dynamic prompt function"""
        return kwargs
    
    # Create a proper signature
    sig = inspect.Signature(params)
    dynamic_prompt.__signature__ = sig
    dynamic_prompt.__annotations__ = annotations
    dynamic_prompt.__name__ = f"prompt_{service.name}"
    dynamic_prompt.__doc__ = f"Dynamic prompt: {service.name}"
    
    return dynamic_prompt