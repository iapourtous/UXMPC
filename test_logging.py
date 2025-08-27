#!/usr/bin/env python3
"""Test script to verify logging is working correctly"""

import asyncio
import httpx
import json

API_URL = "http://localhost:8000"

async def test_cot_logs():
    """Test that COT logs are being recorded"""
    async with httpx.AsyncClient() as client:
        # Get COT logs
        response = await client.get(f"{API_URL}/logs/cot?limit=10")
        if response.status_code == 200:
            logs = response.json()
            print(f"✅ Found {len(logs)} COT logs")
            if logs:
                print("Latest COT log:")
                latest = logs[0]
                print(f"  - Level: {latest.get('level')}")
                print(f"  - Message: {latest.get('message')}")
                if 'details' in latest and latest['details']:
                    print(f"  - Details: {json.dumps(latest['details'], indent=2)[:200]}...")
        else:
            print(f"❌ Failed to fetch COT logs: {response.status_code}")

async def test_agent_logs():
    """Test that agent logs are being recorded"""
    async with httpx.AsyncClient() as client:
        # First get an agent
        agents_response = await client.get(f"{API_URL}/agents?active_only=true")
        if agents_response.status_code == 200:
            agents = agents_response.json()
            if agents:
                agent_id = agents[0]['id']
                agent_name = agents[0]['name']
                
                # Get agent logs
                response = await client.get(f"{API_URL}/logs/agents/{agent_id}?limit=10")
                if response.status_code == 200:
                    logs = response.json()
                    print(f"✅ Found {len(logs)} logs for agent '{agent_name}'")
                    if logs:
                        print("Latest agent log:")
                        latest = logs[0]
                        print(f"  - Level: {latest.get('level')}")
                        print(f"  - Message: {latest.get('message')}")
                else:
                    print(f"❌ Failed to fetch agent logs: {response.status_code}")
            else:
                print("⚠️ No active agents found")
        else:
            print(f"❌ Failed to fetch agents: {agents_response.status_code}")

async def test_log_creation():
    """Test creating logs through agent execution"""
    async with httpx.AsyncClient() as client:
        # Get an active agent
        agents_response = await client.get(f"{API_URL}/agents?active_only=true")
        if agents_response.status_code == 200:
            agents = agents_response.json()
            if agents:
                # Find an agent with COT reasoning if available
                cot_agent = next((a for a in agents if a.get('reasoning_strategy') == 'chain-of-thought'), None)
                agent = cot_agent or agents[0]
                
                print(f"\n📝 Testing with agent: {agent['name']}")
                print(f"   Reasoning strategy: {agent.get('reasoning_strategy', 'standard')}")
                
                # Execute agent
                execution_data = {
                    "input": "What is 2+2? Think step by step.",
                    "stream": False,
                    "save_conversation": False
                }
                
                response = await client.post(
                    f"{API_URL}/agents/{agent['id']}/execute",
                    json=execution_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Agent execution successful")
                    print(f"   Result: {result.get('output', '')[:100]}...")
                    
                    # Wait a bit for logs to be written
                    await asyncio.sleep(1)
                    
                    # Check for new logs
                    logs_response = await client.get(f"{API_URL}/logs/agents/{agent['id']}?limit=5")
                    if logs_response.status_code == 200:
                        new_logs = logs_response.json()
                        print(f"   Found {len(new_logs)} new log entries")
                else:
                    print(f"❌ Agent execution failed: {response.status_code}")
                    print(f"   Error: {response.text}")
            else:
                print("⚠️ No active agents found for testing")

async def main():
    """Run all tests"""
    print("🧪 Testing Centralized Logging System\n")
    print("=" * 50)
    
    print("\n1. Testing COT logs endpoint...")
    await test_cot_logs()
    
    print("\n2. Testing Agent logs endpoint...")
    await test_agent_logs()
    
    print("\n3. Testing log creation through execution...")
    await test_log_creation()
    
    print("\n" + "=" * 50)
    print("✅ Testing complete!")

if __name__ == "__main__":
    asyncio.run(main())