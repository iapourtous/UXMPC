"""
Agent Embedding Service

This module provides embedding functionality for agents using sentence transformers.
Used for semantic agent selection in meta-chat.
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports to avoid initialization issues
SentenceTransformer = None


def _ensure_sentence_transformer():
    """Ensure sentence transformer is imported"""
    global SentenceTransformer
    
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as _ST
            SentenceTransformer = _ST
        except ImportError:
            logger.warning("sentence-transformers not installed. Using mock embeddings.")
            return False
    
    return True


class AgentEmbeddingService:
    """Service for calculating embeddings for agents based on their usage history"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding service
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model_name = model_name
        self.model = None
        
        if _ensure_sentence_transformer():
            try:
                self.model = SentenceTransformer(model_name)
                logger.info(f"Loaded sentence transformer model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load sentence transformer model: {e}")
                self.model = None
        else:
            logger.warning("Sentence transformer not available, using mock embeddings")
    
    def calculate_agent_embedding(self, usage_history: List[Dict[str, str]]) -> Optional[List[float]]:
        """
        Calculate the average embedding for an agent based on its usage history
        
        Args:
            usage_history: List of {"query": str, "response": str} dictionaries
            
        Returns:
            Average embedding vector or None if no history or model unavailable
        """
        if not usage_history:
            return None
            
        if not self.model:
            # Return mock embedding for testing
            return self._create_mock_embedding(usage_history)
        
        try:
            # Extract all responses from usage history
            responses = [entry.get("response", "") for entry in usage_history if entry.get("response")]
            
            if not responses:
                return None
            
            # Calculate embeddings for all responses
            embeddings = self.model.encode(responses)
            
            # Calculate average embedding
            if len(embeddings) == 1:
                avg_embedding = embeddings[0]
            else:
                avg_embedding = np.mean(embeddings, axis=0)
            
            # Convert to Python list
            return avg_embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to calculate agent embedding: {e}")
            return None
    
    def calculate_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Calculate embedding for a user query
        
        Args:
            query: User query string
            
        Returns:
            Query embedding vector or None if model unavailable
        """
        if not query or not self.model:
            if not self.model:
                # Return mock embedding for testing
                return self._create_mock_embedding([{"query": query}])
            return None
        
        try:
            embedding = self.model.encode([query])
            return embedding[0].tolist()
            
        except Exception as e:
            logger.error(f"Failed to calculate query embedding: {e}")
            return None
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        if not vec1 or not vec2:
            return 0.0
        
        try:
            # Convert to numpy arrays
            a = np.array(vec1)
            b = np.array(vec2)
            
            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Failed to calculate cosine similarity: {e}")
            return 0.0
    
    def _create_mock_embedding(self, usage_history: List[Dict[str, str]]) -> List[float]:
        """
        Create a mock embedding for testing when sentence transformers is not available
        
        Args:
            usage_history: Usage history to create mock embedding for
            
        Returns:
            Mock embedding vector
        """
        # Create a simple hash-based mock embedding
        if not usage_history:
            return [0.0] * 384  # Same dimension as MiniLM
        
        # Use text content to create a deterministic "embedding"
        text_content = ""
        for entry in usage_history:
            text_content += entry.get("response", "") + " " + entry.get("query", "")
        
        # Create mock embedding based on text hash
        embedding = []
        for i in range(384):
            # Simple hash-based mock value
            hash_val = hash(text_content + str(i)) % 1000
            embedding.append((hash_val - 500) / 500.0)  # Normalize to -1 to 1
        
        return embedding


# Singleton instance
agent_embedding_service = AgentEmbeddingService()