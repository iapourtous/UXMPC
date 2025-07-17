from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.log import AppLog, ServiceLog, LogQuery, ServiceLogQuery, LogLevel
from app.core.database import get_database
from bson import ObjectId
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/app", response_model=List[AppLog])
async def get_app_logs(
    level: Optional[LogLevel] = None,
    module: Optional[str] = None,
    search: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """Get application logs with filtering"""
    db = get_database()
    collection = db["app_logs"]
    
    # Build query
    query = {}
    if level:
        query["level"] = level
    if module:
        query["module"] = {"$regex": module, "$options": "i"}
    if search:
        query["message"] = {"$regex": search, "$options": "i"}
    
    # Time range filtering
    if start_time or end_time:
        time_query = {}
        if start_time:
            time_query["$gte"] = start_time
        if end_time:
            time_query["$lte"] = end_time
        query["timestamp"] = time_query
    
    # Execute query
    cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    logs = []
    
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        logs.append(AppLog(**doc))
    
    return logs


@router.get("/services/{service_id}", response_model=List[ServiceLog])
async def get_service_logs(
    service_id: str,
    execution_id: Optional[str] = None,
    level: Optional[LogLevel] = None,
    search: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    skip: int = Query(0, ge=0)
):
    """Get logs for a specific service"""
    db = get_database()
    collection = db["service_logs"]
    
    # Build query
    query = {"service_id": service_id}
    
    if execution_id:
        query["execution_id"] = execution_id
    if level:
        query["level"] = level
    if search:
        query["message"] = {"$regex": search, "$options": "i"}
    
    # Time range filtering
    if start_time or end_time:
        time_query = {}
        if start_time:
            time_query["$gte"] = start_time
        if end_time:
            time_query["$lte"] = end_time
        query["timestamp"] = time_query
    
    # Execute query
    cursor = collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    logs = []
    
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        logs.append(ServiceLog(**doc))
    
    return logs


@router.get("/services/{service_id}/latest", response_model=List[ServiceLog])
async def get_latest_service_logs(
    service_id: str,
    limit: int = Query(50, ge=1, le=500)
):
    """Get the latest logs for a service"""
    return await get_service_logs(
        service_id=service_id,
        limit=limit,
        skip=0
    )


@router.get("/execution/{execution_id}", response_model=List[ServiceLog])
async def get_execution_logs(
    execution_id: str,
    level: Optional[LogLevel] = None
):
    """Get all logs for a specific execution"""
    db = get_database()
    collection = db["service_logs"]
    
    query = {"execution_id": execution_id}
    if level:
        query["level"] = level
    
    cursor = collection.find(query).sort("timestamp", 1)  # Chronological order
    logs = []
    
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        logs.append(ServiceLog(**doc))
    
    return logs


@router.delete("/services/{service_id}/old")
async def delete_old_service_logs(
    service_id: str,
    days: int = Query(30, ge=1, le=365)
):
    """Delete service logs older than specified days"""
    db = get_database()
    collection = db["service_logs"]
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = await collection.delete_many({
        "service_id": service_id,
        "timestamp": {"$lt": cutoff_date}
    })
    
    return {
        "deleted_count": result.deleted_count,
        "message": f"Deleted {result.deleted_count} logs older than {days} days"
    }


@router.get("/services/stats/{service_id}")
async def get_service_log_stats(
    service_id: str,
    hours: int = Query(24, ge=1, le=168)  # Default 24 hours, max 1 week
):
    """Get log statistics for a service"""
    db = get_database()
    collection = db["service_logs"]
    
    start_time = datetime.utcnow() - timedelta(hours=hours)
    
    pipeline = [
        {
            "$match": {
                "service_id": service_id,
                "timestamp": {"$gte": start_time}
            }
        },
        {
            "$group": {
                "_id": "$level",
                "count": {"$sum": 1}
            }
        }
    ]
    
    stats = {"total": 0}
    async for doc in collection.aggregate(pipeline):
        level = doc["_id"]
        count = doc["count"]
        stats[level.lower()] = count
        stats["total"] += count
    
    # Get unique executions count
    execution_pipeline = [
        {
            "$match": {
                "service_id": service_id,
                "timestamp": {"$gte": start_time}
            }
        },
        {
            "$group": {
                "_id": "$execution_id"
            }
        },
        {
            "$count": "executions"
        }
    ]
    
    async for doc in collection.aggregate(execution_pipeline):
        stats["executions"] = doc["executions"]
    
    if "executions" not in stats:
        stats["executions"] = 0
    
    stats["time_range"] = {
        "start": start_time,
        "end": datetime.utcnow(),
        "hours": hours
    }
    
    return stats


@router.get("/search", response_model=List[ServiceLog])
async def search_logs(
    query: str = Query(..., description="Search query"),
    service_id: Optional[str] = None,
    level: Optional[LogLevel] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """Search across all service logs"""
    db = get_database()
    collection = db["service_logs"]
    
    # Build search query
    search_query = {
        "$or": [
            {"message": {"$regex": query, "$options": "i"}},
            {"details": {"$regex": query, "$options": "i"}}
        ]
    }
    
    if service_id:
        search_query["service_id"] = service_id
    if level:
        search_query["level"] = level
    
    cursor = collection.find(search_query).sort("timestamp", -1).limit(limit)
    logs = []
    
    async for doc in cursor:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        logs.append(ServiceLog(**doc))
    
    return logs