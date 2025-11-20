import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import psutil
import os
from ..database.connection import get_session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["health"],
    responses={404: {"description": "Not found"}},
)

@router.get("")
async def health_check(session: Session = Depends(get_session)):
    """Check system health status"""
    try:
        session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "db_status": db_status,
        "system": {
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent_used": memory.percent
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent_used": disk.percent
            },
            "cpu_percent": psutil.cpu_percent(interval=0.1)
        },
        "environment": os.environ.get("ENV", "development")
    }

@router.get("/docker-health")
async def docker_healthcheck():
    """Simple endpoint for Docker healthcheck"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
