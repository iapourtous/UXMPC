# Prompt Migration Guide

This guide explains how to migrate from inline prompts to centralized prompt files.

## Example Migration: Meta Chat Service

### Before (Inline Prompt):
```python
prompt = f"""Analyze this user request and determine if an agent should handle it.

User request: "{message}"

Available agents:
{json.dumps(agent_list, indent=2)}

CRITICAL DECISION RULES...
"""
```

### After (Centralized Prompt):
```python
from app.core.prompt_loader import load_prompt

# In the method:
prompt = load_prompt(
    "meta_chat/analyze_request.txt",
    message=message,
    agent_list=json.dumps(agent_list, indent=2)
)
```

## Step-by-Step Migration Process

### 1. Extract the Prompt
- Copy the prompt string to a new `.txt` file
- Place it in the appropriate subdirectory under `/prompts/`
- Name it descriptively (e.g., `analyze_request.txt`)

### 2. Identify Variables
- Find all f-string variables (e.g., `{message}`, `{agent_list}`)
- Keep the variable names consistent
- Document required variables in the prompt file header

### 3. Update the Code
```python
# Add import at the top
from app.core.prompt_loader import load_prompt

# Replace the prompt string with:
prompt = load_prompt(
    "service_name/prompt_name.txt",
    variable1=value1,
    variable2=value2
)
```

### 4. Handle Special Cases

#### JSON Formatting
If you need to format JSON in the prompt:
```python
prompt = load_prompt(
    "path/to/prompt.txt",
    data=json.dumps(data_dict, indent=2)
)
```

#### Multi-line Strings
For complex formatting, prepare the variable before passing:
```python
use_cases_formatted = "\n".join(f"- {uc}" for uc in use_cases)
prompt = load_prompt(
    "path/to/prompt.txt",
    use_cases=use_cases_formatted
)
```

## Benefits of Centralization

1. **Version Control**: Track prompt changes independently
2. **A/B Testing**: Easy to swap prompt versions
3. **Maintenance**: Update prompts without touching code
4. **Reusability**: Share prompts across services
5. **Documentation**: Prompts are self-documenting
6. **Testing**: Test prompts independently

## Best Practices

### 1. File Organization
```
prompts/
├── meta_chat/
│   ├── analyze_request.txt
│   ├── select_agent.txt
│   └── generate_html.txt
├── agent_service/
│   ├── create_initial.txt
│   └── fix_errors.txt
└── tool_analyzer/
    └── identify_tools.txt
```

### 2. Variable Naming
- Use descriptive variable names
- Keep names consistent across related prompts
- Document variables at the top of prompt files

### 3. Prompt File Header
Add a header comment to each prompt file:
```
# Analyze User Request Prompt
# Purpose: Determine if an agent should handle the request
# Variables:
#   - message: The user's request text
#   - agent_list: JSON array of available agents
# Returns: JSON object with intent analysis
```

### 4. Error Handling
```python
try:
    prompt = load_prompt("path/to/prompt.txt", **variables)
except FileNotFoundError:
    logger.error(f"Prompt file not found")
    # Fallback to inline prompt or raise error
except ValueError as e:
    logger.error(f"Missing prompt variable: {e}")
    # Handle missing variables
```

## Testing Prompts

### 1. Validate Prompt Files
```python
from app.core.prompt_loader import prompt_loader

# Validate a prompt
result = prompt_loader.validate_prompt("meta_chat/analyze_request.txt")
print(f"Required variables: {result['variables']}")
```

### 2. List All Prompts
```python
# List all available prompts
all_prompts = prompt_loader.list_prompts()
for category, files in all_prompts.items():
    print(f"{category}: {files}")
```

### 3. Unit Testing
```python
def test_analyze_request_prompt():
    # Test that prompt loads and formats correctly
    prompt = load_prompt(
        "meta_chat/analyze_request.txt",
        message="Test message",
        agent_list="[]"
    )
    assert "Test message" in prompt
    assert "CRITICAL DECISION RULES" in prompt
```

## Gradual Migration Strategy

1. **Phase 1**: Migrate critical prompts (most frequently updated)
2. **Phase 2**: Migrate service generation prompts
3. **Phase 3**: Migrate agent configuration prompts
4. **Phase 4**: Migrate remaining prompts

## Monitoring and Debugging

### Enable Prompt Loading Logs
```python
import logging
logging.getLogger("app.core.prompt_loader").setLevel(logging.DEBUG)
```

### Cache Management
```python
# Clear cache to reload prompts during development
from app.core.prompt_loader import reload_prompts
reload_prompts()
```

## Future Enhancements

1. **Prompt Versioning**: Support multiple versions (v1, v2, etc.)
2. **Hot Reloading**: Automatically reload prompts in development
3. **Prompt Testing**: Automated testing framework for prompts
4. **Analytics**: Track which prompts are used most
5. **Web UI**: Edit prompts through the UXMCP interface