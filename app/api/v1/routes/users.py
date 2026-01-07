from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas import auth as schemas
from app.models import user as models
from app.services import auth_service

router = APIRouter()

# --- Dashboard Stats ---
@router.get("/dashboard-count")
def get_dashboard_stats(db: Session = Depends(get_db)):
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.status == "active").count()
    limited_users = db.query(models.User).filter(models.User.status == "restricted").count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "limited_users": limited_users
    }

# --- Get All Users ---
@router.get("/", response_model=List[schemas.UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# --- Get User Logs ---
@router.get("/{user_id}/logs")
def get_user_logs(user_id: int, db: Session = Depends(get_db)):
    try:
        logs = db.query(models.ActivityLog)\
                 .filter(models.ActivityLog.user_id == user_id)\
                 .order_by(models.ActivityLog.created_at.desc())\
                 .all()
        return logs
    except AttributeError:
        return []

# --- Update User Status ---
@router.put("/{user_id}/status")
def update_user_status(user_id: int, request: schemas.UserStatusUpdate, req: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_status = user.status
    user.status = request.status
    db.commit()
    
    # Log activity
    auth_service.log_activity(db, "STATUS_UPDATE", f"{old_status}->{request.status}", 1, user_id, req.client.host)
    
    return {"success": True, "message": "Status updated"}