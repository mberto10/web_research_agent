"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Dict, Any, Literal

# Type alias for frequency validation
Frequency = Literal["daily", "weekly", "monthly"]


class TaskCreate(BaseModel):
    """Schema for creating a new research task."""
    email: EmailStr
    research_topic: str = Field(
        max_length=500,
        description="Research topic (max 500 characters)"
    )
    frequency: Frequency
    schedule_time: str = Field(
        default="09:00",
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Time in HH:MM format (00:00 to 23:59)"
    )


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""
    research_topic: str | None = Field(
        default=None,
        max_length=500,
        description="Research topic (max 500 characters)"
    )
    frequency: Frequency | None = None
    schedule_time: str | None = Field(
        default=None,
        pattern=r"^([01]\d|2[0-3]):([0-5]\d)$",
        description="Time in HH:MM format (00:00 to 23:59)"
    )
    is_active: bool | None = None


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: str
    email: str
    research_topic: str
    frequency: Frequency
    schedule_time: str
    is_active: bool
    created_at: str
    last_run_at: str | None


class BatchExecuteRequest(BaseModel):
    """Schema for batch execution request."""
    frequency: Frequency
    callback_url: str


class BatchExecuteResponse(BaseModel):
    """Schema for batch execution response."""
    status: str
    frequency: Frequency
    tasks_found: int
    started_at: str


class ManualResearchRequest(BaseModel):
    """Schema for manual research execution request."""
    research_topic: str = Field(
        max_length=500,
        description="Research topic (max 500 characters)"
    )
    callback_url: str | None = Field(
        default=None,
        description="Optional webhook URL to send results to"
    )
    email: EmailStr | None = Field(
        default=None,
        description="Optional email to send results to (for tracking in Langfuse)"
    )


class ManualResearchResponse(BaseModel):
    """Schema for manual research response."""
    status: str
    research_topic: str
    started_at: str
    result: Dict[str, Any] | None = None
    error: str | None = None


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
