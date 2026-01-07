from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    company: str
    password: str

class LoginRequest(BaseModel):
    identifier: str
    password: str

class RequestOTP(BaseModel):
    user_id: int
    company_id: int
    identifier: str

class VerifyOTP(BaseModel):
    user_id: int
    otp_code: str

class ForgotPasswordRequest(BaseModel):
    step: int
    contact: Optional[str] = None
    method: Optional[str] = None
    otp_code: Optional[str] = None
    new_password: Optional[str] = None
    company_id: Optional[int] = None

class UserStatusUpdate(BaseModel):
    status: str

# Activity & Company schemas needed for User Response
class ActivityLogResponse(BaseModel):
    id: int
    action: str
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime
    target_user_id: Optional[int] = None
    class Config:
        from_attributes = True

class CompanyResponse(BaseModel):
    id: int
    company_name: str
    company_email: str
    company_phone: str
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    companies: List[CompanyResponse] = []
    class Config:
        from_attributes = True