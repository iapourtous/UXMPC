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


async def close_mongo_connection():
    if db.client:
        db.client.close()


def get_database():
    return db.database