import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import BackgroundTasks

from app.models import user as models
from app.schemas import auth as schemas
from app.core import security
from app.services import notification_service, auth_service
from app.utils import formatters

def register_user(request: schemas.RegisterRequest, db: Session, client_ip: str):
    if len(request.password.encode('utf-8')) > 72:
        return {"success": False, "message": "Password is too long"}

    existing_user = db.query(models.User).filter(
        models.User.email == request.email,
        models.User.phone == request.phone
    ).first()

    user_id = None

    if existing_user:
        company_count = db.query(models.Company).filter(models.Company.user_id == existing_user.id).count()
        if company_count >= 10:
            return {"success": False, "message": "Maximum limit of 10 companies reached"}
        
        duplicate = db.query(models.Company).filter(
            models.Company.user_id == existing_user.id,
            models.Company.company_name == request.company
        ).first()
        if duplicate:
            return {"success": False, "message": "Company already exists"}
        user_id = existing_user.id
    else:
        # Cross check
        if db.query(models.User).filter(or_(models.User.email == request.email, models.User.phone == request.phone)).first():
            return {"success": False, "message": "Email or phone taken by different account"}

        new_user = models.User(
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
            password_hash=security.get_password_hash(request.password),
            status=models.UserStatus.active
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user_id = new_user.id
        auth_service.log_activity(db, "REGISTER", "New user", user_id, None, client_ip)

    new_company = models.Company(
        user_id=user_id,
        company_name=request.company,
        company_email=request.email,
        company_phone=request.phone
    )
    db.add(new_company)
    db.commit()
    return {"success": True, "message": "Registration successful"}

def login_user(request: schemas.LoginRequest, db: Session, background_tasks: BackgroundTasks, client_ip: str):
    if len(request.password.encode('utf-8')) > 72:
        return {"success": False, "message": "Password too long"}

    user_obj = db.query(models.User).filter(
        or_(models.User.email == request.identifier, models.User.phone == request.identifier)
    ).first()

    if not user_obj or not security.verify_password(request.password, user_obj.password_hash):
        return {"success": False, "message": "Invalid credentials"}

    if user_obj.status != models.UserStatus.active:
        return {"success": False, "message": f"Account {user_obj.status.value}"}

    companies = db.query(models.Company).filter(models.Company.user_id == user_obj.id).all()
    if not companies:
        return {"success": False, "message": "No company found"}

    # Single Company -> Send OTP
    if len(companies) == 1:
        otp_code = str(random.randint(100000, 999999))
        otp_entry = models.OTPCode(
            user_id=user_obj.id,
            identifier=request.identifier,
            otp_code=otp_code,
            type=models.OTPType.login,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.add(otp_entry)
        db.commit()

        background_tasks.add_task(notification_service.send_otp_dispatch, request.identifier, otp_code, user_obj.full_name)
        auth_service.log_activity(db, "LOGIN_ATTEMPT", "OTP sent", user_obj.id, None, client_ip)
        
        return {
            "success": True, "message": "OTP sent", "has_multiple": False,
            "user_id": user_obj.id, "otp_method": "email" if "@" in request.identifier else "sms",
            "masked_identifier": formatters.mask_identifier(request.identifier),
            "company_id": companies[0].id
        }

    return {
        "success": True, "message": "Multiple accounts", "has_multiple": True,
        "user_id": user_obj.id, "companies": [{"id": c.id, "company_name": c.company_name} for c in companies]
    }