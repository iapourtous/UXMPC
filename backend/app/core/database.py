from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from typing import Optional
import logging

settings = get_settings()
logger = logging.getLogger(__name__)


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    database = None


db = MongoDB()


async def connect_to_mongo():
    # Configure connection pool for better performance
    db.client = AsyncIOMotorClient(
        settings.mongodb_url,
        maxPoolSize=50,  # Maximum number of connections in the pool
        minPoolSize=10,  # Minimum number of connections to maintain
        maxIdleTimeMS=30000,  # Close idle connections after 30 seconds
        waitQueueTimeoutMS=5000,  # Timeout for waiting for a connection
        serverSelectionTimeoutMS=3000,  # Timeout for selecting a server
        connectTimeoutMS=5000,  # Connection timeout
        socketTimeoutMS=30000  # Socket timeout for operations
    )
    db.database = db.client[settings.database_name]
    
    # Create indexes with background=True to avoid blocking
    logger.info("Creating database indexes in background...")
    
    # Service indexes
    await db.database.services.create_index("name", unique=True, background=True)
    await db.database.services.create_index("route", unique=True, background=True)
    await db.database.services.create_index("active", background=True)
    
    # LLM indexes
    await db.database.llms.create_index("name", unique=True, background=True)
    await db.database.llms.create_index("active", background=True)
    
    # Agent indexes
    await db.database.agents.create_index("name", unique=True, background=True)
    await db.database.agents.create_index("endpoint", unique=True, background=True)
    await db.database.agents.create_index("active", background=True)
    
    # Document indexes
    await db.database.documents.create_index("workspace_id", background=True)
    await db.database.documents.create_index("type", background=True)
    await db.database.documents.create_index("category", background=True)
    await db.database.documents.create_index("tags", background=True)
    await db.database.documents.create_index("created_at", background=True)
    await db.database.documents.create_index(
        [("name", "text"), ("description", "text"), ("content", "text")],
        background=True
    )
    
    # Workspace indexes
    await db.database.workspaces.create_index("name", unique=True, background=True)
    await db.database.workspaces.create_index("owner_id", background=True)
    await db.database.workspaces.create_index("agent_ids", background=True)
    await db.database.workspaces.create_index("is_public", background=True)
    
    # Logs indexes for faster queries
    await db.database.logs.create_index("timestamp", background=True)
    await db.database.logs.create_index("level", background=True)
    await db.database.logs.create_index("logger", background=True)
    await db.database.logs.create_index([("timestamp", -1), ("level", 1)], background=True)
    
    # Conversation indexes for better performance
    await db.database.conversations.create_index("created_at", background=True)
    await db.database.conversations.create_index("execution_id", background=True)
    await db.database.conversations.create_index([("created_at", -1)], background=True)
    
    logger.info("Database indexes created successfully")


async def close_mongo_connection():
    if db.client:
        db.client.close()


def get_database():
    return db.database