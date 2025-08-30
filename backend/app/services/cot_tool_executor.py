"""
Tool Executor for COT Adaptive Engine
Handles tool parsing and execution
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import re
import logging
from app.services.unified_logger import UnifiedLogger

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call request"""
    tool_name: str
    arguments: Dict[str, Any]
    
    
@dataclass
class ToolResult:
    """Result from a tool execution"""
    tool_name: str
    result: Any
    success: bool
    error: Optional[str] = None


class ToolExecutor:
    """Handles tool parsing and execution for COT Adaptive Engine"""
    
    def __init__(self):
        """Initialize tool executor"""
        pass
    
    async def parse_tool_calls(self, tool_text: str, available_tools: List[Dict[str, Any]]) -> List[ToolCall]:
        """Parse tool calls from TOOL_CALLS section text"""
        
        tool_calls = []
        
        # Skip if empty or explicitly says no tools
        if not tool_text or tool_text.strip() == '' or 'empty' in tool_text.lower() or 'none' in tool_text.lower():
            return []
        
        logger.debug(f"Parsing tool calls from text: {tool_text[:200]}")
        
        # Get available tool names for validation
        available_tool_names = set()
        for tool in available_tools:
            if 'function' in tool and 'name' in tool['function']:
                available_tool_names.add(tool['function']['name'])
        
        # Parse each line that looks like a function call
        for line in tool_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
            
            # Match function call pattern: tool_name(arg1="value1", arg2="value2")
            # Allow underscores in tool names
            match = re.match(r'([\w_]+)\((.*?)\)', line)
            if match:
                tool_name = match.group(1)
                args_str = match.group(2)
                
                # Validate tool name
                if tool_name not in available_tool_names:
                    logger.debug(f"Skipping unknown tool: {tool_name}")
                    continue
                
                # Parse arguments
                arguments = {}
                if args_str:
                    # Try to parse as Python-style arguments
                    try:
                        # Parse key=value pairs with improved pattern to handle escaped quotes and JSON
                        # Updated pattern to handle escaped quotes inside strings
                        arg_pattern = r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\[.*?\]|\{.*?\}|\d+(?:\.\d+)?|true|false|null)'
                        matches = re.findall(arg_pattern, args_str)
                        
                        for key, value in matches:
                            try:
                                # Try to parse as JSON value
                                if value.startswith('"') and value.endswith('"'):
                                    # String value - handle escaped quotes
                                    arguments[key] = json.loads(value)
                                elif value in ['true', 'false', 'null']:
                                    # Boolean or null
                                    arguments[key] = json.loads(value)
                                elif value.startswith('[') or value.startswith('{'):
                                    # Array or object - parse as JSON
                                    arguments[key] = json.loads(value)
                                else:
                                    # Number
                                    if '.' in value:
                                        arguments[key] = float(value)
                                    else:
                                        arguments[key] = int(value)
                            except (json.JSONDecodeError, ValueError) as e:
                                # Fallback to string, removing quotes
                                cleaned_value = value.strip('"').replace('\\"', '"')
                                arguments[key] = cleaned_value
                                logger.debug(f"Fallback to string for {key}={value}: {e}")
                    
                    except Exception as e:
                        logger.debug(f"Failed to parse arguments for {tool_name}: {e}")
                        # Try simple split approach as fallback
                        try:
                            if '=' in args_str:
                                # Has key=value pairs
                                parts = args_str.split(',')
                                for part in parts:
                                    if '=' in part:
                                        key, value = part.split('=', 1)
                                        key = key.strip()
                                        value = value.strip().strip('"').strip("'")
                                        arguments[key] = value
                            else:
                                # No key=value, just a single argument
                                # For memory_search, the parameter is "query"
                                clean_arg = args_str.strip().strip('"').strip("'")
                                if tool_name == "memory_search":
                                    arguments["query"] = clean_arg
                                else:
                                    arguments["input"] = clean_arg
                        except:
                            pass
                
                tool_calls.append(ToolCall(tool_name=tool_name, arguments=arguments))
                logger.debug(f"Parsed tool call: {tool_name}({arguments})")
        
        return tool_calls
    
    async def execute_tools(
        self,
        tool_calls: List[ToolCall],
        tool_executor_func,
        unified_logger: UnifiedLogger,
        iteration_num: int
    ) -> List[ToolResult]:
        """Execute tool calls and return results"""
        
        tool_results = []
        
        for tc in tool_calls:
            await unified_logger.info(
                f"Executing tool: {tc.tool_name}",
                iteration=iteration_num,
                arguments=tc.arguments
            )
            
            try:
                # Execute the tool using the provided executor function
                result = await tool_executor_func(tc.tool_name, tc.arguments)
                
                tool_results.append(ToolResult(
                    tool_name=tc.tool_name,
                    result=result,
                    success=True
                ))
                
                await unified_logger.info(
                    f"Tool {tc.tool_name} succeeded",
                    iteration=iteration_num,
                    result_preview=str(result)[:200] if result else None
                )
                
            except Exception as e:
                error_msg = str(e)
                tool_results.append(ToolResult(
                    tool_name=tc.tool_name,
                    result=None,
                    success=False,
                    error=error_msg
                ))
                
                await unified_logger.warning(
                    f"Tool {tc.tool_name} failed",
                    iteration=iteration_num,
                    error=error_msg
                )
        
        return tool_results
    
    def extract_response_sections(self, text: str) -> Dict[str, Any]:
        """Extract structured sections from LLM response"""
        
        sections = {
            'thought': None,
            'tool_calls_text': None,
            'evaluation': None,
            'confidence': 0.5,
            'should_continue': True,
            'knowledge_gathered': None
        }
        
        # Extract THOUGHT
        thought_match = re.search(
            r'THOUGHT:\s*(.*?)(?:TOOL_CALLS:|EVALUATION:|$)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if thought_match:
            sections['thought'] = thought_match.group(1).strip()
        
        # Extract TOOL_CALLS text
        tool_match = re.search(
            r'TOOL_CALLS:\s*(.*?)(?:EVALUATION:|CONFIDENCE:|$)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if tool_match:
            sections['tool_calls_text'] = tool_match.group(1).strip()
        
        # Extract EVALUATION
        eval_match = re.search(
            r'EVALUATION:\s*(.*?)(?:CONFIDENCE:|SHOULD_CONTINUE:|$)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if eval_match:
            sections['evaluation'] = eval_match.group(1).strip()
        
        # Extract CONFIDENCE
        conf_match = re.search(
            r'CONFIDENCE:\s*([\d.]+)',
            text,
            re.IGNORECASE
        )
        if conf_match:
            try:
                sections['confidence'] = float(conf_match.group(1))
            except ValueError:
                pass
        
        # Extract SHOULD_CONTINUE
        continue_match = re.search(
            r'SHOULD_CONTINUE:\s*(true|false)',
            text,
            re.IGNORECASE
        )
        if continue_match:
            sections['should_continue'] = continue_match.group(1).lower() == 'true'
        
        # Extract KNOWLEDGE_GATHERED
        knowledge_match = re.search(
            r'KNOWLEDGE_GATHERED:\s*(.*?)(?:$|\n\n)',
            text,
            re.DOTALL | re.IGNORECASE
        )
        if knowledge_match:
            sections['knowledge_gathered'] = knowledge_match.group(1).strip()
        
        return sections