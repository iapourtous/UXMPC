"""
Memory Consolidation Service

This service provides intelligent memory consolidation using similarity scoring
and LLM-based summarization to reduce redundancy and improve memory quality.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import numpy as np

from app.models.agent_memory import AgentMemory, AgentMemoryCreate
from app.core.database import get_database
from app.core.memory_config import get_vector_store
from app.core.llm_client import llm_client
from bson import ObjectId

logger = logging.getLogger(__name__)


class NoMoreClustersException(Exception):
    """Raised when no more clusters can be consolidated"""
    pass


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)


class MemoryConsolidationService:
    """Service for consolidating agent memories using similarity clustering"""
    
    def __init__(self):
        self.vector_store = get_vector_store()
        self.collection_name = "agent_memories"
        
    async def calculate_similarity_scores(self, agent_id: str, min_similarity: float = 0.7) -> Tuple[str, Dict]:
        """
        Calculate cumulative similarity scores for all memories
        
        Args:
            agent_id: The agent's ID
            min_similarity: Minimum similarity threshold to consider
            
        Returns:
            Tuple of (memory_id, cluster_data) for the best cluster
        """
        db = get_database()
        
        # Get all memories with embeddings
        memories = await db[self.collection_name].find({
            "agent_id": agent_id,
            "content_type": {"$ne": "consolidated"}  # Don't consolidate already consolidated memories
        }).to_list(None)
        
        if len(memories) < 6:  # Need at least 6 memories to form a cluster of 5 + center
            raise NoMoreClustersException("Not enough memories to consolidate")
        
        # Get embeddings from vector store
        memory_embeddings = {}
        
        # Try to get the collection for this agent
        try:
            collection = self.vector_store.client.get_collection(name=f"agent_{agent_id}")
        except Exception as e:
            logger.warning(f"No collection found for agent {agent_id}: {e}")
            raise NoMoreClustersException(f"No vector collection found for agent {agent_id}")
        
        for memory in memories:
            memory_id = str(memory['_id'])
            # Get embedding from vector store
            try:
                results = collection.get(ids=[memory_id], include=['embeddings'])
                if results and results['embeddings'] and len(results['embeddings']) > 0:
                    memory_embeddings[memory_id] = np.array(results['embeddings'][0])
            except Exception as e:
                logger.debug(f"Could not get embedding for memory {memory_id}: {e}")
        
        if len(memory_embeddings) < 6:
            raise NoMoreClustersException("Not enough memories with embeddings")
        
        # Calculate similarity matrix
        similarity_matrix = {}
        
        for mem_i_id, emb_i in memory_embeddings.items():
            similarities = []
            
            for mem_j_id, emb_j in memory_embeddings.items():
                if mem_i_id != mem_j_id:
                    # Calculate cosine similarity
                    score = cosine_similarity(emb_i, emb_j)
                    
                    if score >= min_similarity:
                        similarities.append((mem_j_id, score))
            
            # Keep top 5 similar memories
            top_5 = sorted(similarities, key=lambda x: x[1], reverse=True)[:5]
            
            if len(top_5) >= 5:  # Only consider if we have at least 5 similar memories
                similarity_matrix[mem_i_id] = top_5
        
        if not similarity_matrix:
            raise NoMoreClustersException("No sufficient similarity clusters found")
        
        # Calculate cumulative scores
        cumulative_scores = {}
        for mem_id, neighbors in similarity_matrix.items():
            total_score = sum(score for _, score in neighbors)
            avg_score = total_score / len(neighbors) if neighbors else 0
            cumulative_scores[mem_id] = {
                'total_score': total_score,
                'avg_score': avg_score,
                'neighbors': [n_id for n_id, _ in neighbors],
                'neighbor_scores': dict(neighbors)
            }
        
        # Return the cluster with the highest cumulative score
        best_cluster = max(cumulative_scores.items(), key=lambda x: x[1]['total_score'])
        logger.info(f"Best cluster identified: {best_cluster[0]} with score {best_cluster[1]['total_score']:.3f}")
        
        return best_cluster
    
    async def get_memories_by_ids(self, memory_ids: List[str]) -> List[Dict]:
        """Get memories by their IDs"""
        db = get_database()
        object_ids = [ObjectId(mid) for mid in memory_ids]
        memories = await db[self.collection_name].find({
            "_id": {"$in": object_ids}
        }).to_list(None)
        return memories
    
    async def llm_consolidate(self, memories: List[Dict], agent_id: str) -> str:
        """
        Use LLM to consolidate memories into a coherent summary
        
        Args:
            memories: List of memory documents to consolidate
            agent_id: The agent's ID for context
            
        Returns:
            Consolidated memory content
        """
        # Prepare memory texts for consolidation
        memory_texts = []
        for i, memory in enumerate(memories, 1):
            content = memory.get('content', '')
            content_type = memory.get('content_type', 'unknown')
            created_at = memory.get('created_at', datetime.utcnow())
            
            memory_texts.append(f"[Memory {i} - {content_type} - {created_at.strftime('%Y-%m-%d')}]:\n{content}")
        
        memories_text = "\n\n".join(memory_texts)
        
        # Prepare consolidation prompt
        from app.core.prompt_loader import PromptLoader
        prompt_loader = PromptLoader()
        
        try:
            consolidation_template = prompt_loader.load_prompt('memory_consolidation.txt')
            prompt = consolidation_template.format(
                count=len(memories),
                memories=memories_text
            )
        except Exception as e:
            logger.error(f"Failed to load memory consolidation prompt: {e}")
            # Fallback prompt
            prompt = f"Consolidate these {len(memories)} similar memories into one:\n\n{memories_text}"
        
        # Use the exact same LLM profile as conversation_compactor.py
        from app.services.settings_crud import settings_crud
        from app.services.llm_crud import llm_crud
        
        # Get global settings to find the summary LLM profile
        settings = await settings_crud.get_or_create()
        
        # Use the same profile as conversation summaries (exactly like conversation_compactor.py line 88)
        llm_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
        
        if not llm_profile or not llm_profile.active:
            logger.error(f"Summary LLM profile '{settings.summary_llm_profile}' not found or inactive")
            # Fallback to simple concatenation
            return f"[Consolidated Memory - {datetime.utcnow().strftime('%Y-%m-%d')}]\n" + \
                   "\n---\n".join([m.get('content', '') for m in memories])
        
        # Call LLM client directly without JSON format
        try:
            # Build messages directly to avoid JSON format issues
            messages = [
                {"role": "system", "content": "You are an expert at memory consolidation and summarization. Create concise yet comprehensive summaries in plain text."},
                {"role": "user", "content": prompt}
            ]
            
            # Call LLM with basic parameters only
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            if response and "choices" in response and response["choices"]:
                content = response["choices"][0]["message"]["content"]
                return content
            else:
                logger.error("LLM returned empty response")
                # Fallback to simple concatenation
                return f"[Consolidated Memory - {datetime.utcnow().strftime('%Y-%m-%d')}]\n" + \
                       "\n---\n".join([m.get('content', '') for m in memories])
                       
        except Exception as e:
            logger.error(f"LLM consolidation failed: {str(e)}")
            # Fallback to simple concatenation
            return f"[Consolidated Memory - {datetime.utcnow().strftime('%Y-%m-%d')}]\n" + \
                   "\n---\n".join([m.get('content', '') for m in memories])
    
    async def consolidate_once(self, agent_id: str) -> Dict[str, Any]:
        """
        Perform one consolidation iteration
        
        Args:
            agent_id: The agent's ID
            
        Returns:
            Dictionary with consolidation results
        """
        try:
            # 1. Identify the best cluster
            cluster_id, cluster_data = await self.calculate_similarity_scores(agent_id)
            
            # 2. Get memories in the cluster (center + neighbors)
            memory_ids = [cluster_id] + cluster_data['neighbors']
            memories = await self.get_memories_by_ids(memory_ids)
            
            if not memories:
                raise NoMoreClustersException("Could not retrieve cluster memories")
            
            logger.info(f"Consolidating {len(memories)} memories for agent {agent_id}")
            
            # 3. Send to LLM for consolidation
            consolidated_content = await self.llm_consolidate(memories, agent_id)
            
            # 4. Create the consolidated memory with importance 0.9
            from app.services.agent_memory_service import agent_memory_service
            
            memory_data = AgentMemoryCreate(
                agent_id=agent_id,
                user_id=memories[0].get('user_id'),  # Preserve user_id if exists
                conversation_id=f"consolidated_{datetime.utcnow().timestamp()}",
                content=consolidated_content,
                content_type="consolidated",
                metadata={
                    "source_memories": memory_ids,
                    "consolidation_date": datetime.utcnow().isoformat(),
                    "similarity_score": cluster_data['total_score'],
                    "avg_similarity": cluster_data['avg_score'],
                    "memories_consolidated": len(memory_ids)
                },
                importance=0.9  # High importance for consolidated memories
            )
            
            # Save to database
            db = get_database()
            memory_dict = memory_data.dict()
            memory_dict['created_at'] = datetime.utcnow()
            memory_dict['updated_at'] = datetime.utcnow()
            
            result = await db[self.collection_name].insert_one(memory_dict)
            new_memory_id = str(result.inserted_id)
            
            # Add to vector store
            self.vector_store.add_memory(
                agent_id=agent_id,
                memory_id=new_memory_id,
                content=consolidated_content,
                metadata=memory_dict['metadata']
            )
            
            # 5. Send to collective memory for N4L conversion
            try:
                from app.services.collective_memory_service import collective_memory_service
                
                collective_memory = await collective_memory_service.process_consolidated_memory(
                    consolidated_content=consolidated_content,
                    agent_id=agent_id,
                    source_memory_ids=memory_ids
                )
                
                if collective_memory:
                    logger.info(f"Added {len(collective_memory.n4l_statements)} N4L statements to collective knowledge")
                    
            except Exception as e:
                # Don't fail consolidation if collective memory fails
                logger.warning(f"Failed to process collective memory: {e}")
            
            # 6. Delete original memories
            await self.delete_memories(agent_id, memory_ids)
            
            logger.info(f"Successfully consolidated {len(memory_ids)} memories into memory {new_memory_id}")
            
            return {
                "consolidated_memory_id": new_memory_id,
                "memories_consolidated": len(memory_ids),
                "similarity_score": cluster_data['total_score'],
                "avg_similarity": cluster_data['avg_score'],
                "content_preview": consolidated_content[:200] + "..." if len(consolidated_content) > 200 else consolidated_content
            }
            
        except NoMoreClustersException as e:
            logger.info(f"No more clusters to consolidate: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error during consolidation: {str(e)}", exc_info=True)
            raise
    
    async def delete_memories(self, agent_id: str, memory_ids: List[str]):
        """Delete memories from both MongoDB and vector store"""
        db = get_database()
        object_ids = [ObjectId(mid) for mid in memory_ids]
        
        # Delete from MongoDB
        delete_result = await db[self.collection_name].delete_many({
            "_id": {"$in": object_ids}
        })
        
        logger.info(f"Deleted {delete_result.deleted_count} memories from MongoDB")
        
        # Delete from vector store
        for memory_id in memory_ids:
            try:
                self.vector_store.delete_memory(agent_id, memory_id)
            except Exception as e:
                logger.warning(f"Failed to delete memory {memory_id} from vector store: {e}")
    
    async def consolidate_batch(self, agent_id: str, iterations: int = 5) -> List[Dict]:
        """
        Perform multiple consolidation iterations
        
        Args:
            agent_id: The agent's ID
            iterations: Number of consolidation iterations to perform
            
        Returns:
            List of consolidation results
        """
        results = []
        
        for i in range(iterations):
            try:
                logger.info(f"Consolidation iteration {i+1}/{iterations} for agent {agent_id}")
                result = await self.consolidate_once(agent_id)
                result['iteration'] = i + 1
                results.append(result)
            except NoMoreClustersException:
                logger.info(f"Stopped at iteration {i+1}: No more clusters to consolidate")
                break
            except Exception as e:
                logger.error(f"Error in iteration {i+1}: {str(e)}")
                # Continue with next iteration
                continue
        
        return results
    
    async def identify_top_clusters(self, agent_id: str, limit: int = 10) -> List[Dict]:
        """
        Preview the top clusters that would be consolidated
        
        Args:
            agent_id: The agent's ID
            limit: Maximum number of clusters to preview
            
        Returns:
            List of cluster previews
        """
        clusters = []
        processed_memories = set()
        
        for _ in range(limit):
            try:
                # Get next best cluster
                cluster_id, cluster_data = await self.calculate_similarity_scores(agent_id)
                
                # Skip if already processed
                if cluster_id in processed_memories:
                    continue
                
                # Get memory previews
                memory_ids = [cluster_id] + cluster_data['neighbors']
                memories = await self.get_memories_by_ids(memory_ids)
                
                cluster_preview = {
                    "cluster_id": cluster_id,
                    "total_score": cluster_data['total_score'],
                    "avg_score": cluster_data['avg_score'],
                    "memory_count": len(memory_ids),
                    "memories": [
                        {
                            "id": str(m['_id']),
                            "content_preview": m['content'][:100] + "..." if len(m['content']) > 100 else m['content'],
                            "content_type": m.get('content_type', 'unknown'),
                            "created_at": m.get('created_at').isoformat() if m.get('created_at') else None
                        }
                        for m in memories[:3]  # Show first 3 memories
                    ]
                }
                
                clusters.append(cluster_preview)
                
                # Mark all memories in this cluster as processed
                processed_memories.update(memory_ids)
                
            except NoMoreClustersException:
                break
            except Exception as e:
                logger.error(f"Error identifying cluster: {str(e)}")
                continue
        
        return clusters


# Singleton instance
memory_consolidation_service = MemoryConsolidationService()