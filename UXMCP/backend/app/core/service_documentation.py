"""
Service Documentation for LLM Agent Context

This module provides comprehensive documentation about UXMCP services
to be used as context for the LLM agent when creating new services.
"""

SERVICE_CREATION_GUIDE = """
# UXMCP Service Creation Guide

## Overview
UXMCP allows you to create dynamic services (tools, resources, prompts) that can be exposed via MCP (Model Context Protocol).
Each service is a Python function that processes parameters and returns results.

## Service Structure

Every UXMCP service must have these fields:
- **name**: Unique identifier (alphanumeric, underscore, hyphen only)
- **service_type**: One of "tool", "resource", or "prompt"
- **route**: HTTP endpoint path (e.g., /api/weather/{city})
- **method**: HTTP method (GET, POST, PUT, DELETE)
- **code**: Python code with a `handler(**params)` function
- **params**: List of parameters extracted from route and request
- **dependencies**: Python modules to import (e.g., ["requests", "datetime"])
- **description**: Brief description of what the service does

## Choosing the Right HTTP Method

### Use GET when:
- Parameters are simple values (strings, numbers)
- Parameters don't contain special characters or complex data
- The operation is read-only (fetching data)
- Parameters can be safely exposed in URLs
- Total URL length will be under 2000 characters

### Use POST when:
- Parameters may contain special characters (URLs, paths, JSON)
- Parameters include complex objects or arrays
- The operation creates or modifies data
- Parameters should not be visible in URLs
- You need to send large amounts of data

### Use PUT when:
- Updating an entire resource
- The operation is idempotent

### Use DELETE when:
- Removing a resource

## Examples:
- Weather service (city name) → GET /api/weather/{city}
- URL fetcher (complex URLs) → POST /api/fetch with {"url": "..."} in body
- Calculator (simple numbers) → GET /api/calc?a=1&b=2
- Code analyzer (code text) → POST /api/analyze with {"code": "..."} in body

## Service Types

### 1. Tool Services
Tools perform actions and return structured data. They MUST:
- Define a handler function that accepts **params
- Return JSON-serializable data
- Include an output_schema (JSON Schema) describing the return format

Example Tool:
```python
def handler(**params):
    city = params.get('city', 'Unknown')
    temperature = params.get('temp', 20)
    
    # Process the data
    result = {
        "location": city,
        "temperature": temperature,
        "unit": "celsius",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return result
```

Output Schema for above:
```json
{
    "type": "object",
    "properties": {
        "location": {"type": "string", "description": "City name"},
        "temperature": {"type": "number", "description": "Temperature value"},
        "unit": {"type": "string", "description": "Temperature unit"},
        "timestamp": {"type": "string", "description": "ISO timestamp"}
    },
    "required": ["location", "temperature", "unit", "timestamp"]
}
```

### 2. Resource Services
Resources provide data content with a MIME type. They MUST:
- Return a dictionary with "content" and "mimeType" fields
- Content can be text, JSON, HTML, etc.

Example Resource:
```python
def handler(**params):
    doc_id = params.get('id', 'default')
    
    content = f'''Documentation for {doc_id}
    
This is a sample resource that provides documentation.
Generated at: {datetime.utcnow()}
'''
    
    return {
        "content": content,
        "mimeType": "text/plain"
    }
```

### 3. Prompt Services
Prompts generate dynamic templates for LLMs. They MUST:
- Return a dictionary with "template" field
- Can use parameters to customize the prompt

Example Prompt:
```python
def handler(**params):
    language = params.get('language', 'Python')
    task = params.get('task', 'explain this code')
    
    template = f'''You are an expert {language} developer.
    
Task: {task}

Please provide a detailed response following best practices.'''
    
    return {"template": template}
```

## Parameter Handling

### Route Parameters
Parameters in curly braces in the route (e.g., /api/user/{id}) are:
- Automatically extracted from the URL
- Always required
- Passed to handler via params dict

### Query Parameters (GET)
For GET requests, non-route parameters become query parameters:
```python
# Route: /api/search/{category}
# URL: /api/search/books?limit=10&sort=title
def handler(**params):
    category = params['category']  # From route
    limit = params.get('limit', 20)  # From query
    sort = params.get('sort', 'date')  # From query
```

### Body Parameters (POST/PUT)
For POST/PUT requests, parameters come from JSON body:
```python
# Route: /api/users
# Body: {"name": "John", "email": "john@example.com"}
def handler(**params):
    name = params.get('name')
    email = params.get('email')
```

## Error Handling

Always use try-except blocks for robust error handling:
```python
def handler(**params):
    try:
        # Your logic here
        result = process_data(params)
        return result
    except ValueError as e:
        return {"error": f"Invalid value: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
```

## Common Patterns

### External API Calls
```python
import requests

def handler(**params):
    api_key = params.get('api_key', '')
    query = params.get('query', '')
    
    try:
        response = requests.get(
            f"https://api.example.com/search",
            params={"q": query, "key": api_key},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": f"API call failed: {str(e)}"}
```

### URL Fetcher (POST method recommended)
```python
import requests
import urllib.parse

def handler(**params):
    url = params.get('url', '')
    headers = params.get('headers', {})
    timeout = params.get('timeout', 30)
    
    try:
        # Add https:// if no protocol specified
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        
        response = requests.get(url, headers=headers, timeout=timeout)
        
        return {
            "url": url,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": response.text[:1000],  # First 1000 chars
            "content_length": len(response.content)
        }
    except requests.RequestException as e:
        return {"error": f"Failed to fetch URL: {str(e)}"}
```

### Data Processing
```python
import json
import statistics

def handler(**params):
    data = params.get('data', [])
    
    if not isinstance(data, list):
        return {"error": "Data must be a list of numbers"}
    
    try:
        result = {
            "count": len(data),
            "sum": sum(data),
            "mean": statistics.mean(data) if data else 0,
            "median": statistics.median(data) if data else 0
        }
        return result
    except Exception as e:
        return {"error": f"Statistical calculation failed: {str(e)}"}
```

### File/Text Processing
```python
import re
import hashlib

def handler(**params):
    text = params.get('text', '')
    operation = params.get('operation', 'wordcount')
    
    if operation == 'wordcount':
        words = len(re.findall(r'\w+', text))
        return {"word_count": words}
    elif operation == 'hash':
        hash_value = hashlib.sha256(text.encode()).hexdigest()
        return {"sha256": hash_value}
    else:
        return {"error": f"Unknown operation: {operation}"}
```

## Best Practices

1. **Always validate inputs**: Check types and ranges
2. **Use meaningful variable names**: Make code self-documenting
3. **Return consistent structures**: Always return dicts with clear fields
4. **Handle missing parameters**: Use .get() with defaults
5. **Import only what you need**: List specific dependencies
6. **Add helpful error messages**: Help users understand what went wrong
7. **Keep it simple**: Don't over-engineer, focus on the task
8. **Test edge cases**: Empty inputs, invalid types, etc.

## CRITICAL: Import Rules in Dynamic Environment

In the UXMCP dynamic execution environment, imports work differently:

### ❌ WRONG - These will NOT work:
```python
from urllib.parse import unquote  # ❌ Will cause NameError
from datetime import datetime     # ❌ Will cause NameError
from os.path import join         # ❌ Will cause NameError
```

### ✅ CORRECT - Use full module paths:
```python
# For urllib functions
url = urllib.parse.unquote(encoded_url)  # ✓ Correct

# For datetime
timestamp = datetime.datetime.utcnow()  # ✓ Correct

# For os.path
path = os.path.join(dir, file)  # ✓ Correct
```

### Available Pre-imported Modules:
When you list a module in `dependencies`, it's imported as the full module:
- `urllib` → use `urllib.parse.unquote()`
- `datetime` → use `datetime.datetime.utcnow()`
- `os` → use `os.path.join()`
- `json` → use `json.dumps()`
- `math` → use `math.sqrt()`

IMPORTANT: Always use the full module path notation!

## Debugging Tips

- Use print() statements - they will appear in service logs
- Return intermediate values for debugging
- Check parameter types with isinstance()
- Validate required fields early in the function
- Use descriptive error messages

## Parameter Types

When defining service parameters, use these types:
- **string**: Text values
- **number**: Integer or float values  
- **boolean**: True/False values
- **array**: List of values
- **object**: Dictionary/JSON object

## Dependencies

Common Python modules and their uses:
- **requests**: HTTP API calls
- **datetime**: Date/time operations
- **json**: JSON parsing (usually auto-imported)
- **math**: Mathematical operations
- **re**: Regular expressions
- **hashlib**: Cryptographic hashing
- **statistics**: Statistical calculations
- **random**: Random number generation
- **urllib**: URL parsing
- **base64**: Base64 encoding/decoding

### Package Management

The agent can automatically install missing packages! When creating services:
1. List common dependencies in the `dependencies` field
2. If activation fails due to missing module, the agent will:
   - Detect the missing module automatically
   - Check if it's available on PyPI
   - Install it using pip
   - Retry activation

IMPORTANT: Package names vs Import names
Some packages have different names for installation and import:

| Package Name (pip install) | Import Name (in code) | Usage |
|----------------------------|----------------------|--------|
| beautifulsoup4 | bs4 | `from bs4 import BeautifulSoup` |
| pillow | PIL | `from PIL import Image` |
| opencv-python | cv2 | `import cv2` |
| scikit-learn | sklearn | `from sklearn import ...` |
| pyyaml | yaml | `import yaml` |

Example with BeautifulSoup:
```python
# In dependencies list:
"dependencies": ["beautifulsoup4"]

# In code:
from bs4 import BeautifulSoup  # ✓ Correct
# NOT: from beautifulsoup4 import ...  # ✗ Wrong
```

Popular packages that can be installed:
- **beautifulsoup4** (import as bs4): HTML/XML parsing
- **numpy**: Numerical computing
- **pandas**: Data analysis
- **pillow** (import as PIL): Image processing
- **psutil**: System monitoring
- **pytz**: Timezone handling
- **pyyaml** (import as yaml): YAML parsing
- **matplotlib**: Plotting/visualization
- **scikit-learn** (import as sklearn): Machine learning
- **nltk**: Natural language processing
- **lxml**: XML/HTML processing
- **requests**: HTTP requests (usually pre-installed)
- **httpx**: Modern async HTTP client
- **aiohttp**: Async HTTP client/server
- **fastapi**: Web framework
- **pydantic**: Data validation

### IMPORTANT: datetime module usage
When using the datetime module, remember:
```python
# WRONG - This will cause AttributeError
import datetime
timestamp = datetime.utcnow()  # ❌ ERROR!

# CORRECT - Use the full path
import datetime
timestamp = datetime.datetime.utcnow()  # ✓ Correct

# OR import the class directly
from datetime import datetime
timestamp = datetime.utcnow()  # ✓ Also correct
```

Remember: Only include dependencies you actually use in the code!
"""

