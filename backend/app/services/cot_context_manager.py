"""
COT Context Manager
Manages context throughout COT reasoning iterations
"""
from typing import List, Dict, Any, Optional
import logging
import re
from datetime import datetime
from app.services.cot_iteration_executor import ReasoningIteration

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages and updates context throughout COT execution"""
    
    def __init__(self):
        """Initialize context manager"""
        pass
    
    def initialize_context(
        self,
        problem: str,
        initial_context: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        agent_config: Dict[str, Any] = None,
        demonstrations: List[Any] = None,
        tools: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Initialize context for COT execution
        
        Args:
            problem: The problem to solve
            initial_context: Initial context from agent
            conversation_history: Full conversation history
            agent_config: Agent's 7D configuration
            demonstrations: Reasoning demonstrations
            tools: Available tools in OpenAI format
            
        Returns:
            Initialized context dictionary
        """
        context = {
            'problem': problem,
            'accumulated_knowledge': [],
            'accumulated_facts': [],
            'tool_usage_history': {},
            'iteration_count': 0,
            'recovery_attempts': 0,
            'available_tools': [t.get('function', {}).get('name') for t in (tools or [])],
            'agent_config': agent_config,
            'demonstrations': demonstrations or [],
            'timestamp': datetime.now().isoformat(),
            'conversation_summary': self._summarize_conversation(conversation_history),
            'memory_context': initial_context.get('memory_context', '') if initial_context else ''
        }
        
        # Merge with initial context (this preserves any additional fields)
        if initial_context:
            # Update with initial_context but don't override what we've already set
            for key, value in initial_context.items():
                if key not in context:
                    context[key] = value
        
        # Store the full context messages for use in all iterations
        # conversation_history contains all the system messages with agent config, memory, User Context, etc.
        # We keep ALL messages except the last one (which is the user's question)
        if conversation_history and isinstance(conversation_history, list) and len(conversation_history) > 0:
            # Store all messages except the last user message (the question)
            context['full_context_messages'] = conversation_history[:-1]
        else:
            context['full_context_messages'] = []
        
        logger.debug(f"Context initialized with {len(context.get('full_context_messages', []))} context messages")
        
        return context
    
    def update_context(
        self,
        context: Dict[str, Any],
        iteration: ReasoningIteration
    ) -> Dict[str, Any]:
        """Update context after an iteration
        
        Args:
            context: Current context
            iteration: Completed iteration
            
        Returns:
            Updated context
        """
        updated = {**context}
        
        # Update iteration count
        updated['iteration_count'] = updated.get('iteration_count', 0) + 1
        
        # Add knowledge to accumulated facts
        if iteration.knowledge_gathered and iteration.knowledge_gathered != "None":
            if 'accumulated_facts' not in updated:
                updated['accumulated_facts'] = []
            updated['accumulated_facts'].append(iteration.knowledge_gathered)
        
        # Track tool usage
        if 'tool_usage_history' not in updated:
            updated['tool_usage_history'] = {}
        
        for tool_call in iteration.tool_calls:
            tool_name = tool_call.tool_name
            if tool_name not in updated['tool_usage_history']:
                updated['tool_usage_history'][tool_name] = 0
            updated['tool_usage_history'][tool_name] += 1
        
        # Add successful tool results to accumulated knowledge
        if 'accumulated_knowledge' not in updated:
            updated['accumulated_knowledge'] = []
        
        for tool_result in iteration.tool_results:
            if tool_result.success and tool_result.result:
                result_summary = {
                    'tool': tool_result.tool_name,
                    'iteration': iteration.iteration_number,
                    'result': str(tool_result.result)[:500]  # Store preview only
                }
                updated['accumulated_knowledge'].append(result_summary)
                
                # Extract important information (numbers, percentages, names, dates)
                facts = self._extract_key_facts(str(tool_result.result))
                updated['accumulated_facts'].extend(facts)
        
        # Track confidence trend
        if 'confidence_history' not in updated:
            updated['confidence_history'] = []
        updated['confidence_history'].append(iteration.confidence)
        
        # Store last iteration for reference
        updated['last_iteration'] = {
            'number': iteration.iteration_number,
            'confidence': iteration.confidence,
            'thought': iteration.thought[:200],
            'should_continue': iteration.should_continue
        }
        
        return updated
    
    def prepare_recovery_context(
        self,
        context: Dict[str, Any],
        recovery_strategy: str,
        recovery_prompt: str
    ) -> Dict[str, Any]:
        """Prepare context for recovery iterations
        
        Args:
            context: Current context
            recovery_strategy: Strategy being used
            recovery_prompt: Recovery prompt to inject
            
        Returns:
            Enhanced context for recovery
        """
        enhanced_context = {**context}
        enhanced_context['recovery_mode'] = True
        enhanced_context['recovery_strategy'] = recovery_strategy
        enhanced_context['recovery_prompt'] = recovery_prompt
        enhanced_context['recovery_attempts'] = enhanced_context.get('recovery_attempts', 0) + 1
        
        logger.debug(f"Recovery context prepared with strategy: {recovery_strategy}")
        
        return enhanced_context
    
    def get_iteration_summary(self, context: Dict[str, Any]) -> str:
        """Get a summary of the current iteration state
        
        Args:
            context: Current context
            
        Returns:
            Summary string
        """
        summary_parts = []
        
        # Iteration count
        iteration_count = context.get('iteration_count', 0)
        summary_parts.append(f"Iterations completed: {iteration_count}")
        
        # Confidence trend
        if context.get('confidence_history'):
            recent_confidence = context['confidence_history'][-5:]
            trend = ' → '.join([f"{c:.0%}" for c in recent_confidence])
            summary_parts.append(f"Confidence trend: {trend}")
        
        # Tool usage
        if context.get('tool_usage_history'):
            tool_summary = ', '.join([f"{name}({count}x)" 
                                     for name, count in context['tool_usage_history'].items()])
            summary_parts.append(f"Tools used: {tool_summary}")
        
        # Facts gathered
        if context.get('accumulated_facts'):
            summary_parts.append(f"Facts gathered: {len(context['accumulated_facts'])}")
        
        # Recovery status
        if context.get('recovery_mode'):
            summary_parts.append(f"Recovery mode: {context.get('recovery_strategy', 'unknown')}")
            summary_parts.append(f"Recovery attempts: {context.get('recovery_attempts', 0)}")
        
        return " | ".join(summary_parts)
    
    def should_summarize_context(self, context: Dict[str, Any]) -> bool:
        """Determine if context should be summarized to reduce size
        
        Args:
            context: Current context
            
        Returns:
            True if context should be summarized
        """
        # Check if accumulated knowledge is getting too large
        if context.get('accumulated_knowledge'):
            total_size = sum(len(str(k)) for k in context['accumulated_knowledge'])
            if total_size > 50000:  # 50KB threshold
                return True
        
        # Check if too many iterations
        if context.get('iteration_count', 0) > 10:
            return True
        
        # Check if too many facts
        if len(context.get('accumulated_facts', [])) > 20:
            return True
        
        return False
    
    async def summarize_context(
        self,
        context: Dict[str, Any],
        llm_profile: Any
    ) -> Dict[str, Any]:
        """Summarize context to reduce size while preserving key information
        
        Args:
            context: Current context
            llm_profile: LLM profile for summarization
            
        Returns:
            Summarized context
        """
        summarized = {**context}
        
        # Summarize accumulated knowledge if needed
        if self.should_summarize_context(context):
            logger.debug("Summarizing context to reduce size")
            
            # Keep only recent knowledge entries
            if context.get('accumulated_knowledge'):
                summarized['accumulated_knowledge'] = context['accumulated_knowledge'][-10:]
            
            # Keep only recent facts
            if context.get('accumulated_facts'):
                summarized['accumulated_facts'] = context['accumulated_facts'][-10:]
            
            # Keep only recent confidence history
            if context.get('confidence_history'):
                summarized['confidence_history'] = context['confidence_history'][-5:]
        
        return summarized
    
    def extract_final_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract essential context for final synthesis
        
        Args:
            context: Full context
            
        Returns:
            Essential context for synthesis
        """
        return {
            'full_context_messages': context.get('full_context_messages', []),
            'accumulated_facts': context.get('accumulated_facts', []),
            'confidence_history': context.get('confidence_history', []),
            'tool_usage_history': context.get('tool_usage_history', {})
        }
    
    def _extract_key_facts(self, text: str) -> List[str]:
        """Extract key facts from tool results
        
        Args:
            text: Text to extract facts from
            
        Returns:
            List of key facts
        """
        facts = []
        
        # Extract percentages
        percentages = re.findall(r'\b\d+(?:\.\d+)?%', text)
        for pct in percentages:  # NO LIMIT - extract all percentages
            # Find context around percentage
            idx = text.find(pct)
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            context = text[start:end].strip()
            if context:
                facts.append(context)
        
        # Extract large numbers (e.g., statistics)
        numbers = re.findall(r'\b\d{4,}\b', text)
        for num in numbers:  # NO LIMIT - extract all numbers
            idx = text.find(num)
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            context = text[start:end].strip()
            if context:
                facts.append(context)
        
        # Extract dates (years)
        years = re.findall(r'\b20\d{2}\b', text)
        for year in set(years):  # NO LIMIT - extract all years
            idx = text.find(year)
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            context = text[start:end].strip()
            if context:
                facts.append(context)
        
        # Extract key words indicating important information
        key_patterns = [
            r'(?:is|are|was|were)\s+(?:approximately|about|around|exactly)?\s*\$?\d+',
            r'(?:increased|decreased|rose|fell|grew|declined)\s+(?:by|to)\s+\d+',
            r'(?:revenue|profit|loss|growth|decline)\s+(?:of|at)\s+\$?\d+',
            r'(?:founded|established|created|started)\s+(?:in|on)\s+\d{4}'
        ]
        
        for pattern in key_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                facts.append(match.group(0))
        
        # Deduplicate while preserving order
        seen = set()
        unique_facts = []
        for fact in facts:
            if fact not in seen:
                seen.add(fact)
                unique_facts.append(fact)
        
        return unique_facts
    
    async def _summarize_previous_iterations(
        self,
        iterations: List[ReasoningIteration],
        problem: str,
        llm_profile: Any = None
    ) -> str:
        """Summarize previous iterations to reduce context size
        
        Args:
            iterations: List of previous iterations
            problem: The problem being solved
            llm_profile: Optional LLM profile for summarization
            
        Returns:
            Summary of previous iterations
        """
        # Try to use LLM for summarization if available
        if llm_profile:
            try:
                from app.services.settings_crud import settings_crud
                from app.services.llm_crud import llm_crud
                
                # Get global settings
                settings = await settings_crud.get_or_create()
                if settings and settings.summary_llm_profile:
                    # Get the Summary LLM profile
                    summary_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
                    if summary_profile and summary_profile.active:
                        # Build detailed text of iterations to summarize
                        iterations_text = ""
                        for iteration in iterations:
                            iterations_text += f"\nIteration {iteration.iteration_number}:\n"
                            iterations_text += f"- Thought: {iteration.thought}\n"
                            
                            if iteration.tool_results:
                                iterations_text += f"- Tools used: {', '.join([tr.tool_name for tr in iteration.tool_results])}\n"
                                for tr in iteration.tool_results:
                                    if tr.success:
                                        # Include key results but limited
                                        result_preview = str(tr.result)[:500]
                                        iterations_text += f"  Result preview: {result_preview}\n"
                            
                            if iteration.knowledge_gathered:
                                iterations_text += f"- Knowledge: {iteration.knowledge_gathered}\n"
                            
                            iterations_text += f"- Confidence: {iteration.confidence:.0%}\n"
                        
                        # Create prompt for summarization
                        summary_prompt = f"""Summarize the following Chain of Thought iterations concisely.
