import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from app.core.config import settings
from app.utils.formatters import format_phone_bd

def send_email_otp(email_to: str, otp: str, user_name: str = "User"):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Verification Code"
        msg["From"] = f"Ez Bid <{settings.MAIL_USERNAME}>"
        msg["To"] = email_to

        html_content = f"""
        <html><body>
            <h2>Verification Code</h2>
            <p>Hello {user_name},</p>
            <p>Your code is: <strong style='font-size: 24px; color: #1a56db;'>{otp}</strong></p>
            <p>Expires in 10 minutes.</p>
        </body></html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as server:
            server.starttls()
            server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            server.sendmail(settings.MAIL_USERNAME, email_to, msg.as_string())
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

def send_sms_otp(phone: str, otp: str):
    try:
        formatted_phone = format_phone_bd(phone)
        message = f"Your Ez Bid verification code: {otp}. Valid for 10 minutes."
        
        data = {
            "api_key": settings.SMS_API_KEY,
            "senderid": settings.SMS_SENDER_ID,
            "number": formatted_phone,
            "message": message
        }
        
        response = requests.post(settings.SMS_API_URL, data=data)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("success") or res_json.get("response_code") == 202:
                return True
        return False
    except Exception as e:
        print(f"SMS Error: {e}")
        return False

def send_otp_dispatch(identifier: str, otp: str, user_name: str = "User"):
    if "@" in identifier:
        return send_email_otp(identifier, otp, user_name)
    else:
        return send_sms_otp(identifier, otp)