#!/usr/bin/env python3
"""
Trading Session Detector
Detects trading sessions (Asian, London, New York) based on timestamp
"""
from datetime import datetime, timezone
from typing import Optional


def detect_session(ts: str) -> str:
    """
    Detect trading session based on UTC timestamp
    
    Sessions (UTC):
    - Asian: 00:00 - 09:00
    - London: 08:00 - 17:00
    - New York: 13:00 - 22:00
    """
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        hour = dt.hour
        
        # Determine session based on hour
        if 0 <= hour < 8:
            return "ASIAN"
        elif 8 <= hour < 13:
            return "LONDON"
        elif 13 <= hour < 22:
            return "NEW_YORK"
        else:
            return "ASIAN"
            
    except Exception:
        return "UNKNOWN"


def get_session_overlap(ts: str) -> Optional[str]:
    """
    Detect if timestamp falls in session overlap
    
    Overlaps (UTC):
    - London/New York: 13:00 - 17:00
    - Asian/London: 08:00 - 09:00
    """
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        hour = dt.hour
        
        if 13 <= hour < 17:
            return "LONDON_NY"
        elif 8 <= hour < 9:
            return "ASIAN_LONDON"
        else:
            return None
            
    except Exception:
        return None


def is_high_volatility_session(ts: str) -> bool:
    """Check if timestamp is in high volatility session (London/NY overlap)"""
    overlap = get_session_overlap(ts)
    return overlap == "LONDON_NY"
