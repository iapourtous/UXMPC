#!/usr/bin/env python3
"""
Test script for conversation persistence feature

This script tests the new conversation persistence functionality
by creating conversations, adding messages, and verifying storage.
"""

import asyncio
import httpx
import json
from datetime import datetime


BASE_URL = "http://localhost:8000"


async def test_conversation_crud():
    """Test basic CRUD operations for conversations"""
    async with httpx.AsyncClient() as client:
        print("\n=== Testing Conversation CRUD ===")
        
        # 1. Create a test conversation
        print("\n1. Creating a new conversation...")
        create_data = {
            "agent_id": "test-agent-123",
            "user_id": "test-user",
            "title": "Test Conversation",
            "metadata": {"test": True}
        }
        
        try:
            response = await client.post(f"{BASE_URL}/conversations/", json=create_data)
            if response.status_code == 404:
                print("   Error: Agent not found (expected for test agent)")
            else:
                print(f"   Response: {response.status_code}")
                if response.status_code == 200:
                    conversation = response.json()
                    print(f"   Created conversation ID: {conversation['id']}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # 2. List conversations
        print("\n2. Listing conversations...")
        try:
            response = await client.get(f"{BASE_URL}/conversations/")
            print(f"   Response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Total conversations: {data['total']}")
                print(f"   Page: {data['page']}/{data['pages']}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # 3. Test agent-specific endpoints
        print("\n3. Testing agent-specific endpoints...")
        try:
            response = await client.get(f"{BASE_URL}/conversations/agent/test-agent-123")
            print(f"   Response: {response.status_code}")
        except Exception as e:
            print(f"   Error: {e}")


async def test_agent_integration():
    """Test conversation persistence with actual agent execution"""
    async with httpx.AsyncClient() as client:
        print("\n=== Testing Agent Integration ===")
        
        # First, get a list of active agents
        print("\n1. Getting list of active agents...")
        try:
            response = await client.get(f"{BASE_URL}/agents/?active_only=true")
            if response.status_code == 200:
                agents = response.json()
                print(f"   Found {len(agents)} active agents")
                
                if agents:
                    # Use the first active agent
                    agent = agents[0]
                    print(f"   Using agent: {agent['name']} (ID: {agent['id']})")
                    
                    # Test execution with conversation persistence
                    print("\n2. Testing agent execution with conversation persistence...")
                    execution_data = {
                        "input": "Hello, this is a test message for conversation persistence.",
                        "save_conversation": True
                    }
                    
                    response = await client.post(
                        f"{BASE_URL}/agents/{agent['id']}/execute",
                        json=execution_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"   Execution successful: {result['success']}")
                        if result.get('conversation_id'):
                            print(f"   Conversation ID: {result['conversation_id']}")
                            
                            # Get the conversation
                            conv_response = await client.get(
                                f"{BASE_URL}/conversations/{result['conversation_id']}"
                            )
                            if conv_response.status_code == 200:
                                conversation = conv_response.json()
                                print(f"   Messages in conversation: {conversation['message_count']}")
                                print(f"   Last user message: {conversation.get('last_user_message', 'N/A')[:50]}...")
                        else:
                            print("   No conversation ID returned")
                    else:
                        print(f"   Execution failed: {response.status_code}")
                        print(f"   Error: {response.text}")
                else:
                    print("   No active agents found. Please activate an agent first.")
                    
        except Exception as e:
            print(f"   Error: {e}")


async def test_conversation_continuation():
    """Test continuing an existing conversation"""
    async with httpx.AsyncClient() as client:
        print("\n=== Testing Conversation Continuation ===")
        
        # Get the latest conversation for any agent
        print("\n1. Getting conversations...")
        try:
            response = await client.get(f"{BASE_URL}/conversations/?per_page=1")
            if response.status_code == 200:
                data = response.json()
                if data['conversations']:
                    conversation = data['conversations'][0]
                    print(f"   Found conversation: {conversation['id']}")
                    print(f"   Agent: {conversation['agent_id']}")
                    print(f"   Messages: {conversation['message_count']}")
                    
                    # Continue the conversation
                    print("\n2. Continuing the conversation...")
                    execution_data = {
                        "input": "This is a follow-up message in the same conversation.",
                        "conversation_id": conversation['id'],
                        "save_conversation": True
                    }
                    
                    response = await client.post(
                        f"{BASE_URL}/agents/{conversation['agent_id']}/execute",
                        json=execution_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        print(f"   Execution successful: {result['success']}")
                        print(f"   Same conversation ID: {result.get('conversation_id') == conversation['id']}")
                    else:
                        print(f"   Execution failed: {response.status_code}")
                else:
                    print("   No conversations found")
        except Exception as e:
            print(f"   Error: {e}")


async def main():
    """Run all tests"""
    print("Testing Conversation Persistence Feature")
    print("=" * 50)
    
    await test_conversation_crud()
    await test_agent_integration()
    await test_conversation_continuation()
    
    print("\n" + "=" * 50)
    print("Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())