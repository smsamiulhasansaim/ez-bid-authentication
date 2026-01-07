import re

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