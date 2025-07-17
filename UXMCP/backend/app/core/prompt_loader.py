"""
Prompt Loader Utility

Centralized prompt management for all LLM interactions in UXMCP.
Loads prompts from text files and supports variable substitution.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PromptLoader:
    """Load and manage prompts from the centralized prompts directory"""
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the prompt loader with base path to prompts directory"""
        if base_path is None:
            # Default to prompts directory in project root
            current_dir = Path(__file__).resolve().parent.parent.parent.parent
            base_path = current_dir / "prompts"
        
        self.base_path = base_path
        self._cache: Dict[str, str] = {}
        
    def load_prompt(self, prompt_path: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Load a prompt from file and substitute variables.
        
        Args:
            prompt_path: Path relative to prompts directory (e.g., "meta_chat/analyze_request.txt")
            variables: Dictionary of variables to substitute in the prompt
            
        Returns:
            The loaded and processed prompt text
        """
        # Check cache first
        if prompt_path in self._cache:
            prompt_text = self._cache[prompt_path]
        else:
            # Load from file
            full_path = self.base_path / prompt_path
            
            if not full_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {full_path}")
            
            with open(full_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
            
            # Cache the loaded prompt
            self._cache[prompt_path] = prompt_text
        
        # Substitute variables if provided
        if variables:
            try:
                prompt_text = prompt_text.format(**variables)
            except KeyError as e:
                logger.error(f"Missing variable in prompt {prompt_path}: {e}")
                raise ValueError(f"Missing required variable: {e}")
        
        return prompt_text
    
    def reload_cache(self):
        """Clear the cache to force reloading of prompts"""
        self._cache.clear()
        logger.info("Prompt cache cleared")
    
    def list_prompts(self) -> Dict[str, list]:
        """List all available prompts organized by directory"""
        prompts = {}
        
        for root, dirs, files in os.walk(self.base_path):
            # Get relative path from base
            rel_path = Path(root).relative_to(self.base_path)
            
            # Skip if no text files
            txt_files = [f for f in files if f.endswith('.txt')]
            if not txt_files:
                continue
            
            # Add to result
            category = str(rel_path) if str(rel_path) != '.' else 'root'
            prompts[category] = txt_files
        
        return prompts
    
    def validate_prompt(self, prompt_path: str) -> Dict[str, Any]:
        """
        Validate a prompt file and extract required variables.
        
        Returns:
            Dictionary with validation results and required variables
        """
        try:
            # Load the prompt
            full_path = self.base_path / prompt_path
            
            if not full_path.exists():
                return {
                    "valid": False,
                    "error": f"File not found: {prompt_path}",
                    "variables": []
                }
            
            with open(full_path, 'r', encoding='utf-8') as f:
                prompt_text = f.read()
            
            # Extract variables (looking for {variable_name} patterns)
            import re
            variables = re.findall(r'\{(\w+)\}', prompt_text)
            unique_variables = list(set(variables))
            
            return {
                "valid": True,
                "variables": unique_variables,
                "length": len(prompt_text),
                "lines": prompt_text.count('\n') + 1
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
                "variables": []
            }


# Singleton instance
prompt_loader = PromptLoader()


# Convenience functions
def load_prompt(prompt_path: str, **kwargs) -> str:
    """Load a prompt with variable substitution"""
    return prompt_loader.load_prompt(prompt_path, kwargs)


def reload_prompts():
    """Reload all prompts (clear cache)"""
    prompt_loader.reload_cache()