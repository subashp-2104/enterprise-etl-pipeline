import re
from datetime import datetime, timezone
from typing import Any, Optional

def clean_email(email: Optional[str]) -> Optional[str]:
    """
    Standardizes email strings to lowercase and removes outer whitespaces.
    """
    if not email:
        return None
    return email.strip().lower()

def clean_phone(phone: Optional[str]) -> Optional[str]:
    """
    Sanitizes phone strings by removing common special characters like
    dashes, spaces, and parenthesis, preserving the leading plus sign.
    """
    if not phone:
        return None
    # Strip any characters that are not digits or the leading + symbol
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    return cleaned

def parse_datetime(val: Any) -> datetime:
    """
    Parses unix integer timestamps, ISO-8601 timestamp strings, or date-only strings,
    returning a timezone-aware UTC datetime.
    """
    if val is None:
        raise ValueError("Cannot parse None values into datetimes")
        
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
        
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc)
        
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            raise ValueError("Cannot parse empty strings into datetimes")
        
        # Standardize Salesforce 'Z' suffix to +00:00 for uniform ISO handling
        standardized_str = val_str.replace("Z", "+00:00")
        
        try:
            dt = datetime.fromisoformat(standardized_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            # Handle YYYY-MM-DD date-only strings
            try:
                dt = datetime.strptime(standardized_str, "%Y-%m-%d")
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                raise ValueError(f"Unsupported timestamp format: {val_str}")
                
    raise TypeError(f"Cannot parse type {type(val)} as datetime")
