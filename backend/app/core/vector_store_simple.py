"""
Simple Vector Store Service (without ChromaDB)

This module provides a simple in-memory vector store for testing
until ChromaDB compatibility issues are resolved.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import hashlib

logger = logging.getLogger(__name__)


class SimpleVectorStore:
    """Simple in-memory vector store for agent memories"""
    
    def __init__(self, persist_directory: str = "/data/chromadb"):
        """Initialize the simple vector store"""
        self.persist_directory = persist_directory
        self.collections = {}  # agent_id -> list of memories
        logger.info("Simple vector store initialized (ChromaDB disabled)")
    
    def create_collection(self, agent_id: str) -> None:
        """Create or get a collection for an agent"""
        if agent_id not in self.collections:
            self.collections[agent_id] = []
            logger.info(f"Created new collection for agent {agent_id}")
    
    def add_memory(
        self, 
        agent_id: str, 
        memory_id: str,
        content: str, 
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None
    ) -> None:
        """Add a memory to an agent's collection"""
        self.create_collection(agent_id)
        
        # Simple text-based storage
        memory = {
            "id": memory_id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding or self._simple_embedding(content)
        }
        
        self.collections[agent_id].append(memory)
        logger.info(f"Added memory {memory_id} to agent {agent_id}")
    
    def search_memories(
        self, 
        agent_id: str, 
        query: str, 
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, str, Dict[str, Any], float]]:
        """Search for similar memories using simple text matching"""
        if agent_id not in self.collections:
            logger.warning(f"No collection found for agent {agent_id}")
            return []
        
        memories = self.collections[agent_id]
        query_lower = query.lower()
        
        # Simple scoring based on text similarity
        scored_memories = []
        for memory in memories:
            # Apply filters
            if filter_dict:
                skip = False
                for key, value in filter_dict.items():
                    if memory['metadata'].get(key) != value:
                        skip = True
                        break
                if skip:
                    continue
            
            # Simple scoring: count matching words
            content_lower = memory['content'].lower()
            words = query_lower.split()
            score = sum(1 for word in words if word in content_lower) / len(words) if words else 0
            
            if score > 0:
                scored_memories.append((
                    memory['id'],
                    memory['content'],
                    memory['metadata'],
                    score
                ))
        
        # Sort by score and return top k
        scored_memories.sort(key=lambda x: x[3], reverse=True)
        return scored_memories[:k]
    
    def get_recent_memories(
        self, 
        agent_id: str, 
        limit: int = 10,
        content_type: Optional[str] = None
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Get recent memories for an agent"""
        if agent_id not in self.collections:
            logger.warning(f"No collection found for agent {agent_id}")
            return []
        
        memories = self.collections[agent_id]
        
        # Filter by content type if specified
        if content_type:
            memories = [m for m in memories if m['metadata'].get('content_type') == content_type]
        
        # Return most recent (assuming they're added in order)
        recent = memories[-limit:] if len(memories) > limit else memories
        return [(m['id'], m['content'], m['metadata']) for m in reversed(recent)]
    
    def update_memory(
        self, 
        agent_id: str, 
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> bool:
        """Update an existing memory"""
        if agent_id not in self.collections:
            return False
        
        for memory in self.collections[agent_id]:
            if memory['id'] == memory_id:
                if content is not None:
                    memory['content'] = content
                    memory['embedding'] = embedding or self._simple_embedding(content)
                if metadata is not None:
                    memory['metadata'].update(metadata)
                return True
        
        return False
    
    def delete_memory(self, agent_id: str, memory_id: str) -> bool:
        """Delete a specific memory"""
        if agent_id not in self.collections:
            return False
        
        original_len = len(self.collections[agent_id])
        self.collections[agent_id] = [
            m for m in self.collections[agent_id] if m['id'] != memory_id
        ]
        
        return len(self.collections[agent_id]) < original_len
    
    def clear_memories(self, agent_id: str) -> bool:
        """Clear all memories for an agent"""
        if agent_id in self.collections:
            del self.collections[agent_id]
            logger.info(f"Cleared all memories for agent {agent_id}")
            return True
        return False
    
    def get_collection_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics about an agent's memory collection"""
        if agent_id not in self.collections:
            return {
                "total_memories": 0,
                "collection_exists": False
            }
        
        memories = self.collections[agent_id]
        
        # Calculate statistics
        content_types = {}
        for memory in memories:
            ct = memory['metadata'].get('content_type', 'unknown')
            content_types[ct] = content_types.get(ct, 0) + 1
        
        return {
            "total_memories": len(memories),
            "collection_exists": True,
            "content_types": content_types,
            "metadata": {"agent_id": agent_id, "type": "simple_in_memory"}
        }
    
    def _simple_embedding(self, text: str) -> List[float]:
        """Generate a simple hash-based embedding"""
        # Simple hash-based pseudo-embedding
        hash_obj = hashlib.md5(text.encode())
        hash_hex = hash_obj.hexdigest()
        # Convert to list of floats (0-1)
        embedding = []
        for i in range(0, len(hash_hex), 2):
            value = int(hash_hex[i:i+2], 16) / 255.0
            embedding.append(value)
        return embedding


# Global instance
vector_store = None

def get_vector_store() -> SimpleVectorStore:
    """Get or create the global vector store instance"""
    global vector_store
    if vector_store is None:
        vector_store = SimpleVectorStore()
    return vector_store