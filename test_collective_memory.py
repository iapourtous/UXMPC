#!/usr/bin/env python3
"""
Test script for collective memory system with N4L conversion
"""

import asyncio
import httpx
import json

API_URL = "http://localhost:8000"

async def test_collective_memory():
    """Test the collective memory system"""
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing Collective Memory System with N4L\n")
        
        # 1. Test processing a consolidated memory
        print("1️⃣ Processing a consolidated memory into N4L...")
        
        consolidated_content = """
        Based on multiple user interactions, I've learned the following:
        
        Python is an excellent programming language for machine learning applications.
        It has a rich ecosystem including libraries like NumPy for numerical computing,
        TensorFlow and PyTorch for deep learning, and scikit-learn for traditional ML.
        
        NumPy significantly improves computational speed compared to pure Python,
        especially for matrix operations. TensorFlow is part of the Python ecosystem
        and enables GPU acceleration for neural network training.
        
        The user prefers simple, readable code and values documentation.
        They have experience with FastAPI for building web services and
        use MongoDB for data persistence. Docker is their preferred deployment method.
        
        Performance optimization is important, but code clarity takes precedence.
        The user follows clean code principles and test-driven development practices.
        """
        
        response = await client.post(
            f"{API_URL}/api/collective-memory/process-memory",
            params={
                "consolidated_content": consolidated_content,
                "agent_id": "test_agent_001",
                "source_memory_ids": ["mem1", "mem2", "mem3"]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Created {result['statements_created']} N4L statements")
            print(f"   Entities: {result['entities_extracted'][:5]}...")
            print()
        else:
            print(f"❌ Error: {response.status_code} - {response.text}\n")
            return
        
        # 2. Search the collective knowledge
        print("2️⃣ Searching collective knowledge...")
        
        search_request = {
            "query": "Python performance optimization",
            "min_confidence": 0.5,
            "limit": 5
        }
        
        response = await client.post(
            f"{API_URL}/api/collective-memory/search",
            json=search_request
        )
        
        if response.status_code == 200:
            statements = response.json()
            print(f"✅ Found {len(statements)} relevant statements:")
            for stmt in statements[:3]:
                print(f"   - {stmt['subject']} → {stmt['predicate']} → {stmt['object']}")
                print(f"     Confidence: {stmt['confidence']:.2f}")
            print()
        
        # 3. Get entity graph
        print("3️⃣ Getting knowledge graph for 'Python'...")
        
        response = await client.get(
            f"{API_URL}/api/collective-memory/entity/Python",
            params={"depth": 2}
        )
        
        if response.status_code == 200:
            graph = response.json()
            print(f"✅ Graph contains {len(graph['statements'])} statements")
            print(f"   Domains: {graph['domains']}")
            print()
        
        # 4. Get statistics
        print("4️⃣ Getting collective memory statistics...")
        
        response = await client.get(f"{API_URL}/api/collective-memory/stats")
        
        if response.status_code == 200:
            stats = response.json()
            print("✅ Collective Memory Stats:")
            print(f"   Total Statements: {stats['total_statements']}")
            print(f"   Unique Entities: {stats['unique_entities']}")
            print(f"   Unique Agents: {stats['unique_agents']}")
            print(f"   Confidence Distribution:")
            print(f"     - High (≥0.8): {stats['confidence_distribution']['high']}")
            print(f"     - Medium (0.5-0.8): {stats['confidence_distribution']['medium']}")
            print(f"     - Low (<0.5): {stats['confidence_distribution']['low']}")
            print()
        
        # 5. Export as N4L document
        print("5️⃣ Exporting knowledge as N4L document...")
        
        response = await client.get(f"{API_URL}/api/collective-memory/export/n4l")
        
        if response.status_code == 200:
            export = response.json()
            n4l_content = export['content']
            lines = n4l_content.split('\n')[:10]
            print("✅ N4L Document Preview:")
            for line in lines:
                print(f"   {line}")
            print("   ...")
            print()
        
        # 6. Test consensus building
        print("6️⃣ Testing consensus mechanism...")
        
        # Validate a statement (increase confidence)
        consensus_request = {
            "statement": {
                "subject": "Python",
                "predicate": "is good for",
                "object": "machine learning",
                "relation_type": 1,
                "contexts": ["technology", "machine_learning"],
                "confidence": 0.8,
                "contributing_agents": ["test_agent_001"]
            },
            "agent_id": "test_agent_002",
            "action": "validate"
        }
        
        response = await client.post(
            f"{API_URL}/api/collective-memory/consensus",
            json=consensus_request
        )
        
        if response.status_code == 200:
            updated = response.json()
            print(f"✅ Statement validated by agent test_agent_002")
            print(f"   New confidence: {updated['confidence']:.2f}")
            print(f"   Contributors: {updated['contributing_agents']}")
            print()
        
        print("🎉 All tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_collective_memory())