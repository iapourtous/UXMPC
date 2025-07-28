from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.core.database import get_database
from app.models.conversation import (
    ConversationCreate, ConversationUpdate, ConversationInDB, 
    Conversation, ConversationList, ConversationSummary,
    MessageCreate, MessageBase
)
import logging

logger = logging.getLogger(__name__)


class ConversationCRUD:
    def __init__(self):
        self._db = None
        self._collection = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_database()
        return self._db
    
    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.db.conversations
        return self._collection

    async def create(self, conversation: ConversationCreate) -> Conversation:
        """Create a new conversation"""
        try:
            # Create conversation document
            conversation_dict = conversation.dict()
            conversation_dict["created_at"] = datetime.utcnow()
            conversation_dict["updated_at"] = datetime.utcnow()
            
            # Generate title if not provided
            if not conversation_dict.get("title"):
                conversation_dict["title"] = f"Conversation - {conversation_dict['created_at'].strftime('%Y-%m-%d %H:%M')}"
            
            # Insert into database
            result = await self.collection.insert_one(conversation_dict)
            
            # Retrieve and return the created conversation
            created = await self.collection.find_one({"_id": result.inserted_id})
            # Convert ObjectId to string
            if created and "_id" in created:
                created["_id"] = str(created["_id"])
            db_conversation = ConversationInDB(**created)
            return Conversation.from_db(db_conversation)
            
        except Exception as e:
            logger.error(f"Failed to create conversation: {str(e)}")
            raise

    async def get(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID"""
        try:
            conversation = await self.collection.find_one({"_id": ObjectId(conversation_id)})
            if conversation:
                # Convert ObjectId to string
                conversation["_id"] = str(conversation["_id"])
                db_conversation = ConversationInDB(**conversation)
                return Conversation.from_db(db_conversation)
            return None
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {str(e)}")
            return None

    async def get_latest_conversation(self, user_id: Optional[str] = None) -> Optional[Conversation]:
        """Get the most recent conversation"""
        try:
            filter_dict = {"active": True}
            if user_id:
                filter_dict["user_id"] = user_id
            
            conversation = await self.collection.find_one(
                filter_dict,
                sort=[("last_activity", -1)]
            )
            
            if conversation:
                # Convert ObjectId to string
                conversation["_id"] = str(conversation["_id"])
                db_conversation = ConversationInDB(**conversation)
                return Conversation.from_db(db_conversation)
            
            return None
        except Exception as e:
            logger.error(f"Failed to get latest conversation: {str(e)}")
            return None

    async def list(
        self, 
        skip: int = 0, 
        limit: int = 10,
        active_only: bool = False,
        user_id: Optional[str] = None
    ) -> ConversationList:
        """List conversations with pagination"""
        try:
            # Build filter
            filter_dict = {}
            if active_only:
                filter_dict["active"] = True
            if user_id:
                filter_dict["user_id"] = user_id
            
            # Count total
            total = await self.collection.count_documents(filter_dict)
            
            # Get paginated results
            cursor = self.collection.find(filter_dict).sort(
                "last_activity", -1
            ).skip(skip).limit(limit)
            
            conversations = []
            async for doc in cursor:
                # Convert ObjectId to string
                doc["_id"] = str(doc["_id"])
                db_conversation = ConversationInDB(**doc)
                conversations.append(Conversation.from_db(db_conversation))
            
            total_pages = (total + limit - 1) // limit if limit > 0 else 1
            
            return ConversationList(
                items=conversations,
                total=total,
                page=(skip // limit) + 1 if limit > 0 else 1,
                page_size=limit,
                total_pages=total_pages
            )
        except Exception as e:
            logger.error(f"Failed to list conversations: {str(e)}")
            raise

    async def update(self, conversation_id: str, update: ConversationUpdate) -> Optional[Conversation]:
        """Update a conversation"""
        try:
            update_dict = update.dict(exclude_unset=True)
            if update_dict:
                update_dict["updated_at"] = datetime.utcnow()
                
                result = await self.collection.update_one(
                    {"_id": ObjectId(conversation_id)},
                    {"$set": update_dict}
                )
                
                if result.modified_count > 0:
                    return await self.get(conversation_id)
            
            return await self.get(conversation_id)
        except Exception as e:
            logger.error(f"Failed to update conversation {conversation_id}: {str(e)}")
            return None

    async def add_message(self, conversation_id: str, message: MessageCreate) -> Optional[Conversation]:
        """Add a message to a conversation"""
        try:
            # Create message with timestamp
            message_dict = message.dict()
            message_dict["timestamp"] = datetime.utcnow()
            
            # Prepare update operations
            update_ops = {
                "$push": {"messages": message_dict},
                "$set": {
                    "last_activity": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
            
            # If this is an assistant message with an agent_id, add to agents_used
            if message.role == "assistant" and message.agent_id:
                update_ops["$addToSet"] = {"agents_used": message.agent_id}
            
            # Update conversation
            result = await self.collection.update_one(
                {"_id": ObjectId(conversation_id)},
                update_ops
            )
            
            if result.modified_count > 0:
                return await self.get(conversation_id)
            
            return None
        except Exception as e:
            logger.error(f"Failed to add message to conversation {conversation_id}: {str(e)}")
            return None

    async def delete(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        try:
            result = await self.collection.delete_one({"_id": ObjectId(conversation_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {str(e)}")
            return False


    async def get_summaries(
        self,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[ConversationSummary]:
        """Get conversation summaries for quick display"""
        try:
            filter_dict = {}
            if user_id:
                filter_dict["user_id"] = user_id
            
            # Project only needed fields for performance
            cursor = self.collection.find(
                filter_dict,
                {
                    "_id": 1,
                    "title": 1,
                    "last_activity": 1,
                    "created_at": 1,
                    "active": 1,
                    "agents_used": 1,
                    "messages": {"$size": "$messages"}
                }
            ).sort("last_activity", -1).limit(limit)
            
            summaries = []
            async for doc in cursor:
                summary = ConversationSummary(
                    _id=str(doc["_id"]),
                    title=doc.get("title"),
                    message_count=doc.get("messages", 0),
                    last_activity=doc["last_activity"],
                    created_at=doc["created_at"],
                    active=doc.get("active", True),
                    agents_used=doc.get("agents_used", [])
                )
                summaries.append(summary)
            
            return summaries
        except Exception as e:
            logger.error(f"Failed to get conversation summaries: {str(e)}")
            return []

    async def clear_messages(self, conversation_id: str) -> bool:
        """Clear all messages from a conversation"""
        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {
                    "$set": {
                        "messages": [],
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to clear messages for conversation {conversation_id}: {str(e)}")
            return False


# Create singleton instance
conversation_crud = ConversationCRUD()