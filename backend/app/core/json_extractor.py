"""
JSON Extraction Utilities

Provides robust JSON extraction from text responses,
allowing LLMs to work in text mode while still returning structured data.
"""
import json
import re
from typing import Optional, Any, Union
import logging

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[Union[dict, list]]:
    """
    Extract JSON from various text formats.
    
    Tries multiple extraction methods in order:
    1. Direct JSON parsing if already valid JSON
    2. Extract from markdown JSON code blocks ```json...```
    3. Extract from generic code blocks ```...```
    4. Find raw JSON objects/arrays in text
    5. Aggressive extraction between first { and last }
    
    Args:
        text: The text containing potential JSON
        
    Returns:
        Parsed JSON object/array or None if extraction fails
    """
    if not text:
        return None
    
    # 1. Try direct parsing - text might already be valid JSON
    try:
        return json.loads(text.strip())
    except:
        pass
    
    # 2. Extract from ```json ... ``` blocks
    json_block_pattern = r'```json\s*(.*?)\s*```'
    json_blocks = re.findall(json_block_pattern, text, re.DOTALL | re.IGNORECASE)
    for block in json_blocks:
        try:
            result = json.loads(block.strip())
            logger.debug("Successfully extracted JSON from markdown json block")
            return result
        except Exception as e:
            logger.debug(f"Failed to parse JSON block: {e}")
            continue
    
    # 3. Extract from generic ``` ... ``` blocks
    code_block_pattern = r'```\s*(.*?)\s*```'
    code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
    for block in code_blocks:
        try:
            result = json.loads(block.strip())
            logger.debug("Successfully extracted JSON from generic code block")
            return result
        except:
            continue
    
    # 4. Try to find JSON objects in the text
    # Look for pattern that starts with { and ends with }
    object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    object_matches = re.findall(object_pattern, text)
    for match in object_matches:
        try:
            result = json.loads(match)
            logger.debug("Successfully extracted JSON object from text")
            return result
        except:
            continue
    
    # 5. Try to find JSON arrays in the text
    array_pattern = r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]'
    array_matches = re.findall(array_pattern, text)
    for match in array_matches:
        try:
            result = json.loads(match)
            logger.debug("Successfully extracted JSON array from text")
            return result
        except:
            continue
    
    # 6. Last resort - find first { and last }, or first [ and last ]
    # This handles cases where JSON is embedded in text
    obj_start = text.find('{')
    obj_end = text.rfind('}')
    arr_start = text.find('[')
    arr_end = text.rfind(']')
    
    # Try object extraction
    if obj_start >= 0 and obj_end > obj_start:
        try:
            result = json.loads(text[obj_start:obj_end + 1])
            logger.debug("Successfully extracted JSON using boundary detection (object)")
            return result
        except:
            pass
    
    # Try array extraction
    if arr_start >= 0 and arr_end > arr_start:
        # Only try if array comes before object or no object found
        if obj_start < 0 or arr_start < obj_start:
            try:
                result = json.loads(text[arr_start:arr_end + 1])
                logger.debug("Successfully extracted JSON using boundary detection (array)")
                return result
            except:
                pass
    
    logger.debug("Could not extract JSON from text")
    return None


def ensure_json_in_text(prompt: str, json_example: Optional[str] = None) -> str:
    """
    Add instructions to a prompt to ensure JSON is returned in a parseable format.
    
    Args:
        prompt: The original prompt
        json_example: Optional example of expected JSON structure
        
    Returns:
        Enhanced prompt with JSON formatting instructions
    """
    json_instruction = """
IMPORTANT: Format your JSON response in a markdown code block like this:
```json
{
  "your_response": "goes here"
}
```
"""
    
    if json_example:
        json_instruction += f"\nExpected structure:\n```json\n{json_example}\n```\n"
    
    return prompt + "\n\n" + json_instruction


def create_json_instruction(schema: Optional[Any] = None) -> str:
    """
    Create a clear instruction for JSON output based on a schema.
    
    Args:
        schema: Optional schema or example to guide the output
        
    Returns:
        Instruction string to add to prompts
    """
    instruction = "Please provide your response as valid JSON in a markdown code block (```json ... ```)."
    
    if schema:
        if isinstance(schema, dict):
            example = json.dumps(schema, indent=2)
            instruction += f"\n\nExample structure:\n```json\n{example}\n```"
        elif isinstance(schema, str) and schema != "json":
            instruction += f"\n\nExpected format: {schema}"
    
    return instruction