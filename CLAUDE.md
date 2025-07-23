# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UXMCP is a dynamic MCP (Model Context Protocol) service manager that allows creating, storing, and activating services on the fly through a web interface. It features intelligent agents, automated service creation, and an advanced chat interface with automatic routing to appropriate agents.

## Architecture

The project consists of four main components running in Docker:
- **Backend (port 8000)**: FastAPI server with MongoDB integration, FastMCP, and intelligent agent system
- **Frontend (port 5173)**: React SPA with Vite for managing services, agents, and interactive demos
- **MongoDB (port 27018)**: Persistent storage for services, agents, LLM profiles, and logs
- **ChromaDB (embedded)**: Vector database for agent memory and semantic search capabilities

## Key Commands

```bash
# Development
make up          # Start all services
make down        # Stop all services
make logs        # Follow logs
make status      # Check service status
make shell-api   # Shell into API container
make shell-mongo # MongoDB shell

# Testing
make test        # Run all tests
docker-compose exec api pytest tests/unit/test_models.py  # Run specific test

# Build & Deploy
make build       # Build Docker images
make clean       # Clean volumes and prune

# Import examples
make import-examples  # Import example MCP services
```

## Development Workflow

### Backend Development
The backend uses FastAPI with hot-reload enabled. Changes to Python files are automatically reflected:
1. Core business logic: `backend/app/core/`
2. API endpoints: `backend/app/api/`
3. Data models: `backend/app/models/`
4. CRUD operations: `backend/app/services/`

### Frontend Development
React app with Vite dev server and hot-reload:
1. Components: `frontend/src/components/`
2. API hooks: `frontend/src/hooks/`
3. API client: `frontend/src/services/api.js`

### Adding New Features
1. Update Pydantic models in `backend/app/models/`
2. Extend CRUD operations in `backend/app/services/`
3. Add/modify API endpoints in `backend/app/api/`
4. Update React components and hooks
5. Run tests to ensure nothing breaks

## Core Components

### Dynamic Service System
Services are created with Python code and can be:
- **Tools**: Functions callable by LLMs (`@mcp.tool`)
- **Resources**: Data providers (`@mcp.resource`)
- **Prompts**: Template generators (`@mcp.prompt`)

Services are stored in MongoDB and dynamically mounted/unmounted at runtime without restart.

### MCP Integration
The `MCPManager` class (`backend/app/core/mcp_manager.py`) handles:
- Registering services as MCP tools/resources/prompts
- Dynamic execution of user-defined Python code
- Integration with LLM profiles for AI-powered services

### Dynamic Routing
The `dynamic_router.py` module manages:
- Runtime addition/removal of FastAPI routes
- Service activation/deactivation
- HTTP endpoint creation for each service

### Intelligent Agent System
The project includes an advanced agent system with:
- **7D Configuration**: Backstory, Objectives, Constraints, Memory, Reasoning, Personality, Decision Policies
- **Memory System**: Persistent memory with ChromaDB for semantic search and context retention
- **Tool Integration**: Agents can use any activated MCP service as a tool
- **Automatic Execution**: Agents process requests and use tools autonomously

### Meta-Agent
The `MetaAgentService` (`backend/app/services/meta_agent_service.py`) provides:
- Automatic agent creation based on natural language requirements
- Intelligent tool matching and creation
- Progress tracking via Server-Sent Events (SSE)
- Capability analysis and gap filling

### Meta-Chat
The `MetaChatService` (`backend/app/services/meta_chat_service.py`) offers:
- Intelligent request routing to appropriate agents
- Automatic agent creation when needed
- HTML/CSS/JS response generation with validation
- Manual and automatic execution modes
- Request enhancement for better results

### AI Agent
The autonomous service creator (`backend/app/services/agent_service.py`):
- Creates services from natural language descriptions
- Iteratively tests and fixes code until working
- Supports external API integration
- Provides real-time progress updates via SSE

### Additional Systems
- **Feedback System**: Collect and analyze user feedback with ratings and statistics
- **Demos System**: Host and manage interactive HTML/CSS/JS demonstrations
- **Logging System**: Comprehensive MongoDB-based logging with execution tracking

