"""
N4L Converter Service

Converts consolidated memories into N4L format using LLM-based entity and relation extraction.
"""

import logging
import json
import re
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from app.models.n4l_memory import (
    N4LStatement, N4LRelationType, CollectiveMemory, N4LGraph
)
from app.core.llm_client import llm_client
from app.core.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class N4LConverter:
    """
    Converts text memories into N4L knowledge graph statements
    """
    
    def __init__(self):
        self.prompt_loader = PromptLoader()
        
    async def convert_to_n4l(
        self, 
        consolidated_content: str,
        agent_id: str,
        source_memory_ids: List[str],
        llm_profile: Any
    ) -> CollectiveMemory:
        """
        Convert a consolidated memory into N4L statements
        
        Args:
            consolidated_content: The consolidated memory text
            agent_id: ID of the agent processing this
            source_memory_ids: IDs of source memories that were consolidated
            llm_profile: LLM profile to use for extraction
            
        Returns:
            CollectiveMemory with extracted N4L statements
        """
        logger.info(f"Converting consolidated memory to N4L for agent {agent_id}")
        
        # Step 1: Extract entities and relations
        entities, relations = await self._extract_entities_relations(
            consolidated_content, llm_profile
        )
        
        # Step 2: Convert to N4L statements
        n4l_statements = await self._relations_to_n4l(
            entities, relations, consolidated_content, llm_profile
        )
        
        # Step 3: Add metadata to statements
        for stmt in n4l_statements:
            stmt.contributing_agents = [agent_id]
            stmt.source_memory_ids = source_memory_ids
        
        # Create collective memory
        collective_memory = CollectiveMemory(
            raw_content=consolidated_content,
            n4l_statements=n4l_statements,
            extracted_entities=entities,
            extracted_relations=relations,
            processing_agent=agent_id,
            processing_llm_profile=getattr(llm_profile, 'name', 'unknown')
        )
        
        logger.info(f"Extracted {len(n4l_statements)} N4L statements from consolidated memory")
        
        return collective_memory
    
    async def _extract_entities_relations(
        self, 
        content: str, 
        llm_profile: Any
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Extract entities and their relationships from text
        """
        try:
            # Build the extraction prompt
            prompt = self._build_extraction_prompt(content)
            
            messages = [
                {"role": "system", "content": "You are an expert at knowledge extraction and graph construction."},
                {"role": "user", "content": prompt}
            ]
            
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.3,  # Low temperature for consistent extraction
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            if response and "choices" in response and response["choices"]:
                result_text = response["choices"][0]["message"]["content"]
                result = json.loads(result_text)
                
                entities = result.get("entities", [])
                relations = result.get("relations", [])
                
                return entities, relations
            
        except Exception as e:
            logger.error(f"Failed to extract entities and relations: {e}")
            
        # Fallback: basic extraction
        return self._fallback_extraction(content)
    
    def _build_extraction_prompt(self, content: str) -> str:
        """Build the prompt for entity and relation extraction"""
        return f"""Extract entities and relationships from this consolidated memory content.

Content:
{content}

Please extract:
1. Entities: Important concepts, tools, technologies, people, or things mentioned
2. Relations: How these entities relate to each other

Return a JSON object with this structure:
{{
    "entities": ["entity1", "entity2", ...],
    "relations": [
        {{
            "subject": "entity1",
            "predicate": "relationship_type", 
            "object": "entity2",
            "context": "optional context"
        }},
        ...
    ]
}}

Focus on factual, reusable knowledge that would benefit other agents.
Examples of good relationships:
- "Python" -> "is good for" -> "machine learning"
- "NumPy" -> "improves" -> "computational speed"
- "TensorFlow" -> "is part of" -> "Python ecosystem"
- "User" -> "prefers" -> "simple syntax"

Return ONLY valid JSON."""
    
    async def _relations_to_n4l(
        self,
        entities: List[str],
        relations: List[Dict[str, Any]],
        original_content: str,
        llm_profile: Any
    ) -> List[N4LStatement]:
        """
        Convert extracted relations to N4L statements with proper types and contexts
        """
        n4l_statements = []
        
        for relation in relations:
            # Classify the relation type
            relation_type = await self._classify_relation_type(
                relation, llm_profile
            )
            
            # Extract context with LLM for better understanding
            contexts, spatial, temporal = await self._extract_contexts_with_llm(
                relation, original_content, llm_profile
            )
            
            # Create N4L statement with full spacetime coordinates
            stmt = N4LStatement(
                subject=relation["subject"],
                predicate=relation["predicate"],
                object=relation["object"],
                relation_type=relation_type,
                contexts=contexts,
                spatial_context=spatial,
                temporal_context=temporal,
                confidence=0.8  # Default confidence for single-agent extraction
            )
            
            n4l_statements.append(stmt)
        
        return n4l_statements
    
    async def _classify_relation_type(
        self, 
        relation: Dict[str, Any],
        llm_profile: Any
    ) -> N4LRelationType:
        """
        Classify a relation into one of the 4 N4L types
        """
        predicate = relation.get("predicate", "").lower()
        
        # Quick classification based on common predicates
        similarity_words = ["equals", "similar", "like", "same as", "equivalent"]
        causality_words = ["causes", "leads to", "affects", "results in", "then", "produces"]
        containment_words = ["contains", "has", "includes", "part of", "component", "belongs to"]
        property_words = ["is", "has property", "described as", "means", "defined as"]
        
        if any(word in predicate for word in similarity_words):
            return N4LRelationType.SIMILARITY
        elif any(word in predicate for word in causality_words):
            return N4LRelationType.CAUSALITY
        elif any(word in predicate for word in containment_words):
            return N4LRelationType.CONTAINMENT
        elif any(word in predicate for word in property_words):
            return N4LRelationType.PROPERTY
        
        # If no quick match, use LLM for classification
        try:
            prompt = f"""Classify this relationship into one of 4 types:
0: SIMILARITY (things that are similar, equivalent, or near each other)
1: CAUSALITY (one thing causes, leads to, or affects another)
2: CONTAINMENT (one thing contains, has parts, or hierarchical relationships)
3: PROPERTY (descriptive attributes or properties)

Relationship: "{relation['subject']}" -> "{relation['predicate']}" -> "{relation['object']}"

Return ONLY the number (0, 1, 2, or 3)."""

            messages = [
                {"role": "system", "content": "You are a relation classifier."},
                {"role": "user", "content": prompt}
            ]
            
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.1,
                max_tokens=10
            )
            
            if response and "choices" in response:
                result = response["choices"][0]["message"]["content"].strip()
                if result in ["0", "1", "2", "3"]:
                    return N4LRelationType(int(result))
                    
        except Exception as e:
            logger.warning(f"Failed to classify relation type: {e}")
        
        # Default to property type
        return N4LRelationType.PROPERTY
    
    async def _extract_contexts_with_llm(
        self, 
        relation: Dict[str, Any], 
        content: str,
        llm_profile: Any
    ) -> Tuple[List[str], Optional[str], Optional[str]]:
        """
        Extract contexts using LLM to understand intentional stance and spacetime coordinates
        Returns: (contexts, spatial_context, temporal_context)
        """
        try:
            prompt = f"""Extract semantic spacetime contexts from this knowledge relation.

In N4L/Semantic Spacetime, context represents:
- WHERE this knowledge applies (spatial/domain context)
- WHEN this knowledge is valid (temporal context)
- The INTENTIONAL STANCE (what circumstances make this relevant)

Relation: "{relation['subject']}" -> "{relation['predicate']}" -> "{relation['object']}"
Full content: {content[:500]}

Return JSON with:
{{
    "contexts": ["domain1", "domain2"],  // Main context domains
    "spatial": "where this applies",     // Optional: spatial/scope context
    "temporal": "when this is valid",    // Optional: temporal context
    "intentional": "circumstance"        // Optional: intentional stance
}}

Focus on creating meaningful contexts that help retrieve this knowledge later."""

            messages = [
                {"role": "system", "content": "You are an expert in semantic spacetime and context extraction."},
                {"role": "user", "content": prompt}
            ]
            
            response = await llm_client.call(
                llm_profile=llm_profile,
                messages=messages,
                temperature=0.3,
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            if response and "choices" in response:
                result = json.loads(response["choices"][0]["message"]["content"])
                
                contexts = result.get("contexts", ["general"])
                spatial = result.get("spatial")
                temporal = result.get("temporal")
                
                # Deduplicate contexts
                contexts = list(set(contexts))
                
                # Add intentional context if provided (avoid duplicates)
                if result.get("intentional"):
                    intent_context = f"intent:{result['intentional']}"
                    if intent_context not in contexts:
                        contexts.append(intent_context)
                
                return contexts, spatial, temporal
                
        except Exception as e:
            logger.warning(f"Failed to extract contexts with LLM: {e}")
        
        # Fallback to simple extraction
        return self._extract_contexts(relation, content), None, None
    
    def _extract_contexts(self, relation: Dict[str, Any], content: str) -> List[str]:
        """
        Extract contextual domains from the relation and content
        """
        contexts = []
        
        # Check for common domain keywords
        tech_keywords = ["python", "java", "code", "programming", "software", "api", "database"]
        ml_keywords = ["machine learning", "ml", "ai", "neural", "model", "training"]
        business_keywords = ["customer", "business", "market", "sales", "revenue"]
        science_keywords = ["research", "study", "experiment", "hypothesis", "theory"]
        
        combined_text = f"{relation.get('subject', '')} {relation.get('object', '')} {content}".lower()
        
        if any(kw in combined_text for kw in tech_keywords):
            contexts.append("technology")
        if any(kw in combined_text for kw in ml_keywords):
            contexts.append("machine_learning")
        if any(kw in combined_text for kw in business_keywords):
            contexts.append("business")
        if any(kw in combined_text for kw in science_keywords):
            contexts.append("science")
        
        # Add custom context from relation if provided
        if "context" in relation and relation["context"]:
            contexts.append(relation["context"])
        
        return contexts if contexts else ["general"]
    
    def _fallback_extraction(self, content: str) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Fallback entity extraction using regex patterns
        """
        entities = []
        relations = []
        
        # Extract capitalized words as potential entities
        words = re.findall(r'\b[A-Z][a-z]+\b', content)
        entities = list(set(words))[:10]  # Limit to 10 entities
        
        # Look for simple patterns like "X is Y" or "X uses Y"
        patterns = [
            r'(\w+)\s+(?:is|are|was|were)\s+(\w+)',
            r'(\w+)\s+(?:uses|using|used)\s+(\w+)',
            r'(\w+)\s+(?:has|have|had)\s+(\w+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches[:5]:  # Limit relations
                relations.append({
                    "subject": match[0],
                    "predicate": "relates_to",
                    "object": match[1]
                })
        
        logger.warning(f"Using fallback extraction: found {len(entities)} entities, {len(relations)} relations")
        return entities, relations
    
    async def merge_with_consensus(
        self,
        new_statements: List[N4LStatement],
        existing_statements: List[N4LStatement],
        agent_id: str
    ) -> List[N4LStatement]:
        """
        Merge new statements with existing ones, updating consensus
        """
        merged = existing_statements.copy()
        
        for new_stmt in new_statements:
            # Find matching existing statement
            match_found = False
            
            for existing in merged:
                if (existing.subject == new_stmt.subject and 
                    existing.predicate == new_stmt.predicate and 
                    existing.object == new_stmt.object):
                    
                    # Update consensus
                    if agent_id not in existing.contributing_agents:
                        existing.contributing_agents.append(agent_id)
                        existing.confidence = min(1.0, existing.confidence + 0.1)
                        existing.last_validated = datetime.utcnow()
                    
                    match_found = True
                    break
            
            if not match_found:
                # Add as new statement
                merged.append(new_stmt)
        
        return merged


# Singleton instance
n4l_converter = N4LConverter()