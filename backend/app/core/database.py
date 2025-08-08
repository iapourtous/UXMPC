from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
from typing import Optional

settings = get_settings()


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    database = None


db = MongoDB()


async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.mongodb_url)
    db.database = db.client[settings.database_name]
    
    # Create indexes
    await db.database.services.create_index("name", unique=True)
    await db.database.services.create_index("route", unique=True)
    await db.database.services.create_index("active")
    
    await db.database.llms.create_index("name", unique=True)
    await db.database.llms.create_index("active")
    
    await db.database.agents.create_index("name", unique=True)
    await db.database.agents.create_index("endpoint", unique=True)
    await db.database.agents.create_index("active")
    
    # Document indexes
    await db.database.documents.create_index("workspace_id")
    await db.database.documents.create_index("type")
    await db.database.documents.create_index("category")
    await db.database.documents.create_index("tags")
    await db.database.documents.create_index("created_at")
    await db.database.documents.create_index([("name", "text"), ("description", "text"), ("content", "text")])
    
    # Workspace indexes
    await db.database.workspaces.create_index("name", unique=True)
    await db.database.workspaces.create_index("owner_id")
    await db.database.workspaces.create_index("agent_ids")
    await db.database.workspaces.create_index("is_public")


async def close_mongo_connection():
    if db.client:
        db.client.close()


def get_database():
    return db.database