def get_service_documentation():
    """Get the complete service documentation for LLM context"""
    return SERVICE_CREATION_GUIDE

def get_examples_by_type(service_type: str) -> str:
    """Get specific examples for a service type"""
    examples = {
        "tool": """
# Weather Service Example
```python
import random

def handler(**params):
    city = params.get('city', 'Paris')
    
    # Simulate weather data
    weather_conditions = ['Sunny', 'Cloudy', 'Rainy', 'Partly Cloudy']
    temp = random.randint(10, 30)
    
    return {
        "city": city,
        "temperature": temp,
        "condition": random.choice(weather_conditions),
        "humidity": f"{random.randint(40, 80)}%"
    }
```

# Calculator Service Example  
```python
import math

def handler(**params):
    operation = params.get('operation', 'add')
    a = params.get('a', 0)
    b = params.get('b', 0)
    
    if operation == 'add':
        result = a + b
    elif operation == 'multiply':
        result = a * b
    elif operation == 'power':
        result = math.pow(a, b)
    else:
        return {"error": f"Unknown operation: {operation}"}
    
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result
    }
```
""",
        "resource": """
# System Info Resource Example
```python
import platform
import os

def handler(**params):
    info = f'''System Information
==================

Platform: {platform.system()}
Python Version: {platform.python_version()}
Machine: {platform.machine()}
Processor: {platform.processor()}

Environment Variables: {len(os.environ)} defined
'''
    
    return {
        "content": info,
        "mimeType": "text/plain"
    }
```

# JSON Data Resource Example
```python
import json
from datetime import datetime

def handler(**params):
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "data-provider",
        "version": "1.0.0",
        "data": {
            "items": ["item1", "item2", "item3"],
            "count": 3
        }
    }
    
    return {
        "content": json.dumps(data, indent=2),
        "mimeType": "application/json"
    }
```
""",
        "prompt": """
# Code Review Prompt Example
```python
def handler(**params):
    language = params.get('language', 'Python')
    code = params.get('code', '')
    focus = params.get('focus', 'general')
    
    template = f'''Please review this {language} code:

```{language}
{code}
```

Focus on: {focus}

Provide feedback on:
1. Code quality and best practices
2. Potential bugs or issues
3. Performance considerations
4. Security concerns
5. Suggestions for improvement'''
    
    return {"template": template}
```

# Task Prompt Example
```python
def handler(**params):
    task_type = params.get('type', 'analysis')
    context = params.get('context', '')
    requirements = params.get('requirements', [])
    
    req_list = '\\n'.join([f"- {req}" for req in requirements])
    
    template = f'''You are an expert assistant specialized in {task_type}.

Context:
{context}

Requirements:
{req_list}

Please provide a comprehensive response addressing all requirements.'''
    
    return {"template": template}
```
"""
    }
    
    return examples.get(service_type, "")

def get_common_errors_solutions():
    """Get common errors and their solutions"""
    return """
# Common Errors and Solutions

## Import Errors
**Error**: ModuleNotFoundError: No module named 'requests'
**Solution**: Add 'requests' to the dependencies list

## Parameter Errors
**Error**: KeyError: 'city'
**Solution**: Use params.get('city', 'default') instead of params['city']

## Type Errors
**Error**: TypeError: unsupported operand type(s)
**Solution**: Validate and convert parameter types before using them

## JSON Errors
**Error**: Object of type datetime is not JSON serializable
**Solution**: Convert datetime to string with .isoformat()

## Return Format Errors
**Error**: Service must return a dictionary
**Solution**: Always return a dict, not strings or other types

## Resource Errors
**Error**: Resource must return content and mimeType
**Solution**: Return {"content": "...", "mimeType": "text/plain"}

## Execution Errors
**Error**: handler function not found
**Solution**: Ensure your main function is named exactly 'handler'
"""