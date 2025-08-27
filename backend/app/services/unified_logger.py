"""
Unified logging service for COT and Agent services
Provides centralized logging with MongoDB persistence
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.database import get_database
from app.models.log import LogLevel
from app.core.mongodb_logger import ServiceLogger
import asyncio
import json
import uuid


class UnifiedLogger:
    """Unified logger for COT and Agent services with MongoDB persistence"""
    
    def __init__(self, service_id: str, service_name: str, execution_id: Optional[str] = None, db=None):
        """
        Initialize unified logger
        
        Args:
            service_id: Unique identifier for the service
            service_name: Human-readable name for the service
            execution_id: Optional execution ID for grouping related logs
            db: Optional database instance (for dependency injection)
        """
        self.service_id = service_id
        self.service_name = service_name
        self.execution_id = execution_id or str(uuid.uuid4())
        self.db = db if db is not None else get_database()
        self.logger = ServiceLogger(self.db, service_id, service_name, self.execution_id)
        
    async def log_cot_iteration(
        self,
        iteration_number: int,
        reasoning_type: str,
        thought: str,
        confidence: float,
        tool_calls: List[Dict[str, Any]] = None,
        tool_results: List[Dict[str, Any]] = None,
        should_continue: bool = True,
        validation_scores: Dict[str, float] = None
    ):
        """Log a Chain of Thought iteration"""
        details = {
            "iteration_number": iteration_number,
            "reasoning_type": reasoning_type,
            "thought": thought[:500] if thought else None,  # Truncate long thoughts
            "confidence": confidence,
            "should_continue": should_continue,
            "tool_calls_count": len(tool_calls) if tool_calls else 0,
            "tool_results_count": len(tool_results) if tool_results else 0
        }
        
        if validation_scores:
            details["validation_scores"] = validation_scores
            
        if tool_calls:
            details["tool_calls"] = [
                {
                    "tool_name": tc.get("tool_name", tc.get("name", "unknown")),
                    "arguments": self._truncate_data(tc.get("arguments", {}))
                }
                for tc in tool_calls[:5]  # Limit to first 5 tools
            ]
            
        if tool_results:
            details["tool_results"] = [
                {
                    "tool_name": tr.get("tool_name", "unknown"),
                    "success": tr.get("success", False),
                    "error": tr.get("error") if tr.get("error") else None
                }
                for tr in tool_results[:5]  # Limit to first 5 results
            ]
        
        message = f"COT Iteration {iteration_number}: {reasoning_type} (confidence: {confidence:.2f})"
        await self.logger.info(message, **details)
    
    async def log_tool_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
        success: bool,
        error: Optional[str] = None,
        execution_time: Optional[float] = None
    ):
        """Log tool execution details"""
        details = {
            "tool_name": tool_name,
            "arguments": self._truncate_data(arguments),
            "success": success,
            "execution_time": execution_time
        }
        
        if error:
            details["error"] = str(error)[:500]  # Truncate long errors
            
        if success and result is not None:
            details["result_preview"] = self._truncate_data(result, max_length=200)
            
        level = LogLevel.INFO if success else LogLevel.ERROR
        message = f"Tool execution: {tool_name} {'succeeded' if success else 'failed'}"
        
        if level == LogLevel.INFO:
            await self.logger.info(message, **details)
        else:
            await self.logger.error(message, **details)
    
    async def log_cot_synthesis(
        self,
        iterations_count: int,
        tool_results_count: int,
        final_answer_length: int,
        convergence_reason: str,
        success: bool
    ):
        """Log COT synthesis phase"""
        details = {
            "iterations_count": iterations_count,
            "tool_results_count": tool_results_count,
            "final_answer_length": final_answer_length,
            "convergence_reason": convergence_reason,
            "success": success
        }
        
        message = f"COT Synthesis: {iterations_count} iterations, {tool_results_count} tools used"
        await self.logger.info(message, **details)
    
    async def log_agent_execution(
        self,
        agent_id: str,
        agent_name: str,
        input_data: Dict[str, Any],
        execution_type: str,
        conversation_id: Optional[str] = None
    ):
        """Log agent execution start"""
        details = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "execution_type": execution_type,
            "input_preview": self._truncate_data(input_data, max_length=200),
            "conversation_id": conversation_id
        }
        
        message = f"Agent execution started: {agent_name} ({execution_type})"
        await self.logger.info(message, **details)
    
    async def log_llm_call(
        self,
        model: str,
        messages_count: int,
        tools_count: int = 0,
        temperature: float = 0.7,
        response_type: str = "text",
        tokens_used: Optional[Dict[str, int]] = None
    ):
        """Log LLM API call"""
        details = {
            "model": model,
            "messages_count": messages_count,
            "tools_count": tools_count,
            "temperature": temperature,
            "response_type": response_type
        }
        
        if tokens_used:
            details["tokens_used"] = tokens_used
            
        message = f"LLM call: {model} with {messages_count} messages"
        await self.logger.debug(message, **details)
    
    async def log_memory_operation(
        self,
        operation: str,
        memories_count: int,
        query: Optional[str] = None,
        success: bool = True
    ):
        """Log memory system operations"""
        details = {
            "operation": operation,
            "memories_count": memories_count,
            "success": success
        }
        
        if query:
            details["query"] = query[:200]  # Truncate long queries
            
        message = f"Memory {operation}: {memories_count} memories"
        await self.logger.debug(message, **details)
    
    async def log_validation(
        self,
        validation_type: str,
        is_valid: bool,
        feedback: Optional[str] = None,
        scores: Optional[Dict[str, float]] = None
    ):
        """Log validation results"""
        details = {
            "validation_type": validation_type,
            "is_valid": is_valid
        }
        
        if feedback:
            details["feedback"] = feedback[:300]
            
        if scores:
            details["scores"] = scores
            
        level = LogLevel.INFO if is_valid else LogLevel.WARNING
        message = f"Validation {validation_type}: {'passed' if is_valid else 'failed'}"
        
        if level == LogLevel.INFO:
            await self.logger.info(message, **details)
        else:
            await self.logger.warning(message, **details)
    
    async def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None
    ):
        """Log error with context"""
        details = {
            "error_type": error_type,
            "error_message": error_message[:500]
        }
        
        if context:
            details["context"] = self._truncate_data(context)
            
        if stack_trace:
            details["stack_trace"] = stack_trace[:1000]
            
        message = f"Error: {error_type} - {error_message[:100]}"
        await self.logger.error(message, **details)
    
    async def debug(self, message: str, **kwargs):
        """Log debug message"""
        await self.logger.debug(message, **kwargs)
    
    async def info(self, message: str, **kwargs):
        """Log info message"""
        await self.logger.info(message, **kwargs)
    
    async def warning(self, message: str, **kwargs):
        """Log warning message"""
        await self.logger.warning(message, **kwargs)
    
    async def error(self, message: str, **kwargs):
        """Log error message"""
        await self.logger.error(message, **kwargs)
    
    def _truncate_data(self, data: Any, max_length: int = 300) -> Any:
        """Truncate data for logging"""
        if data is None:
            return None
            
        if isinstance(data, str):
            return data[:max_length] if len(data) > max_length else data
            
        if isinstance(data, dict):
            truncated = {}
            for key, value in list(data.items())[:10]:  # Limit to 10 keys
                truncated[key] = self._truncate_data(value, max_length=100)
            return truncated
            
        if isinstance(data, list):
            return [self._truncate_data(item, max_length=100) for item in data[:5]]  # Limit to 5 items
            
        try:
            str_data = str(data)
            return str_data[:max_length] if len(str_data) > max_length else str_data
        except:
            return "<truncated>"


class SyncUnifiedLogger:
    """Synchronous wrapper for UnifiedLogger for use in synchronous contexts"""
    
    def __init__(self, service_id: str, service_name: str, execution_id: Optional[str] = None):
        self.async_logger = UnifiedLogger(service_id, service_name, execution_id)
        
    def _run_async(self, coro):
        """Run async method in sync context"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, create task
                asyncio.create_task(coro)
            else:
                # We're in sync context, run until complete
                loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop, create one
            asyncio.run(coro)
    
    def log_cot_iteration(self, *args, **kwargs):
        self._run_async(self.async_logger.log_cot_iteration(*args, **kwargs))
    
    def log_tool_execution(self, *args, **kwargs):
        self._run_async(self.async_logger.log_tool_execution(*args, **kwargs))
    
    def log_cot_synthesis(self, *args, **kwargs):
        self._run_async(self.async_logger.log_cot_synthesis(*args, **kwargs))
    
    def log_agent_execution(self, *args, **kwargs):
        self._run_async(self.async_logger.log_agent_execution(*args, **kwargs))
    
    def log_llm_call(self, *args, **kwargs):
        self._run_async(self.async_logger.log_llm_call(*args, **kwargs))
    
    def log_memory_operation(self, *args, **kwargs):
        self._run_async(self.async_logger.log_memory_operation(*args, **kwargs))
    
    def log_validation(self, *args, **kwargs):
        self._run_async(self.async_logger.log_validation(*args, **kwargs))
    
    def log_error(self, *args, **kwargs):
        self._run_async(self.async_logger.log_error(*args, **kwargs))
    
    def debug(self, *args, **kwargs):
        self._run_async(self.async_logger.debug(*args, **kwargs))
    
    def info(self, *args, **kwargs):
        self._run_async(self.async_logger.info(*args, **kwargs))
    
    def warning(self, *args, **kwargs):
        self._run_async(self.async_logger.warning(*args, **kwargs))
    
    def error(self, *args, **kwargs):
        self._run_async(self.async_logger.error(*args, **kwargs))