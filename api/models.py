"""SQLAlchemy models for the research agent."""

from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
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


class ScopeClassification(Base):
    """Model for caching scope classification results."""

    __tablename__ = "scope_classifications"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    request_hash = Column(String(64), unique=True, nullable=False)
    request_text = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    time_window = Column(String(50), nullable=False)
    depth = Column(String(50), nullable=False)
    strategy_slug = Column(String(100), nullable=True)
    tasks = Column(JSON, nullable=False)
    variables = Column(JSON, nullable=False)
    strategy_index_version = Column(String(64), nullable=False)
    prompt_version = Column(String(64), nullable=False)
    model_version = Column(String(50), nullable=False)
    hit_count = Column(Integer, default=0, server_default=text("0"))
    last_hit_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_scope_request_hash", "request_hash"),
        Index("idx_scope_expires_at", "expires_at"),
        Index("idx_scope_strategy_category", "strategy_slug", "category"),
    )

    def __repr__(self):
        return (
            f"<ScopeClassification(id={self.id}, request_hash={self.request_hash}, "
            f"category={self.category}, strategy_slug={self.strategy_slug})>"
        )

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "request_hash": self.request_hash,
            "request_text": self.request_text,
            "category": self.category,
            "time_window": self.time_window,
            "depth": self.depth,
            "strategy_slug": self.strategy_slug,
            "tasks": self.tasks,
            "variables": self.variables,
            "strategy_index_version": self.strategy_index_version,
            "prompt_version": self.prompt_version,
            "model_version": self.model_version,
            "hit_count": self.hit_count,
            "last_hit_at": self.last_hit_at.isoformat() if self.last_hit_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class Strategy(Base):
    """Model for storing strategy configurations."""

    __tablename__ = "strategies"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    slug = Column(String(100), unique=True, nullable=False)
    yaml_content = Column(JSON, nullable=False)  # Stores entire strategy YAML as JSON
    is_active = Column(Boolean, default=True, server_default=text("true"))
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("idx_strategies_slug", "slug"),
        Index("idx_strategies_active", "is_active"),
    )

    def __repr__(self):
        return f"<Strategy(id={self.id}, slug={self.slug}, is_active={self.is_active})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "slug": self.slug,
            "yaml_content": self.yaml_content,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class GlobalSetting(Base):
    """Model for storing global configuration settings."""

    __tablename__ = "global_settings"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=False)
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        Index("idx_global_settings_key", "key"),
    )

    def __repr__(self):
        return f"<GlobalSetting(id={self.id}, key={self.key})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "id": str(self.id),
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
