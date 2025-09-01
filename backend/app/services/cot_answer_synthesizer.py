"""
COT Answer Synthesizer
Handles synthesis of final answers from reasoning iterations and tool results
"""
from typing import List, Dict, Optional, Any
import logging
import json
from app.services.cot_iteration_executor import ReasoningIteration
from app.services.cot_tool_executor import ToolResult
from app.services.cot_url_extractor import URLExtractor
from app.services.llm_crud import llm_crud
from app.services.settings_crud import settings_crud
from app.core.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class AnswerSynthesizer:
    """Synthesizes final answers from COT iterations and tool results"""
    
    def __init__(self):
        """Initialize answer synthesizer"""
        self.prompt_loader = PromptLoader()
        self.url_extractor = URLExtractor()
    
    async def synthesize_final_answer(
        self,
        problem: str,
        iterations: List[ReasoningIteration],
        all_tool_results: List[ToolResult],
        context: Dict[str, Any],
        llm_profile: Any,
        agent_config: Dict[str, Any]
    ) -> str:
        """Synthesize final answer from all iterations and tool results"""
        
        # Initialize URL collection
        all_urls = []
        
        # Get agent_id for memory storage (if available)
        agent_id = agent_config.get('id') or agent_config.get('agent_id')
        memory_enabled = agent_config.get('memory_enabled', False) and agent_id
        
        # Load synthesis prompt template
        try:
            prompt_template = self.prompt_loader.load_prompt('cot/synthesize_answer.txt')
        except Exception as e:
            logger.error(f"Failed to load synthesis prompt: {str(e)}")
            # Fallback to inline prompt if file not found
            prompt_template = """Answer the question: {problem}
            
Using the following data:
{tool_results}
{insights}

Provide a comprehensive answer."""
        
        # Build reasoning chain summary
        reasoning_chain_text = "## REASONING PROCESS:\n\n"
        for iteration in iterations:
            reasoning_chain_text += f"### Iteration {iteration.iteration_number} (Confidence: {iteration.confidence:.0%})\n"
            reasoning_chain_text += f"**Thought:** {iteration.thought}\n"
            
            if iteration.tool_results:
                reasoning_chain_text += f"**Tools used:**\n"
                for tr in iteration.tool_results:
                    if tr.success:
                        # Check if result is already summarized (new format)
                        if isinstance(tr.result, dict) and tr.result.get("was_summarized"):
                            # Result was already summarized in parallel execution
                            result_str = tr.result.get("summary", str(tr.result.get("original", ""))[:10000])
                            all_urls.extend(tr.result.get("urls", []))
                            original_length = len(str(tr.result.get("original", "")))
                            reasoning_chain_text += f"- {tr.tool_name} (summarized from {original_length} chars):\n```\n{result_str}\n```\n"
                        else:
                            # Handle regular results
                            result_str = str(tr.result)
                            if len(result_str) > 5000:
                                # This shouldn't happen with new parallel execution, but keep as fallback
                                result_str = result_str[:5000] + "..."
                                reasoning_chain_text += f"- {tr.tool_name} (truncated):\n```\n{result_str}\n```\n"
                            else:
                                reasoning_chain_text += f"- {tr.tool_name}:\n```\n{result_str}\n```\n"
                                # Extract URLs from non-summarized results
                                extracted = self.url_extractor.extract_and_validate(result_str)
                                all_urls.extend(extracted)
            
            if iteration.knowledge_gathered:
                reasoning_chain_text += f"**Knowledge gathered:** {iteration.knowledge_gathered}\n"
            reasoning_chain_text += "\n---\n\n"
        
        # Build consolidated tool results section  
        tool_results_text = "## ALL TOOL RESULTS:\n\n"
        # Building synthesis - logged to MongoDB only
        for i, tool_result in enumerate(all_tool_results):
            if tool_result.success and tool_result.result:
                # Check if result is already summarized (new format from parallel execution)
                if isinstance(tool_result.result, dict) and tool_result.result.get("was_summarized"):
                    # Already summarized in parallel execution
                    result_str = tool_result.result.get("summary", str(tool_result.result.get("original", ""))[:10000])
                    original_length = len(str(tool_result.result.get("original", "")))
                    extracted_urls = tool_result.result.get("urls", [])
                    all_urls.extend(extracted_urls)
                    
                    # Save synthesis to memory if enabled
                    if memory_enabled:
                        try:
                            from app.services.agent_memory_service import agent_memory_service
                            
                            # Find iteration number for this tool result
                            iteration_num = None
                            iteration_thought = ""
                            for iteration in iterations:
                                if any(tr.tool_name == tool_result.tool_name for tr in iteration.tool_results):
                                    iteration_num = iteration.iteration_number
                                    iteration_thought = iteration.thought
                                    break
                            
                            await agent_memory_service.save_tool_synthesis(
                                agent_id=agent_id,
                                tool_name=tool_result.tool_name,
                                original_result=str(tool_result.result),
                                synthesis=result_str,
                                problem_context=problem,
                                iteration_number=iteration_num,
                                urls=extracted_urls
                            )
                            logger.debug(f"Saved tool synthesis to memory for {tool_result.tool_name}")
                        except Exception as e:
                            logger.warning(f"Failed to save tool synthesis to memory: {str(e)}")
                    
                    tool_results_text += f"### {tool_result.tool_name} (summarized from {original_length} chars):\n```\n{result_str}\n```\n\n"
                    logger.debug(f"Added pre-summarized tool result from {tool_result.tool_name} ({original_length} -> {len(result_str)} chars)")
                else:
                    # Handle regular results (not pre-summarized)
                    result_str = str(tool_result.result)
                    original_length = len(result_str)
                    
                    # This case should rarely happen with new parallel execution
                    # but keep as fallback for backward compatibility
                    if len(result_str) > 10000:
                        result_str = result_str[:10000] + "..."
                        tool_results_text += f"### {tool_result.tool_name} (truncated from {original_length} chars):\n```\n{result_str}\n```\n\n"
                    else:
                        tool_results_text += f"### {tool_result.tool_name}:\n```\n{result_str}\n```\n\n"
                    
                    # Extract URLs from non-summarized results
                    extracted = self.url_extractor.extract_and_validate(result_str)
                    all_urls.extend(extracted)
                    
                    # For shorter results, still save to memory if enabled
                    if memory_enabled and len(result_str) > 100:  # Only save meaningful results
                        try:
                            from app.services.agent_memory_service import agent_memory_service
                            
                            # Find iteration number for this tool result
                            iteration_num = None
                            for iteration in iterations:
                                if any(tr.tool_name == tool_result.tool_name for tr in iteration.tool_results):
                                    iteration_num = iteration.iteration_number
                                    break
                            
                            await agent_memory_service.save_tool_synthesis(
                                agent_id=agent_id,
                                tool_name=tool_result.tool_name,
                                original_result=result_str,
                                synthesis=result_str,  # No synthesis needed for short results
                                problem_context=problem,
                                iteration_number=iteration_num,
                                urls=extracted
                            )
                            logger.debug(f"Saved tool result to memory for {tool_result.tool_name}")
                        except Exception as e:
                            logger.warning(f"Failed to save tool result to memory: {str(e)}")
                    
                    tool_results_text += f"### {tool_result.tool_name}:\n```\n{result_str}\n```\n\n"
                    logger.debug(f"Added tool result from {tool_result.tool_name} (length: {len(result_str)})")
        
        # Build key insights section from all iterations
        insights_text = "## KEY INSIGHTS:\n\n"
        for iteration in iterations:
            if iteration.knowledge_gathered:
                insights_text += f"- **Iteration {iteration.iteration_number}:** {iteration.knowledge_gathered}\n"
        
        # Get communication style
        communication_style = agent_config.get('personality', {}).get('communication_style', 'clear and direct')
        
        # Load markdown capabilities to inject into synthesis prompt
        try:
            markdown_capabilities = self.prompt_loader.load_prompt('markdown_capabilities.txt')
        except Exception as e:
            logger.warning(f"Could not load markdown capabilities: {e}")
            markdown_capabilities = ""
        
        # Format the prompt with all variables including reasoning chain
        synthesis_prompt = prompt_template.format(
            problem=problem,
            reasoning_chain=reasoning_chain_text,
            tool_results=tool_results_text,
            insights=insights_text,
            communication_style=json.dumps(communication_style),
            markdown_capabilities=markdown_capabilities
        )
        
        try:
            # Get synthesis LLM profile (may be different from main profile)
            settings = await settings_crud.get_or_create()
            synthesis_profile = llm_profile  # Default to main profile
            
            if settings and settings.summary_llm_profile:
                # Try to use dedicated synthesis profile
                custom_synthesis = await llm_crud.get_by_name(settings.summary_llm_profile)
                if custom_synthesis and custom_synthesis.active:
                    synthesis_profile = custom_synthesis
                    logger.debug(f"Using custom synthesis profile: {settings.summary_llm_profile}")
            
            # Force text mode for synthesis
            import copy
            synthesis_profile = copy.deepcopy(synthesis_profile)
            synthesis_profile.mode = "text"  # FORCE TEXT MODE
            
            # Build messages with full context for synthesis
            synthesis_messages = []
            
            # Collect all system messages to merge them
            system_contents = []
            other_messages = []
            
            # Process existing context messages
            if context.get('full_context_messages'):
                for msg in context['full_context_messages']:
                    if msg['role'] == 'system':
                        # Collect system message content
                        system_contents.append(msg['content'])
                    else:
                        # Keep non-system messages as-is
                        other_messages.append(msg)
            
            # Add synthesis-specific system content
            # Markdown capabilities are now injected directly in the synthesis prompt template
            synthesis_system_content = "You are creating the final answer. Transform all data into natural language, always return prose."
            
            system_contents.append(synthesis_system_content)
            
            # Create a single merged system message
            if system_contents:
                merged_system_content = "\n\n---\n\n".join(system_contents)
                synthesis_messages.append({
                    "role": "system",
                    "content": merged_system_content
                })
            
            # Add all non-system messages after the merged system message
            synthesis_messages.extend(other_messages)
            
            # Add the synthesis prompt as user message
            synthesis_messages.append({
                "role": "user",
                "content": synthesis_prompt
            })
            
            # Save synthesis_messages to /tmp/prompt.txt for debugging
            try:
                import os
                tmp_dir = "/tmp"
                if os.path.exists(tmp_dir):
                    prompt_file_path = os.path.join(tmp_dir, "prompt.txt")
                    with open(prompt_file_path, "w", encoding="utf-8") as f:
                        json.dump(synthesis_messages, f, indent=2, ensure_ascii=False)
                    logger.info(f"Synthesis messages saved to {prompt_file_path}")
            except Exception as e:
                logger.warning(f"Could not save synthesis messages to /tmp/prompt.txt: {e}")
            
            # Use call_advanced with full context
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            response = await llm_client.call_advanced(
                llm_profile=synthesis_profile,
                messages=synthesis_messages,
                temperature=getattr(synthesis_profile, 'temperature', 0.7)
            )
            
            # Synthesis response logged to MongoDB only
            logger.debug(f"Final answer preview: {response[:200]}...")
            
            # URLs are now included directly in the synthesis response by the LLM
            # No need to add them separately to avoid duplication
            
            return response.strip()
        except Exception as e:
            logger.error(f"Failed to synthesize final answer: {str(e)}")
            logger.error(f"Using fallback for synthesis")
            # Fallback: return the best knowledge we have - NO TRUNCATION
            if all_tool_results:
                # Check if any result looks like JSON
                for tr in all_tool_results:
                    if tr.success and tr.result:
                        result_str = str(tr.result)
                        if result_str.startswith('{') or result_str.startswith('['):
                            try:
                                # Try to parse and format JSON
                                parsed = json.loads(result_str)
                                return json.dumps(parsed, indent=2, ensure_ascii=False)
                            except:
                                pass
                # Return the most substantial result
                best_result = max(all_tool_results, 
                                key=lambda r: len(str(r.result)) if r.success and r.result else 0)
                if best_result.success and best_result.result:
                    return str(best_result.result)
            
            # Ultimate fallback
            return "Je n'ai pas pu synthétiser une réponse complète. " + str(e)
    
    async def summarize_tool_result(
        self,
        tool_name: str,
        result: str,
        problem: str,
        iteration_thought: str
    ) -> Dict[str, Any]:
        """Summarize long tool results using Summary LLM Profile from settings, preserving URLs"""
        # First, extract all URLs from the result (reliable method)
        extracted_urls = self.url_extractor.extract_and_validate(result)
        
        try:
            # Get global settings
            settings = await settings_crud.get_or_create()
            if not settings or not settings.summary_llm_profile:
                logger.debug("No Summary LLM profile configured in settings")
                # Fallback to truncation but preserve URLs
                truncated = result[:10000] + "\n... [truncated to 10000 chars]"
                return {
                    "summary": truncated,
                    "urls": extracted_urls
                }
            
            # Get the Summary LLM profile
            summary_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
            if not summary_profile or not summary_profile.active:
                logger.debug(f"Summary LLM profile '{settings.summary_llm_profile}' not found or inactive")
                # Fallback to truncation but preserve URLs
                truncated = result[:10000] + "\n... [truncated to 10000 chars]"
                return {
                    "summary": truncated,
                    "urls": extracted_urls
                }
            
            # Force text mode for summary
            import copy
            summary_profile = copy.deepcopy(summary_profile)
            summary_profile.mode = "text"
            
            # Build list of URLs to force inclusion
            urls_list = "\n".join([f"- {url['url']}" for url in extracted_urls]) if extracted_urls else "Aucune URL trouvée"
            
            # Load and format the summary prompt
            summary_prompt = self.prompt_loader.load_prompt('cot/summarize_tool_result.txt', {
                'problem': problem,
                'iteration_thought': iteration_thought,
                'tool_name': tool_name,
                'result': result
            })
            
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            summary = await llm_client.call_advanced(
                llm_profile=summary_profile,
                prompt=summary_prompt,
                temperature=0.3,
                max_tokens=8192   # As in old version
            )
            
            if summary:
                # Return both summary and URLs
                return {
                    "summary": summary.strip(),
                    "urls": extracted_urls
                }
            else:
                # Fallback to truncation but preserve URLs
                truncated = result[:10000] + "\n... [truncated to 10000 chars]"
                return {
                    "summary": truncated,
                    "urls": extracted_urls
                }
                
        except Exception as e:
            logger.error(f"Failed to summarize tool result: {e}")
            # Fallback to truncation but preserve URLs
            truncated = result[:10000] + "\n... [truncated to 10000 chars]"
            return {
                "summary": truncated,
                "urls": extracted_urls
            }
    
    async def _filter_relevant_urls(
        self, 
        urls: List[Dict[str, str]], 
        problem: str,
        llm_profile: Any,
        max_urls: int = 5
    ) -> List[Dict[str, str]]:
        """Filter URLs to keep only the most relevant ones for the problem"""
        
        if len(urls) <= max_urls:
            return urls
        
        try:
            # Build prompt for URL filtering
            prompt = f"""Given this question: {problem}

Select the {max_urls} most relevant URLs from this list. Return ONLY the numbers of the selected URLs.

URLs:
"""
            for i, url_info in enumerate(urls, 1):
                prompt += f"{i}. {url_info['url']}\n"
                if url_info.get('context'):
                    prompt += f"   Context: {url_info['context'][:100]}...\n"
            
            prompt += f"\nReturn the numbers of the {max_urls} most relevant URLs (e.g., '1, 3, 5, 7, 9'):"
            
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            response = await llm_client.call_advanced(
                llm_profile=llm_profile,
                prompt=prompt,
                temperature=0.3,
                max_tokens=100
            )
            
            # Parse response to get selected indices
            import re
            numbers = re.findall(r'\d+', response)
            selected_indices = [int(n) - 1 for n in numbers[:max_urls]]
            
            # Return selected URLs
            selected = []
            for idx in selected_indices:
                if 0 <= idx < len(urls):
                    selected.append(urls[idx])
            
            # If parsing failed, return top URLs by confidence
            if not selected:
                return sorted(urls, key=lambda x: x.get('confidence', 0.5), reverse=True)[:max_urls]
            
            return selected
            
        except Exception as e:
            logger.error(f"Failed to filter URLs: {e}")
            # Fallback: return first max_urls
            return urls[:max_urls]
    
    async def _describe_urls_with_llm(
        self,
        urls: List[Dict[str, str]],
        llm_profile: Any
    ) -> List[Dict[str, str]]:
        """Generate short descriptions for URLs using LLM"""
        
        if not urls:
            return urls
        
        try:
            # Build prompt for URL descriptions
            prompt = "Pour chaque URL suivante, génère une description courte (1 phrase) basée sur le contexte fourni:\n\n"
            
            for i, url_info in enumerate(urls, 1):
                prompt += f"{i}. URL: {url_info['url']}\n"
                if url_info.get('context'):
                    prompt += f"   Contexte: {url_info['context'][:200]}\n\n"
            
            prompt += """Format de réponse attendu (une ligne par URL):
1. [Description courte et claire]
2. [Description courte et claire]
etc.

Génère EXACTEMENT une description par URL, dans l'ordre."""
            
            from app.core.llm_client import LLMClient
            llm_client = LLMClient()
            
            response = await llm_client.call_advanced(
                llm_profile=llm_profile,
                prompt=prompt,
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse descriptions from response
            lines = response.strip().split('\n')
            descriptions = []
            
            for line in lines:
                # Remove numbering and clean up (handle various formats)
                line = re.sub(r'^\d+\.\s*\[?', '', line)  # Remove "1. [" or "1. "
                line = re.sub(r'\]$', '', line).strip()    # Remove trailing ]
                if line and not line.startswith('URL:') and not line.startswith('Format'):
                    descriptions.append(line)
            
            # Add descriptions to URLs
            for i, url_info in enumerate(urls):
                if i < len(descriptions) and descriptions[i]:
                    url_info['description'] = descriptions[i]
                else:
                    # Fallback description (like in old version)
                    domain = url_info['url'].split('/')[2] if len(url_info['url'].split('/')) > 2 else 'ressource'
                    url_info['description'] = f"Lien vers {domain}"
            
            return urls
            
        except Exception as e:
            logger.error(f"Failed to generate URL descriptions: {e}")
            # Add fallback descriptions to all URLs
            for url_info in urls:
                domain = url_info['url'].split('/')[2] if len(url_info['url'].split('/')) > 2 else 'ressource'
                url_info['description'] = f"Lien vers {domain}"
            return urls