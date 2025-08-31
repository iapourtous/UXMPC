"""
Message Builder for Agent Executor
Handles construction of messages for LLM interactions
"""
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import json
import yaml
from pathlib import Path
from app.models.agent import Agent, AgentExecution
from app.core.json_extractor import create_json_instruction
from app.core.prompt_loader import PromptLoader


class MessageBuilder:
    """Builds and formats messages for LLM interactions"""
    
    def __init__(self):
        """Initialize the message builder with prompt loader"""
        # Use the correct path to prompts directory
        prompts_path = Path(__file__).parent.parent / "prompts"
        self.prompt_loader = PromptLoader(base_path=prompts_path)
    
    def build_messages(
        self,
        agent: Agent,
        execution_request: AgentExecution,
        memory_context: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, str]]:
        """Build complete message list for LLM
        
        Args:
            agent: Agent configuration
            execution_request: Execution request with input and history
            memory_context: Optional memory context
            tools: Optional list of available tools
            
        Returns:
            List of message dictionaries with role and content
        """
        messages = []
        
        # Build system message
        system_content = self._build_system_message(agent, memory_context, tools)
        if system_content.strip():
            messages.append({
                "role": "system",
                "content": system_content.strip()
            })
        
        # Add conversation history if provided
        if execution_request.conversation_history:
            messages.extend(execution_request.conversation_history)
        
        # Build user message
        user_content = self._build_user_message(agent, execution_request)
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def _build_system_message(
        self,
        agent: Agent,
        memory_context: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build the system message with agent configuration
        
        Args:
            agent: Agent configuration
            memory_context: Optional memory context
            tools: Optional list of available tools
            
        Returns:
            System message content
        """
        sections = []
        
        # Add current date
        current_date = datetime.utcnow().strftime('%d/%m/%Y')
        sections.append(f"Date d'aujourd'hui : {current_date}")
        
        # Add identity and background
        if hasattr(agent, 'backstory') and agent.backstory:
            sections.append(f"# Your Identity and Background\n{agent.backstory}")
        
        # Add objectives
        objectives_section = self._format_objectives(agent)
        if objectives_section:
            sections.append(objectives_section)
        
        # Add constraints
        constraints_section = self._format_constraints(agent)
        if constraints_section:
            sections.append(constraints_section)
        
        # NOTE: Markdown capabilities removed from here - only added during synthesis in COT
        # This avoids duplication and keeps them for final presentation only
        
        # Add memory context
        if memory_context:
            sections.append(f"# Relevant Context from Memory\n{memory_context}")
        
        # Add tools context ONLY if not already in system prompt
        # Check if agent's system_prompt already contains tool descriptions
        if tools and (not agent.system_prompt or 'Available Tools' not in agent.system_prompt):
            tools_section = self.format_tools_for_context(tools)
            if tools_section:
                sections.append(tools_section)
        
        # Add memory system instructions
        memory_instructions = self._format_memory_instructions(agent)
        if memory_instructions:
            sections.append(memory_instructions)
        
        # Add original system prompt
        if agent.system_prompt:
            sections.append(agent.system_prompt)
        
        # Add JSON formatting instructions
        if agent.output_schema and agent.output_schema != "text":
            sections.append(create_json_instruction(agent.output_schema))
        
        return "\n\n".join(sections)
    
    def _format_objectives(self, agent: Agent) -> Optional[str]:
        """Format agent objectives"""
        if not hasattr(agent, 'objectives') or not agent.objectives:
            return None
        
        content = "# Your Objectives\n"
        for obj in agent.objectives:
            content += f"- {obj}\n"
        return content.rstrip()
    
    def _format_constraints(self, agent: Agent) -> Optional[str]:
        """Format agent constraints"""
        if not hasattr(agent, 'constraints') or not agent.constraints:
            return None
        
        content = "# Your Constraints\n"
        for constraint in agent.constraints:
            content += f"- {constraint}\n"
        return content.rstrip()
    
    
    
    def _format_memory_instructions(self, agent: Agent) -> Optional[str]:
        """Format memory system instructions"""
        if not hasattr(agent, 'memory_enabled') or not agent.memory_enabled:
            return None
        
        memory_config = getattr(agent, 'memory_config', {})
        if not memory_config.get('active_memory', True):
            return None
        
        try:
            return self.prompt_loader.load_prompt('agent/memory_system.txt')
        except:
            return None
    
    def format_tools_for_context(self, tools: List[Dict[str, Any]]) -> str:
        """Format tool definitions for inclusion in system context
        
        Args:
            tools: List of tool definitions
            
        Returns:
            Formatted tools description
        """
        if not tools:
            return ""
        
        formatted = "## Available Tools and Their Capabilities\n\n"
        formatted += "You have access to the following tools. Use them when needed to gather information or perform actions:\n\n"
        
        for i, tool in enumerate(tools, 1):
            if tool.get("type") != "function":
                continue
            
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            description = func.get("description", "No description available")
            params = func.get("parameters", {})
            
            # Tool header
            formatted += f"### {i}. {name}\n"
            formatted += f"{description}\n"
            
            # Parameters
            properties = params.get("properties", {})
            required = params.get("required", [])
            
            if properties:
                formatted += "**Parameters:**\n"
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "No description")
                    is_required = param_name in required
                    req_text = "required" if is_required else "optional"
                    
                    formatted += f"  - `{param_name}` ({param_type}, {req_text}): {param_desc}\n"
            else:
                formatted += "**Parameters:** None\n"
            
            formatted += "\n"
        
        # Add tools usage instructions
        try:
            tools_usage = self.prompt_loader.load_prompt('agent/tools_usage.txt')
            formatted += tools_usage
        except:
            formatted += "💡 **How to use tools:**\n"
            formatted += "- Call tools when you need specific information or to perform actions\n"
            formatted += "- Provide all required parameters\n"
            formatted += "- You can call multiple tools in sequence if needed\n"
            formatted += "- Once you have gathered all necessary information, provide your final answer\n"
        
        return formatted.rstrip()
    
    def _build_user_message(
        self,
        agent: Agent,
        execution_request: AgentExecution
    ) -> str:
        """Build the user message
        
        Args:
            agent: Agent configuration
            execution_request: Execution request
            
        Returns:
            User message content
        """
        user_content = ""
        
        # Add pre-prompt if configured
        if agent.pre_prompt:
            user_content = agent.pre_prompt + "\n\n"
        
        # Add user input
        if isinstance(execution_request.input, str):
            user_content += execution_request.input
        else:
            user_content += json.dumps(execution_request.input)
        
        return user_content