"""
Collective Memory Service

Manages the shared knowledge graph accessible by all agents,
using N4L format and Semantic Spacetime principles.
"""

import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId

from app.models.n4l_memory import (
    N4LStatement, N4LRelationType, CollectiveMemory, 
    N4LGraph, N4LSearchRequest, N4LConsensusRequest
)
from app.services.n4l_converter import n4l_converter
from app.core.database import get_database
from app.core.memory_config import get_vector_store
from app.services.llm_crud import llm_crud
from app.core.llm_client import llm_client
import json

logger = logging.getLogger(__name__)


class CollectiveMemoryService:
    """
    Service for managing collective knowledge graph shared by all agents
    """
    
    def __init__(self):
        self.collection_name = "collective_knowledge"
        self.vector_store = get_vector_store()
        
        # ALWAYS use file-based storage for N4L world model
        from app.services.n4l_file_manager import n4l_file_manager
        self.file_manager = n4l_file_manager
        logger.info("Using file-based storage for N4L world model at /data/world_model.n4l")
        
    async def process_consolidated_memory(
        self,
        consolidated_content: str,
        agent_id: str,
        source_memory_ids: List[str],
        llm_profile_name: Optional[str] = None
    ) -> CollectiveMemory:
        """
        Process a consolidated memory and add it to the collective knowledge
        
        Args:
            consolidated_content: The consolidated memory text
            agent_id: ID of the agent that created this
            source_memory_ids: IDs of memories that were consolidated
            llm_profile_name: Optional LLM profile to use
            
        Returns:
            The created collective memory
        """
        logger.info(f"Processing consolidated memory for collective knowledge from agent {agent_id}")
        
        # Get LLM profile
        if llm_profile_name:
            llm_profile = await llm_crud.get_by_name(llm_profile_name)
        else:
            # Use default summarization profile
            from app.services.settings_crud import settings_crud
            settings = await settings_crud.get_or_create()
            llm_profile = await llm_crud.get_by_name(settings.summary_llm_profile)
        
        if not llm_profile or not llm_profile.active:
            logger.error("No active LLM profile available for N4L conversion")
            return None
        
        # STEP 1: Filter and extract valuable knowledge for collective memory
        filtered_content = await self._filter_collective_knowledge(
            consolidated_content, 
            llm_profile
        )
        
        if not filtered_content:
            logger.info("No valuable collective knowledge found to extract")
            # Fallback: use original content if filtering returns nothing
            filtered_content = consolidated_content
        
        logger.info(f"Knowledge extraction complete")
        
        # STEP 2: Convert filtered content to N4L format
        collective_memory = await n4l_converter.convert_to_n4l(
            filtered_content,
            agent_id,
            source_memory_ids,
            llm_profile
        )
        
        # Always save to N4L file
        self.file_manager.add_statements(collective_memory.n4l_statements, agent_id)
        logger.info(f"Added {len(collective_memory.n4l_statements)} statements to N4L world model file")
        
        # Also save to MongoDB for backup/metadata (optional)
        await self._save_collective_memory(collective_memory)
        
        return collective_memory
    
    async def _filter_collective_knowledge(
        self,
        content: str,
        llm_profile: Any
    ) -> Optional[str]:
        """
        Filter consolidated memory to extract only valuable collective knowledge
        
        Args:
            content: The consolidated memory content
            llm_profile: LLM profile to use
            
        Returns:
            Filtered content with only valuable knowledge, or None if nothing valuable
        """
        try:
            # Load the filtering prompt
            import os
            prompt_path = os.path.join(
                os.path.dirname(__file__),
                "../prompts/memory/knowledge_filter.txt"
            )
            
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            prompt = prompt_template.replace("{content}", content)
            
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert at filtering knowledge for collective intelligence systems."
                },
                {"role": "user", "content": prompt}
            ]
            
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            if response and "choices" in response:
                result = json.loads(response["choices"][0]["message"]["content"])
                
                # Extract the valuable knowledge items
                collective_knowledge = result.get("collective_knowledge", [])
                
                if not collective_knowledge:
                    return None
                
                # Format the filtered content for N4L conversion
                filtered_items = []
                for item in collective_knowledge:
                    if isinstance(item, dict):
                        knowledge = item.get("knowledge", "")
                        domain = item.get("domain", "")
                        if knowledge:
                            # Add domain context if available
                            if domain:
                                filtered_items.append(f"[{domain}] {knowledge}")
                            else:
                                filtered_items.append(knowledge)
                    elif isinstance(item, str):
                        filtered_items.append(item)
                
                if filtered_items:
                    # Join the filtered knowledge items
                    filtered_content = "\n\n".join(filtered_items)
                    
                    # Log filtering summary
                    summary = result.get("filtering_summary", {})
                    logger.info(
                        f"Knowledge filtering: {summary.get('kept_for_collective', 0)} items kept, "
                        f"{summary.get('filtered_out', 0)} items filtered out. "
                        f"Reason: {summary.get('reason', 'N/A')}"
                    )
                    
                    return filtered_content
                
        except Exception as e:
            logger.error(f"Failed to filter collective knowledge: {e}")
            # Fallback: return original content if filtering fails
            return content
        
        return None
    
    async def _save_collective_memory(self, memory: CollectiveMemory):
        """
        Save collective memory to MongoDB
        """
        db = get_database()
        
        memory_dict = memory.dict()
        memory_dict['created_at'] = datetime.utcnow()
        
        # Convert N4L statements to dict format for MongoDB
        memory_dict['n4l_statements'] = [
            stmt.dict() for stmt in memory.n4l_statements
        ]
        
        result = await db[self.collection_name].insert_one(memory_dict)
        memory.id = str(result.inserted_id)
        
        # Store embeddings for each statement
        for stmt in memory.n4l_statements:
            await self._store_statement_embedding(stmt, memory.id)
    
    async def _store_statement_embedding(self, statement: N4LStatement, memory_id: str):
        """
        Generate and store embeddings for a N4L statement
        """
        try:
            # Create searchable text from statement
            search_text = f"{statement.subject} {statement.predicate} {statement.object}"
            if statement.contexts:
                search_text += f" {' '.join(statement.contexts)}"
            
            # Store in vector database
            self.vector_store.add_memory(
                agent_id="collective",  # Special ID for collective memories
                memory_id=f"{memory_id}_{statement.subject}_{statement.object}",
                content=search_text,
                metadata={
                    "relation_type": statement.relation_type,
                    "confidence": statement.confidence,
                    "contexts": statement.contexts,
                    "subject": statement.subject,
                    "object": statement.object,
                    "predicate": statement.predicate
                }
            )
            
            statement.embedding_generated = True
            
        except Exception as e:
            logger.error(f"Failed to store embedding for statement: {e}")
    
    async def _update_knowledge_graph(self, new_statements: List[N4LStatement]):
        """
        Update the global knowledge graph with new statements
        """
        db = get_database()
        
        for stmt in new_statements:
            # Check if similar statement exists
            existing = await db["n4l_statements"].find_one({
                "subject": stmt.subject,
                "predicate": stmt.predicate,
                "object": stmt.object
            })
            
            if existing:
                # Update confidence and contributors
                contributors = set(existing.get("contributing_agents", []))
                contributors.update(stmt.contributing_agents)
                
                new_confidence = min(1.0, existing.get("confidence", 0.5) + 0.1)
                
                await db["n4l_statements"].update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "contributing_agents": list(contributors),
                            "confidence": new_confidence,
                            "last_validated": datetime.utcnow(),
                            "access_count": existing.get("access_count", 0) + 1
                        }
                    }
                )
            else:
                # Insert new statement
                stmt_dict = stmt.dict()
                stmt_dict["created_at"] = datetime.utcnow()
                await db["n4l_statements"].insert_one(stmt_dict)
    
    async def search_knowledge(self, request: N4LSearchRequest) -> List[N4LStatement]:
        """
        Search the collective knowledge graph from N4L file
        
        Args:
            request: Search parameters
            
        Returns:
            List of matching N4L statements
        """
        # Always use file-based search
        results = self.file_manager.search(
            query=request.query,
            entity=request.entity,
            context=request.contexts[0] if request.contexts else None
        )
        
        # Filter by confidence and relation type
        filtered = []
        for stmt in results:
            if stmt.confidence >= request.min_confidence:
                if request.relation_type is None or stmt.relation_type == request.relation_type:
                    filtered.append(stmt)
        
        return filtered[:request.limit]
    
    async def get_entity_graph(self, entity: str, depth: int = 2) -> N4LGraph:
        """
        Get the knowledge graph around a specific entity
        
        Args:
            entity: The entity to explore
            depth: How many hops from the entity to explore
            
        Returns:
            N4LGraph containing related statements
        """
        visited = set()
        to_visit = [entity]
        graph = N4LGraph()
        
        for _ in range(depth):
            if not to_visit:
                break
            
            current_entity = to_visit.pop(0)
            if current_entity in visited:
                continue
            
            visited.add(current_entity)
            
            # Find all statements involving this entity
            search = N4LSearchRequest(entity=current_entity, limit=50)
            statements = await self.search_knowledge(search)
            
            for stmt in statements:
                graph.add_statement(stmt)
                
                # Add connected entities to explore
                if stmt.subject == current_entity and stmt.object not in visited:
                    to_visit.append(stmt.object)
                elif stmt.object == current_entity and stmt.subject not in visited:
                    to_visit.append(stmt.subject)
        
        graph.total_agents = len(set(
            agent for stmt in graph.statements 
            for agent in stmt.contributing_agents
        ))
        
        return graph
    
    async def handle_consensus(self, request: N4LConsensusRequest) -> N4LStatement:
        """
        Handle consensus building for a statement
        
        Args:
            request: Consensus request with statement and action
            
        Returns:
            Updated statement after consensus action
        """
        db = get_database()
        
        # Find the statement
        existing = await db["n4l_statements"].find_one({
            "subject": request.statement.subject,
            "predicate": request.statement.predicate,
            "object": request.statement.object
        })
        
        if request.action == "propose":
            if existing:
                # Already exists, treat as validation
                request.action = "validate"
            else:
                # New statement
                stmt_dict = request.statement.dict()
                stmt_dict["created_at"] = datetime.utcnow()
                stmt_dict["contributing_agents"] = [request.agent_id]
                stmt_dict["confidence"] = 0.6  # Initial confidence
                
                await db["n4l_statements"].insert_one(stmt_dict)
                return request.statement
        
        if not existing:
            logger.warning(f"Statement not found for consensus action: {request.action}")
            return None
        
        if request.action == "validate":
            # Add to contributors if not already there
            contributors = set(existing.get("contributing_agents", []))
            contributors.add(request.agent_id)
            
            # Increase confidence
            new_confidence = min(1.0, existing.get("confidence", 0.5) + 0.1)
            
            await db["n4l_statements"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "contributing_agents": list(contributors),
                        "confidence": new_confidence,
                        "last_validated": datetime.utcnow()
                    },
                    "$inc": {"validation_count": 1}
                }
            )
            
        elif request.action == "dispute":
            # Add to contradicting agents
            contradicting = set(existing.get("contradicting_agents", []))
            contradicting.add(request.agent_id)
            
            # Decrease confidence slightly
            new_confidence = max(0.0, existing.get("confidence", 0.5) - 0.05)
            
            await db["n4l_statements"].update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "contradicting_agents": list(contradicting),
                        "confidence": new_confidence
                    },
                    "$inc": {"dispute_count": 1}
                }
            )
            
            # Log dispute reason if provided
            if request.reason:
                logger.info(f"Agent {request.agent_id} disputed statement: {request.reason}")
        
        # Return updated statement
        updated = await db["n4l_statements"].find_one({"_id": existing["_id"]})
        updated.pop("_id", None)
        return N4LStatement(**updated)
    
    async def get_collective_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collective knowledge graph
        """
        # Get stats from file manager
        file_stats = self.file_manager.get_stats()
        
        # Get additional stats from MongoDB backup
        db = get_database()
        total_memories = await db[self.collection_name].count_documents({})
        
        # Parse statements from file for confidence distribution
        statements = self.file_manager._parse_file()
        high_confidence = sum(1 for s in statements.values() if s.confidence >= 0.8)
        medium_confidence = sum(1 for s in statements.values() if 0.5 <= s.confidence < 0.8)
        low_confidence = sum(1 for s in statements.values() if s.confidence < 0.5)
        
        return {
            "storage_mode": "N4L File",
            "file_path": file_stats["file_path"],
            "file_size_kb": file_stats["file_size_kb"],
            "total_statements": file_stats["total_statements"],
            "total_memories": total_memories,
            "unique_entities": file_stats["unique_entities"],
            "unique_agents": file_stats["unique_agents"],
            "unique_contexts": file_stats["unique_contexts"],
            "confidence_distribution": {
                "high": high_confidence,
                "medium": medium_confidence,
                "low": low_confidence
            },
            "last_updated": file_stats["last_modified"]
        }
    
    async def export_n4l_document(self, domain: Optional[str] = None) -> str:
        """
        Export the knowledge graph as an N4L document
        
        Args:
            domain: Optional domain filter
            
        Returns:
            N4L formatted document as string
        """
        # Read directly from the N4L file
        with open(self.file_manager.filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # If domain filter is specified, filter the content
        if domain:
            lines = content.split('\n')
            filtered_lines = []
            include = False
            
            for line in lines:
                if line.startswith('::'):
                    # Check if this context includes the domain
                    include = domain in line
                    if include:
                        filtered_lines.append(line)
                elif include:
                    filtered_lines.append(line)
                elif line.startswith('#') or not line.strip():
                    # Always include headers and empty lines
                    filtered_lines.append(line)
            
            return '\n'.join(filtered_lines)
        
        return content


# Singleton instance
collective_memory_service = CollectiveMemoryService()