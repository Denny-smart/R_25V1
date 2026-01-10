"""Pydantic schemas for bot-related responses"""

from pydantic import BaseModel
from typing import Optional, Dict, List

class BotStatusResponse(BaseModel):
    status: str
    is_running: bool
    uptime_seconds: Optional[int] = None
    start_time: Optional[str] = None
    error_message: Optional[str] = None
    balance: Optional[float] = None
    active_trades: Optional[List[Dict]] = []
    active_trades_count: Optional[int] = 0
    statistics: Optional[Dict] = {}

class BotControlResponse(BaseModel):
    success: bool
    message: str
    status: str