Focus on:
1. Key findings and facts discovered
2. Tools used and their results
3. Overall progress toward solving: {problem}

Iterations to summarize:
{iterations_text}

Provide a concise summary (max 500 words):"""
                        
                        # Call LLM for summarization
                        from app.core.llm_client import LLMClient
                        llm_client = LLMClient()
                        
                        summary = await llm_client.call_advanced(
                            llm_profile=summary_profile,
                            prompt=summary_prompt,
                            temperature=0.3,
                            max_tokens=1000
                        )
                        
                        if summary:
                            return summary.strip()
            except Exception as e:
                logger.warning(f"Failed to summarize with LLM: {e}")
        
        # Fallback to simple text summary
        return self._fallback_iteration_summary(iterations)
    
    def _fallback_iteration_summary(self, iterations: List[ReasoningIteration]) -> str:
        """Create a simple text summary of iterations without LLM
        
        Args:
            iterations: List of iterations
            
        Returns:
            Text summary
        """
        if not iterations:
            return "No previous iterations"
        
        summary = "Previous iterations summary:\n"
        for iteration in iterations[-5:]:  # Last 5 iterations
            summary += f"\nIteration {iteration.iteration_number}:\n"
            summary += f"- Thought: {iteration.thought[:200]}...\n"
            
            if iteration.tool_results:
                tools = ', '.join([tr.tool_name for tr in iteration.tool_results])
                summary += f"- Tools: {tools}\n"
            
            if iteration.knowledge_gathered:
                summary += f"- Knowledge: {iteration.knowledge_gathered[:100]}...\n"
            
            summary += f"- Confidence: {iteration.confidence:.0%}\n"
        
        return summary
    
    def _summarize_conversation(
        self,
        conversation_history: List[Dict[str, Any]]
    ) -> str:
        """Create a brief summary of conversation history
        
        Args:
            conversation_history: List of conversation messages
            
        Returns:
            Brief summary string
        """
        if not conversation_history:
            return "No previous conversation"
        
        recent = conversation_history[-6:]
        summary = "Recent conversation:\n"
        for msg in recent:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            summary += f"- {role}: {content}\n"
        
        return summary