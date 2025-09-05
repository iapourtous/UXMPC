"""
N4L File-Based World Model Manager

Manages the collective knowledge as a single N4L file,
following the original Semantic Spacetime philosophy.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from filelock import FileLock
import hashlib

from app.models.n4l_memory import N4LStatement, N4LRelationType

logger = logging.getLogger(__name__)


class N4LFileManager:
    """
    Manages the world model as a single N4L file
    """
    
    def __init__(self, filepath: str = "/data/world_model.n4l"):
        """
        Initialize the N4L file manager
        
        Args:
            filepath: Path to the N4L world model file
        """
        self.filepath = filepath
        self.lock_filepath = f"{filepath}.lock"
        self.ensure_file_exists()
        
    def ensure_file_exists(self):
        """Create the file with header if it doesn't exist"""
        if not os.path.exists(self.filepath):
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            with open(self.filepath, 'w', encoding='utf-8') as f:
                f.write(f"# UXMCP Collective World Model\n")
                f.write(f"# Created: {datetime.utcnow().isoformat()}\n")
                f.write(f"# Format: N4L (Notes for Learning) - Semantic Spacetime\n\n")
    
    def add_statements(self, statements: List[N4LStatement], agent_id: str):
        """
        Add new statements to the world model
        
        Args:
            statements: List of N4L statements to add
            agent_id: ID of the agent adding the statements
        """
        with FileLock(self.lock_filepath):
            # Read existing content
            existing_statements = self._parse_file()
            
            # Group statements by context
            context_groups = self._group_by_context(statements)
            
            # Merge with existing, handling duplicates
            for context, stmts in context_groups.items():
                for stmt in stmts:
                    stmt_hash = self._hash_statement(stmt)
                    
                    # Check if statement already exists
                    existing = existing_statements.get(stmt_hash)
                    if existing:
                        # Update confidence and contributors
                        if agent_id not in existing.contributing_agents:
                            existing.contributing_agents.append(agent_id)
                            existing.confidence = min(1.0, existing.confidence + 0.1)
                            existing.last_validated = datetime.utcnow()
                    else:
                        # Add new statement
                        existing_statements[stmt_hash] = stmt
            
            # Rewrite the entire file with updated content
            self._write_file(existing_statements)
            
            logger.info(f"Added/updated {len(statements)} statements from agent {agent_id}")
    
    def _parse_file(self) -> Dict[str, N4LStatement]:
        """
        Parse the N4L file into statements dictionary
        
        Returns:
            Dictionary of statement_hash -> N4LStatement
        """
        statements = {}
        current_contexts = []
        current_spatial = None
        current_temporal = None
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip comments and empty lines
            if line.startswith('#') or not line:
                i += 1
                continue
            
            # Context markers
            if line.startswith('::'):
                # Extract contexts between :: markers
                context_match = re.match(r'::\s*(.+?)\s*::', line)
                if context_match:
                    contexts_str = context_match.group(1)
                    current_contexts = [c.strip() for c in contexts_str.split(',')]
                i += 1
                continue
            
            # Extended contexts
            if line.startswith('+::'):
                context_match = re.match(r'\+::\s*(.+?)\s*::', line)
                if context_match:
                    extended = context_match.group(1)
                    if '@where:' in extended:
                        current_spatial = extended.split('@where:')[1].strip()
                    elif '@when:' in extended:
                        current_temporal = extended.split('@when:')[1].strip()
                    else:
                        # Don't accumulate intent contexts, just note them without adding to main list
                        # They will be handled separately for each statement
                        pass
                i += 1
                continue
            
            # Statement pattern: subject (predicate) object
            stmt_match = re.match(r'(\w+(?:\s+\w+)*)\s*\(([^)]+)\)\s*(.+)', line)
            if stmt_match:
                subject = stmt_match.group(1).strip()
                predicate = stmt_match.group(2).strip()
                obj = stmt_match.group(3).strip()
                
                # Parse metadata from following comment lines
                confidence = 0.8
                contributors = []
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith('#'):
                    meta_line = lines[j].strip()[1:].strip()
                    if meta_line.startswith('@confidence:'):
                        confidence = float(meta_line.split(':')[1].strip())
                    elif meta_line.startswith('@sources:'):
                        sources_str = meta_line.split('[')[1].split(']')[0]
                        contributors = [s.strip() for s in sources_str.split(',')]
                    j += 1
                
                # Create statement
                stmt = N4LStatement(
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    relation_type=self._infer_relation_type(predicate),
                    contexts=current_contexts.copy(),
                    spatial_context=current_spatial,
                    temporal_context=current_temporal,
                    confidence=confidence,
                    contributing_agents=contributors
                )
                
                stmt_hash = self._hash_statement(stmt)
                statements[stmt_hash] = stmt
                
                i = j
            else:
                i += 1
        
        return statements
    
    def _write_file(self, statements: Dict[str, N4LStatement]):
        """
        Write statements back to the N4L file
        
        Args:
            statements: Dictionary of statement_hash -> N4LStatement
        """
        # Group statements by primary context
        context_groups = {}
        for stmt in statements.values():
            primary_context = stmt.contexts[0] if stmt.contexts else "general"
            if primary_context not in context_groups:
                context_groups[primary_context] = []
            context_groups[primary_context].append(stmt)
        
        # Write to file
        with open(self.filepath, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"# UXMCP Collective World Model\n")
            f.write(f"# Last Updated: {datetime.utcnow().isoformat()}\n")
            f.write(f"# Total Statements: {len(statements)}\n")
            f.write(f"# Format: N4L (Notes for Learning) - Semantic Spacetime\n\n")
            
            # Write each context group
            for context, stmts in sorted(context_groups.items()):
                f.write(f"\n:: {context} ::\n\n")
                
                for stmt in stmts:
                    # Write extended contexts if present
                    intent_contexts = [c.replace("intent:", "") for c in stmt.contexts if c.startswith("intent:")]
                    if intent_contexts:
                        f.write(f"+:: {', '.join(intent_contexts)} ::\n")
                    if stmt.spatial_context:
                        f.write(f"+:: @where: {stmt.spatial_context} ::\n")
                    if stmt.temporal_context:
                        f.write(f"+:: @when: {stmt.temporal_context} ::\n")
                    
                    # Write statement
                    f.write(f"{stmt.subject} ({stmt.predicate}) {stmt.object}\n")
                    
                    # Write metadata
                    if stmt.confidence != 1.0:
                        f.write(f"# @confidence: {stmt.confidence:.2f}\n")
                    if stmt.contributing_agents:
                        f.write(f"# @sources: [{', '.join(stmt.contributing_agents)}]\n")
                    
                    f.write("\n")
    
    def search(self, query: str = None, entity: str = None, context: str = None) -> List[N4LStatement]:
        """
        Search statements in the world model
        
        Args:
            query: Text query (searches all fields)
            entity: Search for statements with this entity
            context: Filter by context
            
        Returns:
            List of matching statements
        """
        statements = self._parse_file()
        results = []
        
        for stmt in statements.values():
            # Filter by context
            if context and context not in stmt.contexts:
                continue
            
            # Filter by entity
            if entity:
                if entity.lower() not in stmt.subject.lower() and entity.lower() not in stmt.object.lower():
                    continue
            
            # Filter by query
            if query:
                query_lower = query.lower()
                if not any(query_lower in field.lower() for field in [
                    stmt.subject, stmt.predicate, stmt.object,
                    ' '.join(stmt.contexts)
                ]):
                    continue
            
            results.append(stmt)
        
        # Sort by confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the world model
        
        Returns:
            Dictionary with stats
        """
        statements = self._parse_file()
        
        # Collect unique entities and agents
        entities = set()
        agents = set()
        contexts = set()
        
        for stmt in statements.values():
            entities.add(stmt.subject)
            entities.add(stmt.object)
            agents.update(stmt.contributing_agents)
            contexts.update(stmt.contexts)
        
        return {
            "file_path": self.filepath,
            "file_size_kb": os.path.getsize(self.filepath) / 1024,
            "total_statements": len(statements),
            "unique_entities": len(entities),
            "unique_agents": len(agents),
            "unique_contexts": len(contexts),
            "last_modified": datetime.fromtimestamp(os.path.getmtime(self.filepath))
        }
    
    def _hash_statement(self, stmt: N4LStatement) -> str:
        """Generate a hash for statement deduplication"""
        # Include contexts in hash to avoid losing context information
        contexts_str = "|".join(sorted(stmt.contexts)) if stmt.contexts else ""
        key = f"{stmt.subject}|{stmt.predicate}|{stmt.object}|{contexts_str}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _group_by_context(self, statements: List[N4LStatement]) -> Dict[str, List[N4LStatement]]:
        """Group statements by their primary context"""
        groups = {}
        for stmt in statements:
            primary = stmt.contexts[0] if stmt.contexts else "general"
            if primary not in groups:
                groups[primary] = []
            groups[primary].append(stmt)
        return groups
    
    def _infer_relation_type(self, predicate: str) -> N4LRelationType:
        """Infer relation type from predicate"""
        predicate_lower = predicate.lower()
        
        if any(word in predicate_lower for word in ["causes", "leads to", "affects", "produces"]):
            return N4LRelationType.CAUSALITY
        elif any(word in predicate_lower for word in ["contains", "has", "includes", "part of"]):
            return N4LRelationType.CONTAINMENT
        elif any(word in predicate_lower for word in ["equals", "similar", "like", "same as"]):
            return N4LRelationType.SIMILARITY
        else:
            return N4LRelationType.PROPERTY


# Singleton instance
n4l_file_manager = N4LFileManager()