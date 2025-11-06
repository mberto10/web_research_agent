"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Dict, Any


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


# ============================================================================
# STRATEGY SCHEMAS
# ============================================================================

class StrategyCreate(BaseModel):
    """Schema for creating a new strategy."""
    slug: str
    yaml_content: Dict[str, Any]


class StrategyUpdate(BaseModel):
    """Schema for updating an existing strategy."""
    yaml_content: Dict[str, Any]


class StrategyResponse(BaseModel):
    """Schema for strategy response."""
    id: str
    slug: str
    yaml_content: Dict[str, Any]
    is_active: bool
    created_at: str
    updated_at: str


# ============================================================================
# GLOBAL SETTINGS SCHEMAS
# ============================================================================

class GlobalSettingUpdate(BaseModel):
    """Schema for updating a global setting."""
    value: Dict[str, Any]


class GlobalSettingResponse(BaseModel):
    """Schema for global setting response."""
    id: str
    key: str
    value: Dict[str, Any]
    created_at: str
    updated_at: str
