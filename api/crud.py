"""Database CRUD operations."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from api.models import ResearchTask, ScopeClassification, Strategy, GlobalSetting
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any
import logging
import hashlib

logger = logging.getLogger(__name__)


async def create_task(
    db: AsyncSession,
    email: str,
    topic: str,
    frequency: str,
    schedule_time: str
) -> ResearchTask:
    """Create new research task."""
    task = ResearchTask(
        email=email,
        research_topic=topic,
        frequency=frequency,
        schedule_time=schedule_time
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_tasks_by_email(db: AsyncSession, email: str) -> list[ResearchTask]:
    """Get all tasks for an email."""
    result = await db.execute(
        select(ResearchTask).where(ResearchTask.email == email)
    )
    return result.scalars().all()


async def get_tasks_by_frequency(
    db: AsyncSession,
    frequency: str
) -> list[ResearchTask]:
    """Get all active tasks for a frequency."""
    result = await db.execute(
        select(ResearchTask)
        .where(ResearchTask.frequency == frequency)
        .where(ResearchTask.is_active == True)
    )
    return result.scalars().all()


async def update_task(
    db: AsyncSession,
    task_id: UUID,
    **updates
) -> ResearchTask | None:
    """Update task fields."""
    result = await db.execute(
        select(ResearchTask).where(ResearchTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if task:
        for key, value in updates.items():
            if value is not None:
                setattr(task, key, value)
        await db.commit()
        await db.refresh(task)

    return task


async def mark_task_executed(db: AsyncSession, task_id: UUID):
    """Update last_run_at timestamp."""
    await db.execute(
        update(ResearchTask)
        .where(ResearchTask.id == task_id)
        .values(last_run_at=datetime.utcnow())
    )
    await db.commit()


async def delete_task(db: AsyncSession, task_id: UUID) -> bool:
    """Delete a task."""
    result = await db.execute(
        select(ResearchTask).where(ResearchTask.id == task_id)
    )
    task = result.scalar_one_or_none()

    if task:
        await db.delete(task)
        await db.commit()
        return True
    return False


async def get_cached_scope_classification(
    db: AsyncSession,
    request_text: str
) -> Optional[Dict[str, Any]]:
    """Retrieve cached classification for a research topic.

    Uses case-insensitive matching to find existing classifications.
    No expiration logic - classifications are permanent.
    """
    result = await db.execute(
        select(ScopeClassification).where(
            func.lower(ScopeClassification.request_text) == func.lower(request_text)
        ).limit(1)
    )
    entry = result.scalar_one_or_none()

    if entry:
        return {
            "category": entry.category,
            "time_window": entry.time_window,
            "depth": entry.depth,
            "strategy_slug": entry.strategy_slug,
            "tasks": entry.tasks,
            "variables": entry.variables,
        }

    return None


async def save_scope_classification(
    db: AsyncSession,
    request_text: str,
    result: Dict[str, Any]
) -> None:
    """Store classification permanently for a research topic.

    Handles duplicate writes gracefully without crashing.
    No expiration - classifications are stored permanently.
    """
    try:
        # Generate SHA-256 hash of lowercased request text for uniqueness
        request_hash = hashlib.sha256(request_text.lower().encode()).hexdigest()

        entry = ScopeClassification(
            request_hash=request_hash,
            request_text=request_text,
            category=result["category"],
            time_window=result["time_window"],
            depth=result["depth"],
            strategy_slug=result.get("strategy_slug"),
            tasks=result.get("tasks", []),
            variables=result.get("variables", {}),
            strategy_index_version="v1",  # Placeholder
            prompt_version="v1",  # Placeholder
            model_version="gpt-4",  # Placeholder
            expires_at=None  # No expiration
        )
        db.add(entry)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"Failed to cache classification: {e}")


# ============================================================================
# STRATEGY CRUD OPERATIONS
# ============================================================================

async def get_strategy(db: AsyncSession, slug: str) -> Optional[Strategy]:
    """Get strategy by slug."""
    result = await db.execute(
        select(Strategy).where(Strategy.slug == slug)
    )
    return result.scalar_one_or_none()


async def list_strategies(
    db: AsyncSession,
    active_only: bool = True
) -> list[Strategy]:
    """List all strategies, optionally filtering by active status."""
    query = select(Strategy)
    if active_only:
        query = query.where(Strategy.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


async def create_strategy(
    db: AsyncSession,
    slug: str,
    yaml_content: Dict[str, Any]
) -> Strategy:
    """Create new strategy."""
    strategy = Strategy(
        slug=slug,
        yaml_content=yaml_content,
        is_active=True
    )
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def update_strategy(
    db: AsyncSession,
    slug: str,
    yaml_content: Dict[str, Any]
) -> Optional[Strategy]:
    """Update existing strategy."""
    result = await db.execute(
        select(Strategy).where(Strategy.slug == slug)
    )
    strategy = result.scalar_one_or_none()

    if strategy:
        strategy.yaml_content = yaml_content
        strategy.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(strategy)

    return strategy


async def delete_strategy(db: AsyncSession, slug: str) -> bool:
    """Delete a strategy."""
    result = await db.execute(
        select(Strategy).where(Strategy.slug == slug)
    )
    strategy = result.scalar_one_or_none()

    if strategy:
        await db.delete(strategy)
        await db.commit()
        return True
    return False


# ============================================================================
# GLOBAL SETTINGS CRUD OPERATIONS
# ============================================================================

async def get_global_setting(
    db: AsyncSession,
    key: str
) -> Optional[GlobalSetting]:
    """Get global setting by key."""
    result = await db.execute(
        select(GlobalSetting).where(GlobalSetting.key == key)
    )
    return result.scalar_one_or_none()


async def list_global_settings(db: AsyncSession) -> list[GlobalSetting]:
    """List all global settings."""
    result = await db.execute(select(GlobalSetting))
    return result.scalars().all()


async def update_global_setting(
    db: AsyncSession,
    key: str,
    value: Dict[str, Any]
) -> GlobalSetting:
    """Update or create global setting."""
    result = await db.execute(
        select(GlobalSetting).where(GlobalSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        # Update existing
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        # Create new
        setting = GlobalSetting(key=key, value=value)
        db.add(setting)

    await db.commit()
    await db.refresh(setting)
    return setting
