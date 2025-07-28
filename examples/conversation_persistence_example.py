"""
Example: Using Conversation Persistence with Agents

This example demonstrates how to use the conversation persistence feature
to maintain chat history across multiple agent interactions.
"""

import asyncio
import httpx
import json
from typing import Optional, List, Dict, Any


class ConversationClient:
    """Client for managing agent conversations with persistence"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def create_conversation(
        self, 
        agent_id: str, 
        user_id: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new conversation"""
        data = {
            "agent_id": agent_id,
            "user_id": user_id,
            "title": title
        }
        response = await self.client.post(f"{self.base_url}/conversations/", json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_or_create_conversation(
        self, 
        agent_id: str, 
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get existing conversation or create new one"""
        response = await self.client.post(
            f"{self.base_url}/conversations/agent/{agent_id}/get-or-create",
            params={"user_id": user_id} if user_id else {}
        )
        response.raise_for_status()
        return response.json()
    
    async def chat_with_agent(
        self,
        agent_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        save_conversation: bool = True
    ) -> Dict[str, Any]:
        """Send a message to an agent with optional conversation persistence"""
        data = {
            "input": message,
            "conversation_id": conversation_id,
            "save_conversation": save_conversation
        }
        
        response = await self.client.post(
            f"{self.base_url}/agents/{agent_id}/execute",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    async def get_conversation_history(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Get all messages from a conversation"""
        response = await self.client.get(f"{self.base_url}/conversations/{conversation_id}")
        response.raise_for_status()
        conversation = response.json()
        return conversation.get("messages", [])
    
    async def list_agent_conversations(
        self, 
        agent_id: str, 
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all conversations for an agent"""
        params = {"user_id": user_id} if user_id else {}
        response = await self.client.get(
            f"{self.base_url}/conversations/agent/{agent_id}",
            params=params
        )
        response.raise_for_status()
        return response.json()


async def example_basic_conversation():
    """Example: Basic conversation with persistence"""
    print("\n=== Example: Basic Conversation ===")
    
    client = ConversationClient()
    
    try:
        # Assume we have an agent with ID "weather-agent-123"
        agent_id = "weather-agent-123"
        
        # Start a new conversation
        print("\n1. Starting a new conversation...")
        result = await client.chat_with_agent(
            agent_id=agent_id,
            message="What's the weather like in Paris?",
            save_conversation=True
        )
        
        if result["success"]:
            conversation_id = result.get("conversation_id")
            print(f"   Agent response: {result['output']}")
            print(f"   Conversation ID: {conversation_id}")
            
            # Continue the conversation
            print("\n2. Continuing the conversation...")
            result = await client.chat_with_agent(
                agent_id=agent_id,
                message="How about tomorrow?",
                conversation_id=conversation_id
            )
            
            print(f"   Agent response: {result['output']}")
            
            # Get conversation history
            print("\n3. Getting conversation history...")
            history = await client.get_conversation_history(conversation_id)
            print(f"   Total messages: {len(history)}")
            for i, msg in enumerate(history):
                print(f"   [{i+1}] {msg['role']}: {msg['content'][:50]}...")
        
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


async def example_user_specific_conversations():
    """Example: User-specific conversations"""
    print("\n=== Example: User-Specific Conversations ===")
    
    client = ConversationClient()
    
    try:
        agent_id = "support-agent-123"
        user_id = "user-alice"
        
        # Get or create conversation for user
        print(f"\n1. Getting conversation for user {user_id}...")
        conversation = await client.get_or_create_conversation(
            agent_id=agent_id,
            user_id=user_id
        )
        print(f"   Conversation ID: {conversation['id']}")
        print(f"   Message count: {conversation['message_count']}")
        
        # Send message
        print("\n2. Sending message...")
        result = await client.chat_with_agent(
            agent_id=agent_id,
            message="I need help with my account",
            conversation_id=conversation['id']
        )
        print(f"   Agent response: {result['output']}")
        
        # List all conversations for this user
        print(f"\n3. Listing all conversations for {user_id}...")
        conversations = await client.list_agent_conversations(
            agent_id=agent_id,
            user_id=user_id
        )
        print(f"   Found {len(conversations)} conversations")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


async def example_multiple_agents():
    """Example: Conversations with multiple agents"""
    print("\n=== Example: Multiple Agents ===")
    
    client = ConversationClient()
    
    try:
        # Chat with different agents
        agents = [
            ("weather-agent", "What's the weather forecast?"),
            ("news-agent", "What are the latest tech news?"),
            ("math-agent", "What's the square root of 144?")
        ]
        
        conversations = {}
        
        # Start conversations with each agent
        print("\n1. Starting conversations with multiple agents...")
        for agent_id, message in agents:
            try:
                result = await client.chat_with_agent(
                    agent_id=agent_id,
                    message=message
                )
                if result["success"]:
                    conversations[agent_id] = result.get("conversation_id")
                    print(f"   {agent_id}: Conversation started (ID: {conversations[agent_id]})")
            except Exception as e:
                print(f"   {agent_id}: Failed - {e}")
        
        # Continue a conversation
        if "weather-agent" in conversations:
            print("\n2. Continuing weather conversation...")
            result = await client.chat_with_agent(
                agent_id="weather-agent",
                message="Should I bring an umbrella?",
                conversation_id=conversations["weather-agent"]
            )
            if result["success"]:
                print(f"   Response: {result['output']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()


async def main():
    """Run all examples"""
    print("Conversation Persistence Examples")
    print("=" * 50)
    
    # Note: These examples assume you have agents set up in your system
    # You'll need to replace the agent IDs with actual ones from your setup
    
    await example_basic_conversation()
    await example_user_specific_conversations()
    await example_multiple_agents()
    
    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    asyncio.run(main())