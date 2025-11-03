"""SQLAlchemy models for the research agent."""

from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from api.database import Base


class ResearchTask(Base):
    """Model for storing research tasks."""
    
    __tablename__ = "research_tasks"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email = Column(Text, nullable=False)
    research_topic = Column(Text, nullable=False)
    frequency = Column(Text, nullable=True)
    schedule_time = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, server_default=text("true"))
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    last_run_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        Index("idx_research_tasks_email", "email"),
        Index("idx_research_tasks_active", "is_active"),
    )
    
    def __repr__(self):
        return (
            f"<ResearchTask(id={self.id}, email={self.email}, "
            f"topic={self.research_topic}, frequency={self.frequency})>"
        )
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "email": self.email,
            "research_topic": self.research_topic,
            "frequency": self.frequency,
            "schedule_time": self.schedule_time,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }
