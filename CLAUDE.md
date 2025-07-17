# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

UXMCP is a dynamic MCP (Model Context Protocol) service manager that allows creating, storing, and activating services on the fly through a web interface. Services can be Tools (actions), Resources (data), or Prompts (templates) that are exposed via FastMCP 2.0. It also includes an integrated chat interface for interacting with LLMs.

## Architecture

The project consists of three main components running in Docker:
- **Backend (port 8000)**: FastAPI server with MongoDB integration and FastMCP
- **Frontend (port 5173)**: React SPA with Vite for managing services
- **MongoDB (port 27018)**: Persistent storage for services and LLM profiles

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

### Debugging
- API logs: `docker-compose logs api -f`
- Frontend logs: Browser console + `docker-compose logs frontend -f`
- MongoDB queries: `make shell-mongo` then use `mongosh uxmcp`
- Test specific endpoints: Use curl or the included examples

## Service Code Requirements

When users create services, their Python code must:
- Define a `handler(**params)` function
- Return JSON-serializable data
- Handle exceptions gracefully
- Use only declared dependencies

Example service patterns are in `/examples/` directory.

## Environment Variables

Key environment variables (see `.env.example`):
- `MONGODB_URL`: MongoDB connection string
- `DATABASE_NAME`: Database name (default: uxmcp)
- `MCP_SERVER_URL`: MCP server endpoint
- `LOG_LEVEL`: Logging level (default: INFO)