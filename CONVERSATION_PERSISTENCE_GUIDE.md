# Conversation Persistence Guide

## Overview

The conversation persistence feature allows agents to maintain chat history across multiple interactions. This enables more natural, context-aware conversations and improves the user experience.

## Key Features

- **Automatic Conversation Management**: Conversations are automatically created and maintained
- **User-Specific Conversations**: Support for tracking conversations per user
- **Conversation History**: Full message history with metadata and tool calls
- **Flexible Integration**: Works seamlessly with existing agent execution
- **Memory System Integration**: Complements the existing agent memory system

## How It Works

### 1. Automatic Conversation Creation

When executing an agent without specifying a conversation ID:
```json
POST /agents/{agent_id}/execute
{
  "input": "Hello, agent!",
  "save_conversation": true  // Default: true
}
```

The system will:
- Check for an existing active conversation for the agent
- Create a new conversation if none exists
- Return the conversation ID in the response

### 2. Continuing Conversations

To continue an existing conversation:
```json
POST /agents/{agent_id}/execute
{
  "input": "Follow-up question",
  "conversation_id": "existing-conversation-id"
}
```

The system will:
- Load the full conversation history
- Include it as context for the agent
- Append new messages to the conversation

### 3. User-Specific Conversations

For multi-user scenarios, use the get-or-create endpoint:
```json
POST /conversations/agent/{agent_id}/get-or-create?user_id=user-123
```

This ensures each user has their own conversation thread.

## Integration with Existing Features

### Agent Memory System
- **Conversations**: Store the actual message exchange
- **Memory**: Stores extracted knowledge, preferences, and long-term information
- Both systems work together to provide comprehensive context

### Meta-Chat System
The meta-chat system automatically uses conversation persistence when routing requests to agents.

### Feedback System
Feedback can be linked to specific conversation messages for better tracking.

## Best Practices

### 1. Conversation Lifecycle
- Conversations are created automatically on first interaction
- Mark conversations as inactive when completed
- Delete old conversations periodically to manage storage

### 2. Title Management
- Titles are auto-generated from the first user message
- Update titles for better organization:
```json
PUT /conversations/{conversation_id}
{
  "title": "Customer Support - Order #12345"
}
```

### 3. Metadata Usage
Store useful context in metadata:
```json
{
  "metadata": {
    "source": "web_chat",
    "session_id": "abc123",
    "user_agent": "Mozilla/5.0..."
  }
}
```

### 4. Error Handling
- Errors are saved to conversations with the `error` field
- Failed executions still maintain conversation continuity
- Check the `success` field in responses

## API Examples

### Basic Chat Flow
```python
# 1. Start conversation
response = requests.post(f"{BASE_URL}/agents/{agent_id}/execute", json={
    "input": "What's the weather like?"
})
conversation_id = response.json()["conversation_id"]

# 2. Continue conversation
response = requests.post(f"{BASE_URL}/agents/{agent_id}/execute", json={
    "input": "How about tomorrow?",
    "conversation_id": conversation_id
})

# 3. View conversation history
response = requests.get(f"{BASE_URL}/conversations/{conversation_id}")
messages = response.json()["messages"]
```

### Managing Conversations
```python
# List all conversations for an agent
response = requests.get(f"{BASE_URL}/conversations/agent/{agent_id}")

# Get latest conversation
response = requests.get(f"{BASE_URL}/conversations/agent/{agent_id}/latest")

# Update conversation title
response = requests.put(f"{BASE_URL}/conversations/{conversation_id}", json={
    "title": "Weather Discussion - Paris"
})

# Delete old conversation
response = requests.delete(f"{BASE_URL}/conversations/{conversation_id}")
```

## Migration Guide

### For Existing Applications

1. **No Breaking Changes**: The feature is backward compatible
2. **Opt-out Option**: Set `save_conversation: false` to disable
3. **Conversation History**: Still supported via `conversation_history` parameter

### Upgrading Your Code

Before:
```python
# Manual conversation tracking
messages = []
messages.append({"role": "user", "content": "Hello"})
response = agent_execute(input="Hello", conversation_history=messages)
messages.append({"role": "assistant", "content": response["output"]})
```

After:
```python
# Automatic conversation tracking
response = agent_execute(input="Hello")
conversation_id = response["conversation_id"]
# Continue with same conversation
response = agent_execute(input="Follow-up", conversation_id=conversation_id)
```

## Performance Considerations

- Conversations are stored in MongoDB with efficient indexing
- Message history is loaded on-demand
- Large conversations (>100 messages) may impact response time
- Consider creating new conversations for very long interactions

## Security Considerations

- Implement user authentication before production use
- Conversations may contain sensitive information
- Use the `user_id` field to isolate conversations
- Regular cleanup of old conversations is recommended

## Troubleshooting

### Common Issues

1. **Conversation Not Found**
   - The conversation may have been deleted
   - Check the conversation ID is correct
   - System creates a new conversation automatically

2. **Messages Not Saving**
   - Verify `save_conversation` is not set to `false`
   - Check agent execution is successful
   - Review error logs for database issues

3. **Wrong Conversation Loaded**
   - Ensure you're using the correct conversation ID
   - Check user_id filtering if using multi-user setup
   - Verify the agent_id matches

### Debug Tips

1. Check conversation details:
```bash
curl http://localhost:8000/conversations/{conversation_id}
```

2. View agent's all conversations:
```bash
curl http://localhost:8000/conversations/agent/{agent_id}
```

3. Monitor conversation creation in logs:
```bash
docker-compose logs api | grep "conversation"
```

## Future Enhancements

Planned improvements:
- Conversation branching for exploring different paths
- Conversation templates for common scenarios
- Export/import functionality
- Advanced search within conversations
- Conversation analytics and insights