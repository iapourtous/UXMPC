"""
N4L Memory Model for Collective Knowledge Graph

Based on Semantic Spacetime and N4L (Notes for Learning) format
for representing shared knowledge between agents.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import IntEnum


class N4LRelationType(IntEnum):
    """
    Four fundamental relation types in N4L/Semantic Spacetime
    """
    SIMILARITY = 0  # Proximity, similarity, equivalence (bidirectional)
    CAUSALITY = 1   # Leads to, causes, affects, then (directional)
    CONTAINMENT = 2 # Contains, has part, is part of (hierarchical)
    PROPERTY = 3    # Has property, describes, means (attributive)


class N4LStatement(BaseModel):
    """
    A single N4L statement representing a knowledge relationship
    """
    # Core N4L structure
    subject: str = Field(..., description="The subject entity")
    predicate: str = Field(..., description="The relationship/verb")
    object: str = Field(..., description="The object entity or value")
    relation_type: N4LRelationType = Field(..., description="Type of relationship (0-3)")
    
    # Context and domains
    contexts: List[str] = Field(default=[], description="Contextual domains (e.g., 'technology', 'ML')")
    
    # Semantic spacetime coordinates
    spatial_context: Optional[str] = Field(None, description="Where this knowledge applies")
    temporal_context: Optional[str] = Field(None, description="When this knowledge is/was valid")
    
    # Confidence and consensus
    confidence: float = Field(0.5, ge=0.0, le=1.0, description="Confidence score from consensus")
    contributing_agents: List[str] = Field(default=[], description="Agents that contributed this knowledge")
    contradicting_agents: List[str] = Field(default=[], description="Agents that disagree")
    
    # Metadata
    source_memory_ids: List[str] = Field(default=[], description="Source consolidated memory IDs")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_validated: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = Field(default=0, description="How often this knowledge is accessed")
    
    # Embeddings for semantic search
    embedding_generated: bool = Field(default=False, description="Whether embeddings have been generated")
    
    def to_n4l_syntax(self) -> str:
        """
        Convert to N4L syntax format with proper context hierarchy
        """
        # Map relation types to N4L operators
        operators = {
            N4LRelationType.SIMILARITY: "equals",
            N4LRelationType.CAUSALITY: "causes",
            N4LRelationType.CONTAINMENT: "contains",
            N4LRelationType.PROPERTY: "has_property"
        }
        
        operator = operators.get(self.relation_type, self.predicate)
        
        # Build hierarchical context with proper N4L syntax
        context_lines = []
        
        # Primary contexts (domains)
        primary_contexts = [c for c in self.contexts if not c.startswith("intent:")]
        if primary_contexts:
            context_lines.append(f":: {', '.join(primary_contexts)} ::")
        
        # Intentional stance contexts (deduplicated)
        intent_contexts = list(set([c.replace("intent:", "") for c in self.contexts if c.startswith("intent:")]))
        if intent_contexts:
            # Take only the first if there are duplicates or very long contexts
            if len(intent_contexts) == 1:
                context_lines.append(f"+:: {intent_contexts[0]} ::")
            else:
                # Join unique contexts, limit length
                unique_intents = ', '.join(intent_contexts[:3])  # Max 3 contexts
                if len(unique_intents) > 200:  # Truncate if too long
                    unique_intents = unique_intents[:197] + "..."
                context_lines.append(f"+:: {unique_intents} ::")
        
        # Spatial-temporal contexts as sub-contexts
        if self.spatial_context:
            context_lines.append(f"+:: @where: {self.spatial_context} ::")
        if self.temporal_context:
            context_lines.append(f"+:: @when: {self.temporal_context} ::")
        
        context_str = "\n".join(context_lines) + "\n" if context_lines else ""
        
        # Build the statement with proper N4L syntax
        # Use the actual predicate for more natural language
        if self.predicate and self.predicate != operator:
            statement = f"{self.subject} ({self.predicate}) {self.object}"
        else:
            statement = f"{self.subject} ({operator}) {self.object}"
        
        # Add metadata as N4L comments
        metadata = []
        if self.confidence != 1.0:
            metadata.append(f"@confidence: {self.confidence:.2f}")
        if self.contributing_agents:
            metadata.append(f"@sources: [{', '.join(self.contributing_agents)}]")
        if self.access_count > 0:
            metadata.append(f"@accessed: {self.access_count} times")
        
        metadata_str = "\n".join([f"# {m}" for m in metadata])
        
        return f"{context_str}{statement}\n{metadata_str}" if metadata else f"{context_str}{statement}"
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class N4LGraph(BaseModel):
    """
    A collection of N4L statements forming a knowledge graph
    """
    statements: List[N4LStatement] = Field(default=[], description="All statements in the graph")
    domains: List[str] = Field(default=[], description="Knowledge domains covered")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    total_agents: int = Field(default=0, description="Number of unique contributing agents")
    
    def add_statement(self, statement: N4LStatement):
        """Add a new statement to the graph"""
        self.statements.append(statement)
        # Update domains
        for context in statement.contexts:
            if context not in self.domains:
                self.domains.append(context)
        self.last_updated = datetime.utcnow()
    
    def find_related(self, entity: str, relation_type: Optional[N4LRelationType] = None) -> List[N4LStatement]:
        """Find all statements related to an entity"""
        related = []
        for stmt in self.statements:
            if relation_type is not None and stmt.relation_type != relation_type:
                continue
            if stmt.subject == entity or stmt.object == entity:
                related.append(stmt)
        return related
    
    def to_n4l_document(self) -> str:
        """Export entire graph as N4L document"""
        lines = ["# Collective Knowledge Graph", f"# Generated: {datetime.utcnow().isoformat()}", ""]
        
        # Group by domain
        domain_statements = {}
        for stmt in self.statements:
            domain = stmt.contexts[0] if stmt.contexts else "general"
            if domain not in domain_statements:
                domain_statements[domain] = []
            domain_statements[domain].append(stmt)
        
        # Write each domain section
        for domain, stmts in domain_statements.items():
            lines.append(f"\n:: {domain} ::\n")
            for stmt in stmts:
                lines.append(stmt.to_n4l_syntax())
                lines.append("")
        
        return "\n".join(lines)


class CollectiveMemory(BaseModel):
    """
    A collective memory entry that can be shared across agents
    """
    id: Optional[str] = Field(None, description="Unique identifier")
    n4l_statements: List[N4LStatement] = Field(default=[], description="N4L statements extracted")
    raw_content: str = Field(..., description="Original consolidated content")
    
    # Extraction metadata
    extracted_entities: List[str] = Field(default=[], description="Entities found in content")
    extracted_relations: List[Dict[str, Any]] = Field(default=[], description="Raw relations before N4L conversion")
    
    # Processing metadata
    processing_agent: Optional[str] = Field(None, description="Agent that processed this memory")
    processing_timestamp: datetime = Field(default_factory=datetime.utcnow)
    processing_llm_profile: Optional[str] = Field(None, description="LLM profile used for extraction")
    
    # Consensus tracking
    validation_count: int = Field(default=0, description="Times validated by other agents")
    dispute_count: int = Field(default=0, description="Times disputed by other agents")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class N4LSearchRequest(BaseModel):
    """Request model for searching the collective knowledge graph"""
    query: Optional[str] = Field(None, description="Text query for semantic search")
    entity: Optional[str] = Field(None, description="Find statements about this entity")
    relation_type: Optional[N4LRelationType] = Field(None, description="Filter by relation type")
    contexts: Optional[List[str]] = Field(None, description="Filter by contexts/domains")
    min_confidence: float = Field(0.5, description="Minimum confidence threshold")
    limit: int = Field(10, description="Maximum results to return")


class N4LConsensusRequest(BaseModel):
    """Request for building consensus on a statement"""
    statement: N4LStatement
    agent_id: str = Field(..., description="Agent proposing/validating the statement")
    action: Literal["propose", "validate", "dispute"] = Field(..., description="Consensus action")
    reason: Optional[str] = Field(None, description="Reason for validation or dispute")