"""
Database Schemas for Wolf of Wall Street.site

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name (e.g., User -> "user").
"""
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    hashed_password: str = Field(..., description="BCrypt hashed password")
    avatar_url: Optional[str] = Field(None, description="Profile avatar URL")
    plan: str = Field("free", description="Subscription plan: free|pro|elite")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Session(BaseModel):
    user_id: str
    token: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class ChatMessage(BaseModel):
    user_id: str
    role: str = Field(..., description="user|assistant")
    content: str
    created_at: Optional[datetime] = None

class AnalysisRequest(BaseModel):
    user_id: str
    symbol: str
    timeframe: str = Field("1D", description="e.g., 1m,5m,1H,1D")
    strategy: str = Field("SMA", description="SMA|EMA|RSI")
    lookback: int = Field(50, ge=2, le=500)

class WatchlistItem(BaseModel):
    user_id: str
    symbol: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None
