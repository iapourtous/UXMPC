"""
Feedback API endpoints
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
import logging

from app.models.feedback import FeedbackCreate, Feedback, FeedbackList
from app.services.feedback_crud import feedback_crud

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=Feedback)
async def create_feedback(feedback: FeedbackCreate):
    """
    Create a new feedback entry
    """
    try:
        created_feedback = await feedback_crud.create(feedback)
        return created_feedback
    except Exception as e:
        logger.error(f"Error creating feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create feedback: {str(e)}")


@router.get("/{feedback_id}", response_model=Feedback)
async def get_feedback(feedback_id: str):
    """
    Get a specific feedback by ID
    """
    feedback = await feedback_crud.get(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return feedback


@router.get("/", response_model=FeedbackList)
async def list_feedbacks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    rating: Optional[str] = Query(None, regex="^(positive|negative)$"),
    agent_used: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """
    List feedbacks with pagination and filtering
    """
    return await feedback_crud.list(
        page=page,
        per_page=per_page,
        rating=rating,
        agent_used=agent_used,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/stats/overview")
async def get_feedback_stats():
    """
    Get overall feedback statistics
    """
    return await feedback_crud.get_stats()


@router.get("/stats/by-agent")
async def get_agent_feedback_stats():
    """
    Get feedback statistics grouped by agent
    """
    return await feedback_crud.get_agent_stats()