## Testing

```bash
# Run all tests
docker-compose exec api pytest

# Run with coverage
docker-compose exec api pytest --cov=app

# Run specific test file
docker-compose exec api pytest tests/unit/test_models.py -v

# Run integration tests only
docker-compose exec api pytest tests/integration/ -v
```

## API Documentation

For a complete and up-to-date reference of all API endpoints, including request/response schemas and examples, see `API_DOCUMENTATION.md` in the root directory. This file contains:
- All endpoints organized by category
- Request/response examples
- Authentication requirements
- Error codes and handling
- WebSocket/SSE endpoints

## Common Development Tasks

### Creating a New Service Type
1. Extend `ServiceBase` model in `models/service.py`
2. Update `register_service()` in `mcp_manager.py`
3. Add UI support in `ServiceForm.jsx`
4. Update service list display in `ServiceList.jsx`

### Adding New API Endpoints
1. Create router in `backend/app/api/`
2. Include router in `main.py`
3. Add corresponding CRUD operations
4. Create React hooks for the new endpoints
5. Update `API_DOCUMENTATION.md` with the new endpoints

### Working with Agents and Meta-Chat

#### Creating an Agent via UI
1. Navigate to the Agents section
2. Configure the 7D parameters (backstory, objectives, etc.)
3. Select MCP services as tools
4. Test the agent before activation

#### Using Meta-Chat
1. Go to Meta-Chat interface
2. Type your request naturally
3. System will automatically:
   - Find or create appropriate agent
   - Execute the request
   - Generate interactive HTML response

#### Creating Services with AI Agent
1. Go to Agent Service Creator
2. Describe what you want in natural language
3. The AI will iteratively:
   - Generate code
   - Test it
   - Fix any errors
   - Activate when working

### Debugging
- API logs: `docker-compose logs api -f`
- Frontend logs: Browser console + `docker-compose logs frontend -f`
- MongoDB queries: `make shell-mongo` then use `mongosh uxmcp`
- Test specific endpoints: Use curl or the included examples
- View all error logs: `http://localhost:8000/logs/app?level=ERROR`
- Agent execution logs: Check agent-specific logs in UI

## Service Code Requirements

When users create services, their Python code must:
- Define a `handler(**params)` function
- Return JSON-serializable data
- Handle exceptions gracefully
- Use only declared dependencies

Example service patterns are in `/examples/` directory.

## Environment Variables

Key environment variables:
- `MONGODB_URL`: MongoDB connection string (default: mongodb://localhost:27017)
- `DATABASE_NAME`: Database name (default: uxmcp)
- `MCP_SERVER_URL`: MCP server endpoint (default: http://localhost:8000/mcp)
- `LOG_LEVEL`: Logging level (default: INFO)
- `VITE_API_URL`: Frontend API URL (default: http://localhost:8000)

ChromaDB is automatically configured and uses Docker volume for persistence.

## Key Files to Know

- `API_DOCUMENTATION.md`: Complete API reference with all endpoints
- `metaChatFlow.md`: Detailed Meta-Chat system flow documentation
- `backend/app/prompts/`: LLM prompt templates used by the system
- `examples/`: Example services demonstrating patterns

## Example Usage Scenarios

### 1. Quick Information Query
```
User: "What's the weather in Paris and the latest news?"
Meta-Chat: Automatically finds or creates an agent with weather and news capabilities
Result: Interactive HTML dashboard with weather data and news articles
```

### 2. Service Creation
```
User: "Create a service that converts markdown to HTML"
AI Agent: Generates code, tests it, fixes errors, and activates the service
Result: New endpoint /api/markdown-to-html ready to use
```

### 3. Complex Agent Creation
```
Meta-Agent: "I need a customer support agent that can process refunds"
System: Analyzes requirements, creates necessary tools, configures agent
Result: Fully functional agent with refund processing capabilities
```

## Important Notes

- The system runs entirely locally and requires Docker
- LLM profiles must be configured before using AI features
- All services run in a sandboxed environment
- Agent memory persists across sessions
- SSE endpoints provide real-time updates for long-running operations