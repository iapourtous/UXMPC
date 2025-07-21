"""
Memory Configuration

This module allows switching between different vector store implementations
"""

import os
import logging

logger = logging.getLogger(__name__)

# Environment variable to control which vector store to use
USE_CHROMADB = os.getenv("USE_CHROMADB", "true").lower() == "true"

def get_vector_store():
    """
    Get the appropriate vector store based on configuration
    
    Returns:
        VectorStore instance (either ChromaDB-based or simple)
    """
    if USE_CHROMADB:
        try:
            from app.core.vector_store import get_vector_store as get_chromadb_store
            logger.info("Using ChromaDB vector store")
            return get_chromadb_store()
        except ImportError as e:
            logger.warning(f"ChromaDB not available: {e}, falling back to simple vector store")
            from app.core.vector_store_simple import get_vector_store as get_simple_store
            return get_simple_store()
    else:
        from app.core.vector_store_simple import get_vector_store as get_simple_store
        logger.info("Using simple in-memory vector store")
        return get_simple_store()