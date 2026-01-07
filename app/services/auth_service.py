from sqlalchemy.orm import Session
from app.models.user import ActivityLog

def log_activity(db: Session, action: str, details: str = None, user_id: int = None, target_id: int = None, ip: str = "Unknown"):
    try:
        new_log = ActivityLog(
            user_id=user_id,
            target_user_id=target_id,
            action=action,
            details=details,
            ip_address=ip
        )
        db.add(new_log)
        db.commit()
    except Exception:
        pass