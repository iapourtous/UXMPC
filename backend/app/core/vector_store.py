"""
Vector Store Service using ChromaDB

This module provides a vector database for storing and searching agent memories
using semantic similarity search.
"""

import logging
import os
from datetime import datetime
import json
from typing import List, Dict, Any, Optional, Tuple

# Lazy imports to avoid initialization issues
chromadb = None
Settings = None
SentenceTransformer = None

def _ensure_imports():
    """Ensure required packages are imported"""
    global chromadb, Settings, SentenceTransformer
    
    if chromadb is None:
        try:
            import chromadb as _chromadb
            from chromadb.config import Settings as _Settings
            chromadb = _chromadb
            Settings = _Settings
        except ImportError:
            logger.warning("ChromaDB not installed. Vector store will be disabled.")
            return False
    
    if SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer as _ST
            SentenceTransformer = _ST
        except ImportError:
            logger.warning("sentence-transformers not installed. Using mock embeddings.")
    
    return True

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store for agent memories using ChromaDB"""
    
    def __init__(self, persist_directory: str = "/data/chromadb"):
        """
        Initialize the vector store
        
        Args:
            persist_directory: Directory to persist the ChromaDB data
        """
        # Ensure imports are available
        if not _ensure_imports():
            raise ImportError("Required packages not available for vector store")
        
        self.persist_directory = persist_directory
        
        # Ensure directory exists
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Initialize sentence transformer for embeddings
        if SentenceTransformer:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        else:
            logger.warning("SentenceTransformer not available - using mock embeddings")
            self.embedding_model = None
        
        logger.info(f"Vector store initialized with persist directory: {persist_directory}")
    
    def create_collection(self, agent_id: str):
        """
        Create or get a collection for an agent
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            ChromaDB collection
        """
        collection_name = f"agent_{agent_id}"
        
        try:
            # Try to get existing collection
            collection = self.client.get_collection(name=collection_name)
            logger.info(f"Retrieved existing collection for agent {agent_id}")
        except ValueError:
            # Create new collection if it doesn't exist
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"agent_id": agent_id, "created_at": datetime.utcnow().isoformat()}
            )
            logger.info(f"Created new collection for agent {agent_id}")
        
        return collection
    
    def add_memory(
        self, 
        agent_id: str, 
        memory_id: str,
        content: str, 
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None
    ) -> None:
        """
        Add a memory to an agent's collection
        
        Args:
            agent_id: The agent's ID
            memory_id: Unique ID for the memory
            content: The content to store
            metadata: Additional metadata
            embedding: Pre-computed embedding (optional)
        """
        collection = self.create_collection(agent_id)
        
        # Generate embedding if not provided
        if embedding is None:
            if self.embedding_model:
                embedding = self.embedding_model.encode(content).tolist()
            else:
                # Fallback to simple hash-based embedding
                embedding = self._simple_embedding(content)
        
        # Ensure metadata is JSON serializable
        clean_metadata = self._clean_metadata(metadata)
        
        # Add to collection
        collection.add(
            embeddings=[embedding],
            documents=[content],
            metadatas=[clean_metadata],
            ids=[memory_id]
        )
        
        logger.info(f"Added memory {memory_id} to agent {agent_id}")
    
    def search_memories(
        self, 
        agent_id: str, 
        query: str, 
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[str, str, Dict[str, Any], float]]:
        """
        Search for similar memories using semantic search
        
        Args:
            agent_id: The agent's ID
            query: The search query
            k: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of tuples (id, content, metadata, score)
        """
        try:
            collection = self.client.get_collection(name=f"agent_{agent_id}")
        except ValueError:
            logger.warning(f"No collection found for agent {agent_id}")
            return []
        
        # Generate query embedding
        if self.embedding_model:
            query_embedding = self.embedding_model.encode(query).tolist()
        else:
            query_embedding = self._simple_embedding(query)
        
        # Search with optional filters
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=filter_dict if filter_dict else None
        )
        
        # Format results
        memories = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                memories.append((
                    results['ids'][0][i],
                    results['documents'][0][i],
                    results['metadatas'][0][i],
                    1 - results['distances'][0][i]  # Convert distance to similarity score
                ))
        
        return memories
    
    def get_recent_memories(
        self, 
        agent_id: str, 
        limit: int = 10,
        content_type: Optional[str] = None
    ) -> List[Tuple[str, str, Dict[str, Any]]]:
        """
        Get recent memories for an agent
        
        Args:
            agent_id: The agent's ID
            limit: Maximum number of memories to return
            content_type: Optional filter by content type
            
        Returns:
            List of tuples (id, content, metadata)
        """
        try:
            collection = self.client.get_collection(name=f"agent_{agent_id}")
        except ValueError:
            logger.warning(f"No collection found for agent {agent_id}")
            return []
        
        # Get all memories (ChromaDB doesn't have direct timestamp ordering)
        # We'll need to fetch all and sort ourselves
        where_clause = {"content_type": content_type} if content_type else None
        results = collection.get(where=where_clause)
        
        if not results['ids']:
            return []
        
        # Combine results with timestamps from metadata
        memories = []
        for i in range(len(results['ids'])):
            timestamp = results['metadatas'][i].get('timestamp', '0')
            memories.append((
                timestamp,
                results['ids'][i],
                results['documents'][i],
                results['metadatas'][i]
            ))
        
        # Sort by timestamp (descending) and return requested limit
        memories.sort(key=lambda x: x[0], reverse=True)
        return [(m[1], m[2], m[3]) for m in memories[:limit]]
    
    def update_memory(
        self, 
        agent_id: str, 
        memory_id: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None
    ) -> bool:
        """
        Update an existing memory
        
        Args:
            agent_id: The agent's ID
            memory_id: ID of the memory to update
            content: New content (optional)
            metadata: New or updated metadata (optional)
            embedding: New embedding (optional)
            
        Returns:
            True if updated successfully
        """
        try:
            collection = self.client.get_collection(name=f"agent_{agent_id}")
            
            # Get existing memory
            existing = collection.get(ids=[memory_id])
            if not existing['ids']:
                logger.warning(f"Memory {memory_id} not found for agent {agent_id}")
                return False
            
            # Prepare update
            update_data = {"ids": [memory_id]}
            
            if content is not None:
                update_data["documents"] = [content]
                if embedding is None:
                    # Generate new embedding for new content
                    if self.embedding_model:
                        embedding = self.embedding_model.encode(content).tolist()
                    else:
                        embedding = self._simple_embedding(content)
            
            if embedding is not None:
                update_data["embeddings"] = [embedding]
            
            if metadata is not None:
                # Merge with existing metadata
                existing_metadata = existing['metadatas'][0]
                existing_metadata.update(metadata)
                update_data["metadatas"] = [self._clean_metadata(existing_metadata)]
            
            # Update in collection
            collection.update(**update_data)
            logger.info(f"Updated memory {memory_id} for agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating memory: {str(e)}")
            return False
    
    def delete_memory(self, agent_id: str, memory_id: str) -> bool:
        """
        Delete a specific memory
        
        Args:
            agent_id: The agent's ID
            memory_id: ID of the memory to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            collection = self.client.get_collection(name=f"agent_{agent_id}")
            collection.delete(ids=[memory_id])
            logger.info(f"Deleted memory {memory_id} for agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting memory: {str(e)}")
            return False
    
    def clear_memories(self, agent_id: str) -> bool:
        """
        Clear all memories for an agent
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            True if cleared successfully
        """
        try:
            collection_name = f"agent_{agent_id}"
            self.client.delete_collection(name=collection_name)
            logger.info(f"Cleared all memories for agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing memories: {str(e)}")
            return False
    
    def get_collection_stats(self, agent_id: str) -> Dict[str, Any]:
        """
        Get statistics about an agent's memory collection
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            Dictionary with collection statistics
        """
        try:
            collection = self.client.get_collection(name=f"agent_{agent_id}")
            
            # Get all memories to calculate stats
            results = collection.get()
            
            if not results['ids']:
                return {
                    "total_memories": 0,
                    "collection_exists": True
                }
            
            # Calculate statistics
            content_types = {}
            for metadata in results['metadatas']:
                ct = metadata.get('content_type', 'unknown')
                content_types[ct] = content_types.get(ct, 0) + 1
            
            return {
                "total_memories": len(results['ids']),
                "collection_exists": True,
                "content_types": content_types,
                "metadata": collection.metadata
            }
            
        except ValueError:
            return {
                "total_memories": 0,
                "collection_exists": False
            }
    
    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean metadata to ensure it's JSON serializable for ChromaDB
        
        Args:
            metadata: Raw metadata dictionary
            
        Returns:
            Cleaned metadata
        """
        clean = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            elif isinstance(value, datetime):
                clean[key] = value.isoformat()
            elif isinstance(value, (list, dict)):
                # Convert to JSON string for complex types
                clean[key] = json.dumps(value)
            else:
                # Convert other types to string
                clean[key] = str(value)
        return clean
    
    def _simple_embedding(self, text: str) -> List[float]:
        """
        Generate a simple hash-based embedding as fallback
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding
        """
        import hashlib
        
        # Simple hash-based pseudo-embedding
        hash_obj = hashlib.sha256(text.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Convert to list of floats (0-1) - 384 dimensions to match all-MiniLM-L6-v2
        embedding = []
        for i in range(0, min(len(hash_hex), 96), 2):  # 96*2 chars = 384 values
            value = int(hash_hex[i:i+2], 16) / 255.0
            embedding.append(value)
        
        # Pad to 384 dimensions if needed
        while len(embedding) < 384:
            embedding.append(0.0)
        
        return embedding


# Global instance
vector_store = None

def get_vector_store() -> VectorStore:
    """Get or create the global vector store instance"""
    global vector_store
    if vector_store is None:
        vector_store = VectorStore()
    return vector_store