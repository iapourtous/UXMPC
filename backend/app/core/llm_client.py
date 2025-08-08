"""
Centralized LLM Client Service

This module provides a unified interface for calling different LLM providers,
eliminating code duplication and ensuring consistent behavior across the application.
"""

import json
import httpx
import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from app.models.llm import LLMProfile

logger = logging.getLogger(__name__)


class LLMClient:
    """Centralized client for LLM API calls with provider-specific handling"""
    
    def __init__(self):
        self.default_timeout = 120.0
        self.default_max_retries = 3
    
    async def call(
        self,
        llm_profile: LLMProfile,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[float] = None,
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
                max_retries, timeout, **kwargs
            )
        elif "moonshot.cn" in endpoint:
            return await self._call_moonshot(
                llm_profile, messages, tools, temperature, max_tokens,
                max_retries, timeout, **kwargs
            )
        else:
            # Default to OpenAI-compatible API
            return await self._call_openai_compatible(
                llm_profile, messages, tools, temperature, max_tokens,
                max_retries, timeout, **kwargs
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
                return response["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"Simple LLM call failed: {str(e)}")
        
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
                return {
                    "success": True,
                    "message": response["choices"][0]["message"]["content"],
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
                completion_params["tool_choice"] = "auto"
                
            # Add JSON mode if configured
            if llm_profile.mode == "json":
                completion_params["response_format"] = {"type": "json_object"}
            
            max_retries = max_retries or self.default_max_retries
            
            for attempt in range(max_retries):
                try:
                    completion = await client.chat.completions.create(**completion_params)
                    
                    # Convert to standardized format
                    response = {
                        "choices": [
                            {
                                "message": {
                                    "role": completion.choices[0].message.role,
                                    "content": completion.choices[0].message.content
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
                max_retries, timeout, **kwargs
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
        **kwargs
    ) -> Dict[str, Any]:
        """Call Moonshot API with specific handling"""
        # For now, use OpenAI-compatible handling
        # Can be specialized later if needed
        return await self._call_openai_compatible(
            llm_profile, messages, tools, temperature, max_tokens,
            max_retries, timeout, **kwargs
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
            payload["tool_choice"] = "auto"
            
        # Add JSON mode if configured
        if llm_profile.mode == "json":
            payload["response_format"] = {"type": "json_object"}
        
        max_retries = max_retries or self.default_max_retries
        
        async with httpx.AsyncClient(timeout=timeout or self.default_timeout) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.post(endpoint, headers=headers, json=payload)
                    response.raise_for_status()
                    
                    result = response.json()
                    
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