"""Database CRUD operations."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from api.models import ResearchTask
from datetime import datetime
from uuid import UUID


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
