import json
import re
import httpx
from typing import Dict, Any, List
from app.models.service import ServiceParam
from app.services.llm_crud import llm_crud
from app.core.prompt_manager import load_prompt
import logging

logger = logging.getLogger(__name__)

# Template examples based on existing services
TOOL_EXAMPLE = """
Example of a weather service:
```python
import random
from datetime import datetime

def handler(**params):
    city = params.get('city', 'Unknown')
    
    # Simulate weather data
    weather_conditions = ['Sunny', 'Cloudy', 'Rainy', 'Partly Cloudy', 'Snowy']
    temperature = random.randint(-10, 35)
    humidity = random.randint(30, 90)
    
    return {
        'city': city,
        'temperature': temperature,
        'unit': 'Celsius',
        'condition': random.choice(weather_conditions),
        'humidity': f'{humidity}%',
        'timestamp': datetime.utcnow().isoformat()
    }
```
This service takes a city parameter from the route and returns weather information.
"""

RESOURCE_EXAMPLE = """
Example of a system info resource:
```python
import platform
import os

def handler(**params):
    return {
        'content': f'''System Information
================

Platform: {platform.system()}
Python Version: {platform.python_version()}
Processor: {platform.processor()}
Machine: {platform.machine()}
Node: {platform.node()}

Environment Variables: {len(os.environ)} defined''',
        'mimeType': 'text/plain'
    }
```
Resources return content with a MIME type. No parameters needed for static resources.
"""

PROMPT_EXAMPLE = """
Example of a code review prompt:
```python
def handler(**params):
    language = params.get('language', 'unknown')
    code = params.get('code', '')
    focus = params.get('focus', 'general')
    
    template = f'''Please review the following {language} code:

```{language}
{code}
```

Focus areas: {focus}

Provide feedback on:
1. Code quality and best practices
2. Potential bugs or issues
3. Performance considerations
4. Security concerns
5. Suggestions for improvement'''
    
    return {'template': template}
```
Prompts return a template string that can include parameters.
"""

# This constant is now loaded from the prompt file



class ServiceGenerator:
    
    async def generate_service(self, service_data: Dict[str, Any], llm_profile_name: str) -> Dict[str, Any]:
        """Generate a complete service implementation using LLM"""
        
        # Get the LLM profile
        llm_profile = await llm_crud.get_by_name(llm_profile_name)
        if not llm_profile or not llm_profile.active:
            raise ValueError(f"LLM profile '{llm_profile_name}' not found or inactive")
        
        # Select appropriate example based on service type
        if service_data['service_type'] == 'tool':
            example = TOOL_EXAMPLE
        elif service_data['service_type'] == 'resource':
            example = RESOURCE_EXAMPLE
        elif service_data['service_type'] == 'prompt':
            example = PROMPT_EXAMPLE
        else:
            example = TOOL_EXAMPLE  # Default to tool
        
        # Build the generation prompt
        prompt = load_prompt(
            "service_generator/generation_prompt",
            name=service_data['name'],
            service_type=service_data['service_type'],
            route=service_data['route'],
            method=service_data.get('method', 'GET'),
            description=service_data['description'],
            example=example
        )
        
        try:
            # Call LLM API
            messages = []
            if llm_profile.system_prompt:
                messages.append({"role": "system", "content": llm_profile.system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {llm_profile.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": llm_profile.model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": llm_profile.max_tokens
            }
            
            # Use JSON mode if available
            if llm_profile.mode == "json":
                payload["response_format"] = {"type": "json_object"}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse the response
                if llm_profile.mode == "json":
                    generated = json.loads(content)
                else:
                    # Try to extract JSON from the response
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        generated = json.loads(json_match.group())
                    else:
                        # Fallback generation
                        return self._generate_fallback(service_data)
                
                # Post-process the generated data
                return self._post_process_generated(generated, service_data)
                
        except Exception as e:
            logger.error(f"Failed to generate service with LLM: {str(e)}")
            return self._generate_fallback(service_data)
    
    def _post_process_generated(self, generated: Dict[str, Any], service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process and validate generated service data"""
        
        # Ensure all required fields are present
        result = {
            "code": generated.get("code", self._get_default_code(service_data['service_type'])),
            "params": generated.get("params", []),
            "dependencies": generated.get("dependencies", []),
            "documentation": generated.get("documentation", f"Auto-generated {service_data['service_type']} service"),
        }
        
        # Extract parameters from route if not found
        route_params = self._extract_route_params(service_data['route'])
        existing_param_names = {p['name'] for p in result['params']}
        
        for param in route_params:
            if param not in existing_param_names:
                result['params'].append({
                    "name": param,
                    "type": "string",
                    "required": True,
                    "description": f"Parameter {param} from route"
                })
        
        # Add type-specific fields
        if service_data['service_type'] == 'tool':
            # Add output schema for tools
            result['output_schema'] = generated.get("output_schema", None)
        elif service_data['service_type'] == 'resource':
            result['mime_type'] = generated.get("mime_type", "text/plain")
        elif service_data['service_type'] == 'prompt':
            result['prompt_template'] = generated.get("prompt_template", "{input}")
            result['prompt_args'] = generated.get("prompt_args", [])
        
        return result
    
    def _extract_route_params(self, route: str) -> List[str]:
        """Extract parameter names from route pattern"""
        pattern = re.compile(r'\{(\w+)\}')
        return pattern.findall(route)
    
    def _get_default_code(self, service_type: str) -> str:
        """Get default code template for service type"""
        if service_type == 'tool':
            return """def handler(**params):
    # TODO: Implement your tool logic here
    return {"result": "Success", "params": params}"""
        elif service_type == 'resource':
            return """def handler(**params):
    # TODO: Implement your resource logic here
    return {
        "content": "Resource content",
        "mimeType": "text/plain"
    }"""
        elif service_type == 'prompt':
            return """def handler(**params):
    # TODO: Implement your prompt logic here
    input_text = params.get('input', '')
    return {"template": f"Process this: {input_text}"}"""
        return "def handler(**params):\n    return {}"
    
    def _generate_fallback(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback service data when LLM fails"""
        route_params = self._extract_route_params(service_data['route'])
        
        params = []
        for param in route_params:
            params.append({
                "name": param,
                "type": "string",
                "required": True,
                "description": f"Parameter {param} from route"
            })
        
        result = {
            "code": self._get_default_code(service_data['service_type']),
            "params": params,
            "dependencies": [],
            "documentation": f"{service_data['description']}\n\nThis is an auto-generated {service_data['service_type']} service.",
        }
        
        if service_data['service_type'] == 'resource':
            result['mime_type'] = "text/plain"
        elif service_data['service_type'] == 'prompt':
            result['prompt_template'] = "Process: {input}"
            result['prompt_args'] = [{"name": "input", "type": "string", "required": True, "description": "Input text"}]
        
        return result


# Singleton instance
service_generator = ServiceGenerator()