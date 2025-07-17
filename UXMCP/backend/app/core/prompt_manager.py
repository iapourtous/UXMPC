"""
Prompt Manager for UXMCP

This module handles loading, caching, and managing prompts from files.
It also provides functionality for dynamic prompt updates based on user feedback.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class PromptManager:
    """Manages prompts loaded from files with caching and hot-reload support"""
    
    def __init__(self, prompts_dir: str = None):
        """Initialize the prompt manager
        
        Args:
            prompts_dir: Path to prompts directory, defaults to backend/app/prompts
        """
        if prompts_dir is None:
            # Get the directory relative to this file
            current_dir = Path(__file__).parent.parent
            prompts_dir = current_dir / "prompts"
        
        self.prompts_dir = Path(prompts_dir)
        self._cache = {}
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all prompt directories exist"""
        subdirs = [
            "meta_chat",
            "agent_service", 
            "meta_agent",
            "service_generator",
            "tool_analyzer",
            "chat",
            "llm_profiles"
        ]
        
        for subdir in subdirs:
            (self.prompts_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    @lru_cache(maxsize=128)
    def load_prompt(self, prompt_path: str, **kwargs) -> str:
        """Load a prompt from file with variable substitution
        
        Args:
            prompt_path: Path relative to prompts directory (e.g., "meta_chat/analyze_request.txt")
            **kwargs: Variables to substitute in the prompt
            
        Returns:
            The loaded and formatted prompt string
        """
        full_path = self.prompts_dir / prompt_path
        
        if not full_path.exists():
            # Try with .txt extension if not provided
            if not prompt_path.endswith('.txt'):
                full_path = self.prompts_dir / f"{prompt_path}.txt"
            
            if not full_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                prompt_content = f.read()
            
            # Substitute variables if provided
            if kwargs:
                prompt_content = prompt_content.format(**kwargs)
            
            return prompt_content
            
        except Exception as e:
            logger.error(f"Error loading prompt {prompt_path}: {str(e)}")
            raise
    
    def save_prompt(self, prompt_path: str, content: str) -> bool:
        """Save or update a prompt file
        
        Args:
            prompt_path: Path relative to prompts directory
            content: The prompt content to save
            
        Returns:
            True if successful, False otherwise
        """
        full_path = self.prompts_dir / prompt_path
        
        # Ensure .txt extension
        if not prompt_path.endswith('.txt'):
            full_path = self.prompts_dir / f"{prompt_path}.txt"
        
        try:
            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save the prompt
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Clear cache for this prompt
            self.clear_cache(prompt_path)
            
            logger.info(f"Saved prompt: {prompt_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving prompt {prompt_path}: {str(e)}")
            return False
    
    def update_prompt_with_feedback(
        self, 
        prompt_path: str, 
        feedback: str,
        current_output: str,
        expected_output: str
    ) -> str:
        """Update a prompt based on user feedback
        
        Args:
            prompt_path: Path to the prompt to update
            feedback: User feedback about what went wrong
            current_output: What the system currently produced
            expected_output: What the user expected
            
        Returns:
            The updated prompt content
        """
        current_prompt = self.load_prompt(prompt_path)
        
        # Create a feedback section to append
        feedback_section = f"""

# USER FEEDBACK INCORPORATED ({self._get_timestamp()})
# Feedback: {feedback}
# Current output was: {current_output[:200]}...
# Expected output was: {expected_output[:200]}...
# 
# ADJUSTMENT: Based on this feedback, the prompt has been updated to better align with user expectations.
"""
        
        # For now, append feedback as a comment
        # In a more sophisticated system, we'd use an LLM to intelligently update the prompt
        updated_prompt = current_prompt + feedback_section
        
        # Save with versioning
        self._save_prompt_version(prompt_path, current_prompt)
        self.save_prompt(prompt_path, updated_prompt)
        
        return updated_prompt
    
    def _save_prompt_version(self, prompt_path: str, content: str):
        """Save a version of the prompt for rollback"""
        version_path = self.prompts_dir / "versions" / f"{prompt_path}.{self._get_timestamp()}"
        version_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(version_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _get_timestamp(self) -> str:
        """Get current timestamp for versioning"""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    def clear_cache(self, prompt_path: str = None):
        """Clear cached prompts
        
        Args:
            prompt_path: Specific prompt to clear, or None to clear all
        """
        if prompt_path:
            # Clear specific prompt from LRU cache
            self.load_prompt.cache_clear()
        else:
            # Clear all
            self.load_prompt.cache_clear()
    
    def list_prompts(self, category: str = None) -> List[str]:
        """List all available prompts
        
        Args:
            category: Filter by category (subdirectory) or None for all
            
        Returns:
            List of prompt paths
        """
        prompts = []
        
        if category:
            category_path = self.prompts_dir / category
            if category_path.exists():
                for file in category_path.glob("*.txt"):
                    prompts.append(f"{category}/{file.name}")
        else:
            # List all prompts
            for subdir in self.prompts_dir.iterdir():
                if subdir.is_dir() and subdir.name != "versions":
                    for file in subdir.glob("*.txt"):
                        prompts.append(f"{subdir.name}/{file.name}")
        
        return sorted(prompts)
    
    def get_prompt_metadata(self, prompt_path: str) -> Dict[str, Any]:
        """Get metadata about a prompt
        
        Args:
            prompt_path: Path to the prompt
            
        Returns:
            Dictionary with metadata (size, modified time, etc.)
        """
        full_path = self.prompts_dir / prompt_path
        
        if not full_path.exists() and not prompt_path.endswith('.txt'):
            full_path = self.prompts_dir / f"{prompt_path}.txt"
        
        if not full_path.exists():
            return {}
        
        stat = full_path.stat()
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "path": str(full_path),
            "category": prompt_path.split('/')[0] if '/' in prompt_path else None
        }


# Global instance
prompt_manager = PromptManager()


# Convenience functions
def load_prompt(prompt_path: str, **kwargs) -> str:
    """Load a prompt from file with variable substitution"""
    return prompt_manager.load_prompt(prompt_path, **kwargs)


def save_prompt(prompt_path: str, content: str) -> bool:
    """Save or update a prompt file"""
    return prompt_manager.save_prompt(prompt_path, content)


def update_prompt_with_feedback(
    prompt_path: str,
    feedback: str,
    current_output: str,
    expected_output: str
) -> str:
    """Update a prompt based on user feedback"""
    return prompt_manager.update_prompt_with_feedback(
        prompt_path, feedback, current_output, expected_output
    )