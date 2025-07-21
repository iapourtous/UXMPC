"""
Feedback CRUD operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from app.core.database import get_database
from app.models.feedback import Feedback, FeedbackCreate, FeedbackInDB, FeedbackList

logger = logging.getLogger(__name__)


class FeedbackCRUD:
    """CRUD operations for feedback"""
    
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
            self._collection = self.db.feedbacks
        return self._collection
    
    async def create(self, feedback: FeedbackCreate) -> Feedback:
        """Create a new feedback entry"""
        try:
            feedback_dict = feedback.model_dump()
            feedback_dict["created_at"] = datetime.utcnow()
            
            result = await self.collection.insert_one(feedback_dict)
            feedback_dict["_id"] = result.inserted_id
            feedback_dict["id"] = str(result.inserted_id)
            
            logger.info(f"Created feedback with id: {feedback_dict['id']}")
            return Feedback(**feedback_dict)
            
        except Exception as e:
            logger.error(f"Error creating feedback: {str(e)}")
            raise
    
    async def get(self, feedback_id: str) -> Optional[Feedback]:
        """Get feedback by ID"""
        try:
            if not ObjectId.is_valid(feedback_id):
                return None
                
            feedback = await self.collection.find_one({"_id": ObjectId(feedback_id)})
            if feedback:
                feedback["id"] = str(feedback["_id"])
                return Feedback(**feedback)
            return None
            
        except Exception as e:
            logger.error(f"Error getting feedback {feedback_id}: {str(e)}")
            return None
    
    async def list(
        self, 
        page: int = 1, 
        per_page: int = 20,
        rating: Optional[str] = None,
        agent_used: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> FeedbackList:
        """List feedbacks with pagination and filtering"""
        try:
            # Build filter
            filter_dict = {}
            if rating:
                filter_dict["rating"] = rating
            if agent_used:
                filter_dict["agent_used"] = agent_used
            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = start_date
                if end_date:
                    date_filter["$lte"] = end_date
                filter_dict["created_at"] = date_filter
            
            # Get total count
            total = await self.collection.count_documents(filter_dict)
            
            # Calculate skip
            skip = (page - 1) * per_page
            
            # Get feedbacks
            cursor = self.collection.find(filter_dict).sort("created_at", -1).skip(skip).limit(per_page)
            feedbacks = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                feedbacks.append(Feedback(**doc))
            
            return FeedbackList(
                feedbacks=feedbacks,
                total=total,
                page=page,
                per_page=per_page
            )
            
        except Exception as e:
            logger.error(f"Error listing feedbacks: {str(e)}")
            return FeedbackList(feedbacks=[], total=0, page=page, per_page=per_page)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get feedback statistics"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "positive": {
                            "$sum": {"$cond": [{"$eq": ["$rating", "positive"]}, 1, 0]}
                        },
                        "negative": {
                            "$sum": {"$cond": [{"$eq": ["$rating", "negative"]}, 1, 0]}
                        }
                    }
                }
            ]
            
            result = await self.collection.aggregate(pipeline).to_list(1)
            if result:
                stats = result[0]
                del stats["_id"]
                stats["positive_rate"] = (stats["positive"] / stats["total"] * 100) if stats["total"] > 0 else 0
                return stats
            
            return {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "positive_rate": 0
            }
            
        except Exception as e:
            logger.error(f"Error getting feedback stats: {str(e)}")
            return {
                "total": 0,
                "positive": 0,
                "negative": 0,
                "positive_rate": 0
            }
    
    async def get_agent_stats(self) -> List[Dict[str, Any]]:
        """Get feedback statistics by agent"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$agent_used",
                        "total": {"$sum": 1},
                        "positive": {
                            "$sum": {"$cond": [{"$eq": ["$rating", "positive"]}, 1, 0]}
                        },
                        "negative": {
                            "$sum": {"$cond": [{"$eq": ["$rating", "negative"]}, 1, 0]}
                        }
                    }
                },
                {
                    "$project": {
                        "agent": "$_id",
                        "total": 1,
                        "positive": 1,
                        "negative": 1,
                        "positive_rate": {
                            "$multiply": [
                                {"$divide": ["$positive", "$total"]},
                                100
                            ]
                        }
                    }
                },
                {"$sort": {"total": -1}}
            ]
            
            result = await self.collection.aggregate(pipeline).to_list(None)
            for item in result:
                item["agent"] = item.pop("_id")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting agent feedback stats: {str(e)}")
            return []


# Singleton instance
feedback_crud = FeedbackCRUD()