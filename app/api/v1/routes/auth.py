from fastapi import APIRouter, Depends, Request, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas import auth as schemas
from app.api.v1.controllers import auth_controller
from app.models import user as models
from app.core import security
from app.services import auth_service
from datetime import datetime

router = APIRouter()

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: schemas.RegisterRequest, req: Request, db: Session = Depends(get_db)):
    return auth_controller.register_user(request, db, req.client.host)

@router.post("/login")
def login(request: schemas.LoginRequest, req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return auth_controller.login_user(request, db, background_tasks, req.client.host)

@router.post("/verify-otp")
def verify_otp(request: schemas.VerifyOTP, req: Request, db: Session = Depends(get_db)):
    otp_record = db.query(models.OTPCode).filter(
        models.OTPCode.user_id == request.user_id,
        models.OTPCode.otp_code == request.otp_code,
        models.OTPCode.type == models.OTPType.login,
        models.OTPCode.verified == False,
        models.OTPCode.expires_at > datetime.utcnow()
    ).order_by(models.OTPCode.created_at.desc()).first()

    if not otp_record:
        return {"success": False, "message": "Invalid/Expired OTP"}

    otp_record.verified = True
    db.commit()

    token = security.create_access_token(data={"sub": str(request.user_id)})
    auth_service.log_activity(db, "LOGIN_SUCCESS", "Verified", request.user_id, None, req.client.host)

    return {"success": True, "message": "Login successful", "token": token, "redirect": "/dashboard"}