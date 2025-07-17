from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
from app.core.config import get_settings
from app.core.database import connect_to_mongo, close_mongo_connection
from app.core.dynamic_router import mount_all_active_services
from app.core.mcp_manager import mcp_manager
from app.api import services, llms, docs, chat, mcp_debug, logs, agents, agent, agent_memory, meta_agent, meta_chat

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up UXMCP...")
    await connect_to_mongo()
    logger.info("Connected to MongoDB")
    
    # Setup MongoDB logging
    from app.core.database import get_database
    from app.core.mongodb_logger import setup_mongodb_logging
    db = get_database()
    setup_mongodb_logging(db)
    logger.info("MongoDB logging initialized")
    
    # Mount all active services
    await mount_all_active_services(app)
    logger.info("Mounted all active services")
    
    # Mount all active agents
    from app.core.agent_router import mount_all_active_agents
    await mount_all_active_agents(app)
    logger.info("Mounted all active agents")
    
    yield
    
    # Shutdown
    logger.info("Shutting down UXMCP...")
    
    # Cleanup MongoDB logging
    from app.core.mongodb_logger import cleanup_mongodb_logging
    await cleanup_mongodb_logging()
    
    await close_mongo_connection()


# Create FastAPI app
app = FastAPI(
    title="UXMCP - Dynamic MCP Service Manager",
    description="Create, store, and activate MCP services on the fly",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, configure specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(services.router, prefix="/services", tags=["Services"])
app.include_router(llms.router, prefix="/llms", tags=["LLM Profiles"])
app.include_router(docs.router, prefix="/docs", tags=["Documentation"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(mcp_debug.router, prefix="/debug", tags=["MCP Debug"])
app.include_router(logs.router, prefix="/logs", tags=["Logs"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(agent.router, prefix="/agent", tags=["AI Agent"])
app.include_router(agent_memory.router, prefix="/agents", tags=["Agent Memory"])
app.include_router(meta_agent.router, prefix="/meta-agent", tags=["Meta Agent"])
app.include_router(meta_chat.router, prefix="/meta-chat", tags=["Meta Chat"])

# Mount MCP server
mcp_server = mcp_manager.get_mcp_server()
app.mount("/mcp", mcp_server)

# Pass app reference to routers for dynamic routing
services.router.app = app
agents.router.app = app
agent.router.app = app
meta_agent.router.app = app
meta_chat.router.app = app


@app.get("/")
async def root():
    return {
        "message": "UXMCP - Dynamic MCP Service Manager",
        "endpoints": {
            "services": "/services",
            "llm_profiles": "/llms",
            "documentation": "/docs",
            "mcp_server": "/mcp",
            "openapi": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}