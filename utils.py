import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import re
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def mask_identifier(identifier: str):
    if "@" in identifier:
        parts = identifier.split("@")
        return f"{parts[0][:3]}***@{parts[1]}" if len(parts[0]) > 3 else f"{parts[0]}***@{parts[1]}"
    else:
        return f"{identifier[:3]}******{identifier[-2:]}" if len(identifier) >= 11 else identifier

def format_phone_bd(phone: str):
    mobile = re.sub(r'[^0-9]', '', phone)
    if len(mobile) == 11 and mobile.startswith('01'):
        return '880' + mobile[1:]
    elif len(mobile) == 10 and mobile.startswith('1'):
        return '880' + mobile
    else:
        return '880' + mobile.lstrip('0')

def send_email_otp(email_to: str, otp: str, user_name: str = "User"):
    try:
        sender_email = os.getenv("MAIL_USERNAME")
        sender_password = os.getenv("MAIL_PASSWORD")
        smtp_server = os.getenv("MAIL_SERVER")
        smtp_port = int(os.getenv("MAIL_PORT"))

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Verification Code"
        msg["From"] = f" Ez Bid <{sender_email}>"
        msg["To"] = email_to

        html_content = f"""
        <html>
            <body>
                <h2>Verification Code</h2>
                <p>Hello {user_name},</p>
                <p>Your code is: <strong style='font-size: 24px; color: #1a56db;'>{otp}</strong></p>
                <p>Expires in 10 minutes.</p>
            </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email_to, msg.as_string())
        return True
    except Exception:
        return False

def send_sms_otp(phone: str, otp: str):
    try:
        formatted_phone = format_phone_bd(phone)
        message = f"Your Ez Bid verification code: {otp}. Valid for 10 minutes."
        
        url = os.getenv("SMS_API_URL")
        data = {
            "api_key": os.getenv("SMS_API_KEY"),
            "senderid": os.getenv("SMS_SENDER_ID"),
            "number": formatted_phone,
            "message": message
        }
        
        response = requests.post(url, data=data)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("success") or res_json.get("response_code") == 202:
                return True
        return False
    except Exception:
        return False

def send_otp(identifier: str, otp: str, user_name: str = "User"):
    if "@" in identifier:
        return send_email_otp(identifier, otp, user_name)
    else:
        return send_sms_otp(identifier, otp)