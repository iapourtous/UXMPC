"""
Centralized LLM Client Service

This module provides a unified interface for calling different LLM providers,
eliminating code duplication and ensuring consistent behavior across the application.
"""

import json
import httpx
import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Union
from app.models.llm import LLMProfile

logger = logging.getLogger(__name__)


class LLMClient:
    """Centralized client for LLM API calls with provider-specific handling"""
    
    def __init__(self):
        self.default_timeout = 120.0
        self.default_max_retries = 3
    
    def _clean_think_tags(self, content: Optional[str]) -> Optional[str]:
        """
        Remove <think>...</think> tags and their content from the response
        
        Args:
            content: The text content to clean
            
        Returns:
            Cleaned content without think tags
        """
        if not content:
            return content
        
        # Use regex to remove <think>...</think> tags and their content
        # Using re.DOTALL to match across multiple lines
        cleaned = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Clean up any extra whitespace that might be left
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned if cleaned else content
    
    async def call(
        self,
        llm_profile: LLMProfile,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[float] = None,
        tool_choice: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make a unified LLM API call with automatic provider detection
        
        Args:
            llm_profile: LLM profile configuration
            messages: List of message dictionaries
            tools: Optional list of tool definitions for function calling
            temperature: Override profile temperature
            max_tokens: Override profile max_tokens
            max_retries: Override default retry count
            timeout: Override default timeout
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dict containing the LLM response with standardized format:
            {
                "choices": [...],
                "usage": {...},
                "model": "...",
                "provider": "..."
            }
        """
        endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
        
        # Detect provider type
        if "groq.com" in endpoint:
            return await self._call_groq(
                llm_profile, messages, tools, temperature, max_tokens, 
                max_retries, timeout, tool_choice, **kwargs
            )
        elif "moonshot.cn" in endpoint:
            return await self._call_moonshot(
                llm_profile, messages, tools, temperature, max_tokens,
                max_retries, timeout, tool_choice, **kwargs
            )
        else:
            # Default to OpenAI-compatible API
            return await self._call_openai_compatible(
                llm_profile, messages, tools, temperature, max_tokens,
                max_retries, timeout, tool_choice, **kwargs
            )
    
    async def call_simple(
        self,
        llm_profile: LLMProfile,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: Optional[int] = None
    ) -> Optional[str]:
        """
        Simple LLM call for single prompt/response scenarios
        
        Returns:
            String content of the response or None if failed
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=temperature,
                max_retries=max_retries
            )
            
            if response and "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                return self._clean_think_tags(content)
                
        except Exception as e:
            logger.error(f"Simple LLM call failed: {str(e)}")
        
        return None
    
    async def call_with_tools_iteration(
        self,
        llm_profile: LLMProfile,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        require_tool_use: bool = False,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Single iteration LLM call with tools support for agent executor
        
        Args:
            llm_profile: LLM profile configuration
            messages: Conversation messages
            tools: Available tools in OpenAI format
            temperature: Override temperature
            max_tokens: Override max tokens
            require_tool_use: Force tool usage
            timeout: Request timeout
            
        Returns:
            Raw response dict with standard format including tool_calls if present
        """
        try:
            # Prepare tool choice parameter
            tool_choice = None
            if tools:
                tool_choice = "required" if require_tool_use else "auto"
            
            # CRITICAL: Force text mode when using tools (JSON mode is incompatible with function calling)
            profile_to_use = llm_profile
            if tools and llm_profile.mode == "json":
                import copy
                profile_to_use = copy.copy(llm_profile)
                profile_to_use.mode = "text"
                logger.debug("Forcing text mode for tool call (JSON mode incompatible with function calling)")
            
            # Make the call using existing infrastructure
            response = await self.call(
                llm_profile=profile_to_use,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                tool_choice=tool_choice
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Tool iteration call failed: {str(e)}")
            raise
    
    async def call_advanced(
        self,
        llm_profile: LLMProfile,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, str]]] = None,
        base_messages: Optional[List[Dict[str, str]]] = None,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        json_mode: Optional[bool] = None,
        raise_on_error: bool = True
    ) -> Optional[str]:
        """
        Advanced unified LLM call supporting all use cases
        
        Args:
            llm_profile: LLM profile configuration
            prompt: Simple prompt string (will be added as user message)
            messages: Complete message list (overrides prompt)
            base_messages: Base context messages (prompt will be appended)
            system_message: Override system message
            temperature: Override temperature
            max_tokens: Override max tokens
            timeout: Override timeout
            json_mode: Force JSON response mode (deprecated - always uses text mode now)
            raise_on_error: Raise exception on error (True) or return None (False)
            
        Returns:
            String content of the response, or None if failed and raise_on_error=False
        """
        try:
            # Build messages list
            final_messages = []
            
            if messages:
                # Use provided messages directly
                final_messages = messages
            elif base_messages and prompt:
                # Use base messages and append prompt
                final_messages = base_messages.copy()
                final_messages.append({"role": "user", "content": prompt})
            elif prompt:
                # Build simple message list
                if system_message:
                    final_messages.append({"role": "system", "content": system_message})
                final_messages.append({"role": "user", "content": prompt})
            else:
                raise ValueError("Must provide either messages, prompt, or base_messages+prompt")
            
            # ALWAYS use text mode for better compatibility
            # JSON mode is deprecated and causes issues with tools
            import copy
            profile_to_use = copy.copy(llm_profile)
            profile_to_use.mode = "text"  # Force text mode
            
            # Log if we're overriding JSON mode
            if json_mode or llm_profile.mode == "json":
                logger.debug(f"Overriding JSON mode to text mode for compatibility (was json_mode={json_mode}, profile.mode={llm_profile.mode})")
            
            # Make the call with text mode profile
            response = await self.call(
                llm_profile=profile_to_use,
                messages=final_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            
            # Extract content
            if response and "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                cleaned_content = self._clean_think_tags(content)
                
                # If the caller expected JSON (json_mode was True or profile was JSON),
                # we can try to extract JSON from the text response
                if json_mode or llm_profile.mode == "json":
                    try:
                        from app.core.json_extractor import extract_json_from_text
                        extracted = extract_json_from_text(cleaned_content)
                        if extracted:
                            # Return as string since that's what call_advanced returns
                            import json
                            return json.dumps(extracted)
                    except:
                        # If extraction fails, return the cleaned content as-is
                        pass
                
                return cleaned_content
            
            if raise_on_error:
                raise Exception("No valid response from LLM")
            return None
                    
        except Exception as e:
            logger.error(f"Advanced LLM call failed: {str(e)}")
            if raise_on_error:
                raise
            return None
    
    async def call_with_history(
        self,
        llm_profile: LLMProfile,
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call LLM with conversation history support for chat services
        
        Args:
            llm_profile: LLM profile configuration
            message: New user message
            conversation_history: Previous messages in conversation
            system_message: Override system message
            temperature: Override temperature
            max_tokens: Override max tokens
            
        Returns:
            Full response dict with success status, message content, usage, etc.
        """
        messages = []
        
        # Add system message if provided or from profile
        if system_message or llm_profile.system_prompt:
            system_content = system_message or llm_profile.system_prompt
            messages.append({"role": "system", "content": system_content})
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
            
        # Add the new user message
        messages.append({"role": "user", "content": message})
        
        try:
            response = await self.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response and "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                cleaned_content = self._clean_think_tags(content)
                return {
                    "success": True,
                    "message": cleaned_content,
                    "usage": response.get("usage", {}),
                    "model": response.get("model", llm_profile.model),
                    "provider": response.get("provider", "unknown")
                }
                
        except Exception as e:
            logger.error(f"LLM call with history failed: {str(e)}")
            detail = ""
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                detail = e.response.text
            return {
                "success": False,
                "error": str(e),
                "detail": detail
            }
        
        return {
            "success": False,
            "error": "No response received"
        }
    
    async def _call_groq(
        self,
        llm_profile: LLMProfile,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        max_retries: Optional[int],
        timeout: Optional[float],
        tool_choice: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Call Groq using native client for better compatibility"""
        try:
            from groq import AsyncGroq
            
            client = AsyncGroq(
                api_key=llm_profile.api_key,
                timeout=timeout or self.default_timeout
            )
            
            completion_params = {
                "model": llm_profile.model,
                "messages": messages,
                "temperature": temperature or llm_profile.temperature,
                "max_tokens": max_tokens or llm_profile.max_tokens,
                "top_p": 1,
                "stream": False,
                "stop": None,
                **kwargs
            }
            
            # Add tools if provided
            if tools:
                completion_params["tools"] = tools
                completion_params["tool_choice"] = tool_choice or "auto"
                
            # Add JSON mode if configured (but not if tools are present - they're incompatible)
            if llm_profile.mode == "json" and not tools:
                completion_params["response_format"] = {"type": "json_object"}
            
            max_retries = max_retries or self.default_max_retries
            
            for attempt in range(max_retries):
                try:
                    completion = await client.chat.completions.create(**completion_params)
                    
                    # Convert to standardized format
                    content = completion.choices[0].message.content
                    cleaned_content = self._clean_think_tags(content)
                    response = {
                        "choices": [
                            {
                                "message": {
                                    "role": completion.choices[0].message.role,
                                    "content": cleaned_content
                                }
                            }
                        ],
                        "usage": {
                            "prompt_tokens": completion.usage.prompt_tokens if completion.usage else 0,
                            "completion_tokens": completion.usage.completion_tokens if completion.usage else 0,
                            "total_tokens": completion.usage.total_tokens if completion.usage else 0
                        },
                        "model": completion.model,
                        "provider": "groq"
                    }
                    
                    # Add tool calls if present
                    if hasattr(completion.choices[0].message, 'tool_calls') and completion.choices[0].message.tool_calls:
                        response["choices"][0]["message"]["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in completion.choices[0].message.tool_calls
                        ]
                    
                    # Validate JSON response if in JSON mode
                    if llm_profile.mode == "json":
                        content = response["choices"][0]["message"]["content"]
                        if content:
                            try:
                                json.loads(content)
                            except json.JSONDecodeError:
                                if attempt < max_retries - 1:
                                    logger.warning(f"Invalid JSON response on attempt {attempt + 1}, retrying...")
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                else:
                                    logger.error("Failed to get valid JSON response after all retries")
                    
                    return response
                    
                except Exception as e:
                    logger.error(f"Groq API call failed on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
                    
        except ImportError:
            logger.warning("Groq client not available, falling back to HTTP")
            return await self._call_openai_compatible(
                llm_profile, messages, tools, temperature, max_tokens,
                max_retries, timeout, tool_choice, **kwargs
            )
    
    async def _call_moonshot(
        self,
        llm_profile: LLMProfile,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        max_retries: Optional[int],
        timeout: Optional[float],
        tool_choice: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Call Moonshot API with specific handling"""
        # For now, use OpenAI-compatible handling
        # Can be specialized later if needed
        return await self._call_openai_compatible(
            llm_profile, messages, tools, temperature, max_tokens,
            max_retries, timeout, tool_choice, **kwargs
        )
    
    async def _call_openai_compatible(
        self,
        llm_profile: LLMProfile,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        max_retries: Optional[int],
        timeout: Optional[float],
        tool_choice: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Call OpenAI-compatible API using HTTP"""
        endpoint = llm_profile.endpoint or "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {llm_profile.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": llm_profile.model,
            "messages": messages,
            "temperature": temperature or llm_profile.temperature,
            "max_tokens": max_tokens or llm_profile.max_tokens,
            "stream": False,
            **kwargs
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
            
        # Add JSON mode if configured (but not if tools are present - they're incompatible)
        if llm_profile.mode == "json" and not tools:
            payload["response_format"] = {"type": "json_object"}
        
        max_retries = max_retries or self.default_max_retries
        
        async with httpx.AsyncClient(timeout=timeout or self.default_timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    
                    result = response.json()
                    
                    # Clean think tags from response content
                    if "choices" in result and result["choices"]:
                        for choice in result["choices"]:
                            if "message" in choice and "content" in choice["message"]:
                                choice["message"]["content"] = self._clean_think_tags(choice["message"]["content"])
                    
                    # Add provider info
                    result["provider"] = "openai_compatible"
                    
                    # Validate JSON response if in JSON mode
                    if llm_profile.mode == "json":
                        content = result.get("choices", [{}])[0].get("message", {}).get("content")
                        if content:
                            try:
                                json.loads(content)
                            except json.JSONDecodeError:
                                if attempt < max_retries - 1:
                                    logger.warning(f"Invalid JSON response on attempt {attempt + 1}, retrying...")
                                    await asyncio.sleep(2 ** attempt)
                                    continue
                                else:
                                    logger.error("Failed to get valid JSON response after all retries")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"HTTP API call failed on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
        
        raise Exception("All retry attempts failed")


# Global instance
llm_client = LLMClient()