from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_
from datetime import datetime, timedelta
import random
from typing import List


import models, schemas, utils, database


models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Ez Bid Auth Backend")

# ============================================================
# CORS CONFIGURATION
# ============================================================
origins = [
  "https://ezbid.vercel.app",
  "https://ez-bid-client.vercel.app",
  "https://ezbid.pages.dev",
  "https://ezbidgo.pages.dev",
  "https://ezbidgoadmin.pages.dev",
  "https://api.ezbid.cloud",
  "https://ezbid.cloud",
  "https://admin-panel.ezbid.cloud",
  "http://localhost:5174",
  "http://localhost:5173",
  "http://localhost:5000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
get_db = database.get_db

# ============================================================
# HELPER: ACTIVITY LOGGER
# ============================================================
def log_activity(db: Session, action: str, details: str = None, user_id: int = None, target_id: int = None, ip: str = "Unknown"):
    try:
        new_log = models.ActivityLog(
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

# ============================================================
# ROOT ROUTE
# ============================================================
@app.get("/")
def read_root():
    return {"status": "active", "message": "Service is running properly"}

# ============================================================
# 1. REGISTER API
# ============================================================
@app.post("/api/register", status_code=status.HTTP_201_CREATED)
def register(request: schemas.RegisterRequest, req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    
    # [FIX] Bcrypt crash prevention: Password check
    if len(request.password.encode('utf-8')) > 72:
        return {"success": False, "message": "Password is too long (max 72 characters)"}

    
    existing_user = db.query(models.User).filter(
        models.User.email == request.email,
        models.User.phone == request.phone
    ).first()

    user_id = None

    if existing_user:
        
        company_count = db.query(models.Company).filter(models.Company.user_id == existing_user.id).count()
        if company_count >= 10:
            return {"success": False, "message": "Maximum limit of 10 companies per user reached"}

        duplicate_company = db.query(models.Company).filter(
            models.Company.user_id == existing_user.id,
            models.Company.company_name == request.company
        ).first()
        if duplicate_company:
            return {"success": False, "message": "Company already exists for this user"}

        user_id = existing_user.id
    else:
       
        cross_check = db.query(models.User).filter(
            or_(models.User.email == request.email, models.User.phone == request.phone)
        ).first()

        if cross_check:
            return {"success": False, "message": "Email or phone already registered with different account"}

       
        new_user = models.User(
            full_name=request.full_name,
            email=request.email,
            phone=request.phone,
            password_hash=utils.get_password_hash(request.password),
            status=models.UserStatus.active
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user_id = new_user.id
        
        # Log Registration
        log_activity(db, "REGISTER", "New user registration", user_id, None, req.client.host)

    
    new_company = models.Company(
        user_id=user_id,
        company_name=request.company,
        company_email=request.email,
        company_phone=request.phone
    )
    db.add(new_company)
    db.commit()

    return {"success": True, "message": "Registration successful. Please login."}

# ============================================================
# 2. LOGIN API
# ============================================================
@app.post("/api/login")
def login(request: schemas.LoginRequest, req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    
    if len(request.password.encode('utf-8')) > 72:
        return {"success": False, "message": "Password is too long (max 72 characters)"}

    
    user = db.query(models.User).filter(
        or_(models.User.email == request.identifier, models.User.phone == request.identifier)
    ).first()

    if not user or not utils.verify_password(request.password, user.password_hash):
        return {"success": False, "message": "No account found or invalid password"}

    if user.status != models.UserStatus.active:
        log_activity(db, "LOGIN_DENIED", f"Status: {user.status}", user.id, None, req.client.host)
        return {"success": False, "message": f"Your account is {user.status.value}. Please contact support."}

    
    companies = db.query(models.Company).filter(models.Company.user_id == user.id).all()
    if not companies:
        return {"success": False, "message": "No company account found"}

    company_list = [{"id": c.id, "company_name": c.company_name} for c in companies]

    if len(companies) == 1:
        otp_code = str(random.randint(100000, 999999))
        otp_entry = models.OTPCode(
            user_id=user.id,
            identifier=request.identifier,
            otp_code=otp_code,
            type=models.OTPType.login,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.add(otp_entry)
        db.commit()

        # Background Task for sending Email/SMS
        background_tasks.add_task(utils.send_otp, request.identifier, otp_code, user.full_name)
        
        log_activity(db, "LOGIN_ATTEMPT", "OTP sent", user.id, None, req.client.host)

        return {
            "success": True,
            "message": "OTP sent successfully",
            "has_multiple": False,
            "user_id": user.id,
            "otp_method": "email" if "@" in request.identifier else "sms",
            "masked_identifier": utils.mask_identifier(request.identifier),
            "company_id": companies[0].id
        }

    
    return {
        "success": True,
        "message": "Multiple accounts found",
        "has_multiple": True,
        "user_id": user.id,
        "companies": company_list
    }

# ============================================================
# 3. REQUEST OTP API
# ============================================================
@app.post("/api/request-otp")
def request_otp(request: schemas.RequestOTP, req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    company = db.query(models.Company).filter(
        models.Company.id == request.company_id,
        models.Company.user_id == request.user_id
    ).first()

    if not company:
        return {"success": False, "message": "Invalid company selection"}

    user = db.query(models.User).filter(models.User.id == request.user_id).first()

    if user.status != models.UserStatus.active:
        return {"success": False, "message": "Account is restricted"}

    otp_code = str(random.randint(100000, 999999))
    otp_entry = models.OTPCode(
        user_id=request.user_id,
        identifier=request.identifier,
        otp_code=otp_code,
        type=models.OTPType.login,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(otp_entry)
    db.commit()

    background_tasks.add_task(utils.send_otp, request.identifier, otp_code, user.full_name)
    
    log_activity(db, "OTP_RESEND", "OTP requested manually", user.id, None, req.client.host)

    return {
        "success": True,
        "message": "OTP sent successfully",
        "otp_method": "email" if "@" in request.identifier else "sms",
        "masked_identifier": utils.mask_identifier(request.identifier)
    }

# ============================================================
# 4. VERIFY OTP API
# ============================================================
@app.post("/api/verify-otp")
def verify_otp(request: schemas.VerifyOTP, req: Request, db: Session = Depends(get_db)):
    otp_record = db.query(models.OTPCode).filter(
        models.OTPCode.user_id == request.user_id,
        models.OTPCode.otp_code == request.otp_code,
        models.OTPCode.type == models.OTPType.login,
        models.OTPCode.verified == False,
        models.OTPCode.expires_at > datetime.utcnow()
    ).order_by(models.OTPCode.created_at.desc()).first()

    if not otp_record:
        return {"success": False, "message": "Invalid or expired OTP code"}

    otp_record.verified = True
    db.commit()

    access_token = utils.create_access_token(data={"sub": str(request.user_id)})
    
    log_activity(db, "LOGIN_SUCCESS", "User verified OTP", request.user_id, None, req.client.host)

    return {
        "success": True,
        "message": "Login successful",
        "token": access_token,
        "redirect": "/dashboard"
    }

# ============================================================
# 5. FORGOT PASSWORD API
# ============================================================
@app.post("/api/forgot-password")
def forgot_password(request: schemas.ForgotPasswordRequest, req: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    
    # --- STEP 1: Send OTP ---
    if request.step == 1:
        if not request.contact or not request.method:
            return {"success": False, "message": "Contact and method required"}

        field = models.User.email if request.method == 'email' else models.User.phone
        user = db.query(models.User).filter(field == request.contact).first()

        if not user:
            return {"success": False, "message": f"No account found with this {request.method}"}

        otp_code = str(random.randint(100000, 999999))
        otp_entry = models.OTPCode(
            user_id=user.id,
            identifier=request.contact,
            otp_code=otp_code,
            type=models.OTPType.password_reset,
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        db.add(otp_entry)
        db.commit()

        background_tasks.add_task(utils.send_otp, request.contact, otp_code, user.full_name)
        log_activity(db, "PWD_RESET_INIT", "Password reset started", user.id, None, req.client.host)

        return {"success": True, "message": "OTP sent successfully", "masked_contact": utils.mask_identifier(request.contact)}

    # --- STEP 2: Verify OTP ---
    elif request.step == 2:
        if not request.otp_code or not request.contact:
            return {"success": False, "message": "OTP code and contact required"}

        user = db.query(models.User).filter(
            or_(models.User.email == request.contact, models.User.phone == request.contact)
        ).first()

        if not user:
            return {"success": False, "message": "User not found"}

        otp_record = db.query(models.OTPCode).filter(
            models.OTPCode.user_id == user.id,
            models.OTPCode.otp_code == request.otp_code,
            models.OTPCode.type == models.OTPType.password_reset,
            models.OTPCode.verified == False,
            models.OTPCode.expires_at > datetime.utcnow()
        ).first()

        if not otp_record:
            return {"success": False, "message": "Invalid or expired OTP code"}

        otp_record.verified = True
        db.commit()

        return {"success": True, "message": "OTP verified"}

    # --- STEP 3: Get Companies ---
    elif request.step == 3:
        if not request.contact:
            return {"success": False, "message": "Contact info missing"}

        user = db.query(models.User).filter(
            or_(models.User.email == request.contact, models.User.phone == request.contact)
        ).first()

        companies = db.query(models.Company).filter(models.Company.user_id == user.id).all()
        comp_list = [{"id": c.id, "name": c.company_name} for c in companies]

        return {"success": True, "companies": comp_list}

    # --- STEP 4: Reset Password ---
    elif request.step == 4:
        # [FIX] Bcrypt crash prevention
        if request.new_password and len(request.new_password.encode('utf-8')) > 72:
             return {"success": False, "message": "Password is too long (max 72 characters)"}

        if not request.new_password or not request.contact or not request.company_id:
            return {"success": False, "message": "Missing required fields"}

        user = db.query(models.User).filter(
            or_(models.User.email == request.contact, models.User.phone == request.contact)
        ).first()

        # Verify ownership
        company = db.query(models.Company).filter(
            models.Company.id == request.company_id,
            models.Company.user_id == user.id
        ).first()

        if not company:
            return {"success": False, "message": "Invalid company for this user"}

        user.password_hash = utils.get_password_hash(request.new_password)
        db.commit()

        log_activity(db, "PWD_RESET_COMPLETE", "Password changed successfully", user.id, None, req.client.host)

        return {"success": True, "message": "Password reset successfully"}

    return {"success": False, "message": "Invalid step"}

# ============================================================
# 6. USER MANAGEMENT APIS
# ============================================================
@app.get("/api/users", response_model=List[schemas.UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

@app.put("/api/users/{user_id}/status")
def update_user_status(user_id: int, request: schemas.UserStatusUpdate, req: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_status = user.status
    user.status = request.status
    db.commit()

    # Log Action (Admin ID assumed as 1 for now)
    log_activity(db, "STATUS_UPDATE", f"{old_status} -> {request.status}", 1, user_id, req.client.host)
    return {"success": True, "message": f"User status updated to {request.status}"}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, req: Request, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()

    log_activity(db, "DELETE_USER", f"User ID: {user_id} deleted", 1, user_id, req.client.host)
    return {"success": True, "message": "User deleted successfully"}

@app.get("/api/users/{user_id}/logs", response_model=List[schemas.ActivityLogResponse])
def get_user_logs(user_id: int, db: Session = Depends(get_db)):
    logs = db.query(models.ActivityLog).filter(
        or_(models.ActivityLog.user_id == user_id, models.ActivityLog.target_user_id == user_id)
    ).order_by(models.ActivityLog.created_at.desc()).all()
    return logs

# ============================================================
# 7. DASHBOARD STATS
# ============================================================
@app.get("/api/users/dashboard-count")
def get_user_dashboard_counts(db: Session = Depends(get_db)):
    return {
        "total_users": db.query(models.User).count(),
        "active_users": db.query(models.User).filter(models.User.status == models.UserStatus.active).count(),
        "limited_users": db.query(models.User).filter(models.User.status == models.UserStatus.restricted).count(),
        "suspended_users": db.query(models.User).filter(models.User.status == models.UserStatus.suspended).count()
    }