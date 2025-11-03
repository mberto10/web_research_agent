"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from datetime import datetime


class TaskCreate(BaseModel):
    """Schema for creating a new research task."""
    email: EmailStr
    research_topic: str
    frequency: str  # "daily", "weekly", "monthly"
    schedule_time: str = "09:00"


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""
    research_topic: str | None = None
    frequency: str | None = None
    schedule_time: str | None = None
    is_active: bool | None = None


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: str
    email: str
    research_topic: str
    frequency: str
    schedule_time: str
    is_active: bool
    created_at: str
    last_run_at: str | None


class BatchExecuteRequest(BaseModel):
    """Schema for batch execution request."""
    frequency: str  # "daily", "weekly", "monthly"
    callback_url: str


class BatchExecuteResponse(BaseModel):
    """Schema for batch execution response."""
    status: str
    frequency: str
    tasks_found: int
    started_at: str
