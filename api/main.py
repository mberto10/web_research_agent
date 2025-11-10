"""Research Agent API - Subscription management + batch execution."""
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from uuid import UUID
from pydantic import EmailStr
import os
import logging
import sys
import secrets
from contextlib import asynccontextmanager

from api.database import get_db, db_manager
from api import schemas, crud
from api.webhooks import send_webhook
from core.config import load_config_from_db, clear_config_cache
from strategies import load_strategies_from_db
from api.models import GlobalSetting
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Starting Research Agent API - Database-First Mode")
    logger.info("=" * 60)

    # Use session directly for startup initialization
    async with db_manager.async_session_maker() as db:
        try:
            # Test database connectivity first
            logger.info("🔌 Testing database connectivity...")
            await db.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified")

            # Load strategies from database
            logger.info("📚 Loading strategies from database...")
            strategies = await load_strategies_from_db(db)

            if not strategies:
                logger.error("❌ FATAL: No strategies found in database")
                raise RuntimeError(
                    "Database empty - migration required. "
                    "Run: python scripts/migrate_main_strategies.py"
                )

            logger.info(f"✅ Loaded {len(strategies)} strategies from database")

            # Load configuration from database
            logger.info("⚙️ Loading configuration from database...")
            config = await load_config_from_db(db)

            if not config:
                logger.error("❌ FATAL: No configuration found in database")
                raise RuntimeError(
                    "Global settings are required but not found in database. "
                    "Please ensure 'llm_defaults' and 'prompts' settings exist."
                )

            logger.info("✅ Loaded configuration from database")
            logger.info("=" * 60)
            logger.info("✅ Database initialization complete - Ready to serve requests")
            logger.info("=" * 60)

        except ConnectionError as conn_err:
            logger.error("=" * 60)
            logger.error("❌ FATAL: Cannot connect to database")
            logger.error("   Check your DATABASE_URL environment variable")
            logger.error(f"   Error: {conn_err}")
            logger.error("=" * 60)
            raise RuntimeError(f"Database connection failed: {conn_err}")

        except RuntimeError as runtime_err:
            # These are our explicit errors (empty DB, etc)
            logger.error("=" * 60)
            logger.error(f"❌ FATAL: {runtime_err}")
            logger.error("=" * 60)
            raise

        except Exception as e:
            logger.error("=" * 60)
            logger.error("❌ FATAL: Unexpected error during database initialization")
            logger.error("   This may indicate corrupt data or configuration issues")
            logger.error(f"   Error: {e}")
            logger.error("=" * 60)
            raise RuntimeError(f"Database initialization failed: {e}")

    yield  # Application runs

    # Shutdown
    logger.info("👋 Shutting down Research Agent API...")
    await db_manager.close()


app = FastAPI(
    title="Research Agent API",
    description="Manage research subscriptions and execute batch briefings",
    version="1.0.0",
    lifespan=lifespan
)

# --- Authentication ---

API_KEY = os.getenv("API_SECRET_KEY")
if not API_KEY:
    raise ValueError("API_SECRET_KEY environment variable must be set")
logger.info("🔑 API Key loaded: ***REDACTED*** (configured)")

# Check critical environment variables
REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "PERPLEXITY_API_KEY",
    "EXA_API_KEY",
    "OPENAI_API_KEY"
]

missing_vars = []
for var in REQUIRED_ENV_VARS:
    value = os.getenv(var)
    if value:
        logger.info(f"✅ {var}: ***REDACTED***")
    else:
        logger.error(f"❌ {var}: NOT SET")
        missing_vars.append(var)

# Fail fast if any required environment variables are missing
if missing_vars:
    raise ValueError(f"Required environment variables not set: {', '.join(missing_vars)}")


async def verify_api_key(x_api_key: str = Header(...)):
    """Verify API key from header."""
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# --- Health Check ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "research-agent-api"
    }


# --- Admin Endpoints ---

@app.post(
    "/admin/update-temperature",
    dependencies=[Depends(verify_api_key)],
    summary="Update scope_classifier temperature to 1"
)
async def update_temperature(db: AsyncSession = Depends(get_db)):
    """Admin endpoint to update scope_classifier temperature configuration.

    Updates the database llm_defaults setting to set scope_classifier temperature to 1,
    which is required for gpt-5-mini model compatibility.

    Returns:
        Status message with old and new temperature values
    """
    try:
        # Get llm_defaults config from database
        result = await db.execute(
            select(GlobalSetting).where(GlobalSetting.key == 'llm_defaults')
        )
        setting = result.scalars().first()

        if not setting:
            raise HTTPException(
                status_code=404,
                detail="No 'llm_defaults' configuration found in database"
            )

        # Check current temperature
        old_temp = None
        if 'nodes' in setting.value and 'scope_classifier' in setting.value['nodes']:
            old_temp = setting.value['nodes']['scope_classifier'].get('temperature')

        # Update temperature to 1
        if 'nodes' not in setting.value:
            setting.value['nodes'] = {}
        if 'scope_classifier' not in setting.value['nodes']:
            setting.value['nodes']['scope_classifier'] = {}

        setting.value['nodes']['scope_classifier']['temperature'] = 1

        # Mark as modified for SQLAlchemy JSON tracking
        flag_modified(setting, 'value')

        # Commit to database
        await db.commit()

        # Clear config cache to force reload
        clear_config_cache()

        logger.info(f"✅ Updated scope_classifier temperature: {old_temp} → 1")

        return {
            "status": "success",
            "message": "Temperature updated successfully",
            "old_temperature": old_temp,
            "new_temperature": 1,
            "note": "Config cache cleared. Changes will take effect immediately."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update temperature: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update temperature: {str(e)}")


# --- Subscription Management Endpoints ---

@app.post(
    "/tasks",
    response_model=schemas.TaskResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Create research subscription"
)
async def create_task(
    task: schemas.TaskCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new research subscription for a user.

    Args:
        task: Task creation data (email, topic, frequency, schedule_time)

    Returns:
        Created task with ID and timestamps
    """
    db_task = await crud.create_task(
        db,
        task.email,
        task.research_topic,
        task.frequency,
        task.schedule_time
    )
    return db_task.to_dict()


@app.get(
    "/tasks",
    response_model=list[schemas.TaskResponse],
    dependencies=[Depends(verify_api_key)],
    summary="Get tasks by email"
)
async def get_tasks(
    email: EmailStr,
    db: AsyncSession = Depends(get_db)
):
    """Get all research tasks for a specific email.

    Args:
        email: User email address (must be valid email format)

    Returns:
        List of tasks for the email
    """
    tasks = await crud.get_tasks_by_email(db, email)
    return [task.to_dict() for task in tasks]


@app.patch(
    "/tasks/{task_id}",
    response_model=schemas.TaskResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Update task"
)
async def update_task(
    task_id: UUID,
    updates: schemas.TaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing research task.

    Args:
        task_id: UUID of the task
        updates: Fields to update

    Returns:
        Updated task

    Raises:
        HTTPException: 404 if task not found
    """
    task = await crud.update_task(
        db,
        task_id,
        **updates.model_dump(exclude_unset=True)
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@app.delete(
    "/tasks/{task_id}",
    dependencies=[Depends(verify_api_key)],
    summary="Delete task"
)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a research task.

    Args:
        task_id: UUID of the task

    Returns:
        Deletion confirmation

    Raises:
        HTTPException: 404 if task not found
    """
    deleted = await crud.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True, "task_id": str(task_id)}


# --- Batch Execution Endpoint ---

@app.post(
    "/execute/batch",
    response_model=schemas.BatchExecuteResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Execute batch research"
)
async def execute_batch(
    request: schemas.BatchExecuteRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Execute research for all tasks matching the frequency.

    This endpoint:
    1. Queries database for active tasks with matching frequency
    2. Starts background execution for each task
    3. Sends webhook to callback_url for each completed task

    Args:
        request: Batch execution request (frequency, callback_url)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution status with task count
    """
    logger.info(f"📥 Batch execution request received: frequency={request.frequency}")
    logger.info(f"📞 Callback URL: {request.callback_url}")

    # Get all active tasks for this frequency
    tasks = await crud.get_tasks_by_frequency(db, request.frequency)
    logger.info(f"🔍 Found {len(tasks)} tasks for frequency '{request.frequency}'")

    if not tasks:
        logger.warning(f"⚠️ No tasks found for frequency '{request.frequency}'")
        return schemas.BatchExecuteResponse(
            status="completed",
            frequency=request.frequency,
            tasks_found=0,
            started_at=datetime.utcnow().isoformat()
        )

    # Log task details
    for task in tasks:
        logger.info(f"  - Task {task.id}: {task.email} - {task.research_topic}")

    # Start background execution
    logger.info(f"🚀 Starting background execution for {len(tasks)} tasks")
    background_tasks.add_task(
        run_batch_research,
        tasks,
        request.callback_url
    )

    return schemas.BatchExecuteResponse(
        status="running",
        frequency=request.frequency,
        tasks_found=len(tasks),
        started_at=datetime.utcnow().isoformat()
    )


@app.post(
    "/execute/manual",
    response_model=schemas.ManualResearchResponse,
    dependencies=[Depends(verify_api_key)],
    summary="Execute manual research"
)
async def execute_manual_research(
    request: schemas.ManualResearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Execute a manual research task without database storage.

    This endpoint:
    1. Accepts a research topic directly
    2. Runs the full research architecture
    3. Returns results directly or sends to webhook

    Args:
        request: Manual research request (topic, optional callback_url, optional email)
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Execution status with results (if synchronous) or confirmation (if async with webhook)
    """
    logger.info(f"📥 Manual research request received: {request.research_topic}")
    started_at = datetime.utcnow()

    # If callback_url provided, execute in background
    if request.callback_url:
        logger.info(f"📞 Callback URL provided: {request.callback_url}")
        logger.info("🚀 Starting background execution...")

        background_tasks.add_task(
            run_manual_research,
            request.research_topic,
            request.callback_url,
            request.email
        )

        return schemas.ManualResearchResponse(
            status="running",
            research_topic=request.research_topic,
            started_at=started_at.isoformat()
        )

    # Otherwise execute synchronously and return results
    logger.info("🔄 Executing synchronously...")

    try:
        from core.graph import build_graph
        from core.state import State
        from tools import register_default_adapters
        from core.langfuse_tracing import workflow_span, flush_traces

        # Initialize research tools
        register_default_adapters()
        graph = build_graph()

        # Execute research with tracing
        with workflow_span(
            name=f"Manual Research: {request.research_topic[:50]}...",
            trace_input={
                "research_topic": request.research_topic,
                "email": request.email,
                "mode": "manual_sync"
            },
            user_id=request.email or "manual_user",
            tags=["api", "manual_execution", "synchronous"],
            metadata={
                "mode": "manual_sync"
            }
        ) as trace_ctx:
            result = await graph.ainvoke(State(user_request=request.research_topic), {})

            # Extract vars from result
            vars_dict = result.get("vars", {}) if isinstance(result, dict) else result.vars

            # Extract the full report from briefing_content
            full_report = ""
            briefing_content = vars_dict.get("briefing_content")
            if briefing_content:
                if isinstance(briefing_content, list) and len(briefing_content) > 0:
                    evidence_obj = briefing_content[0]
                    if hasattr(evidence_obj, 'snippet') and evidence_obj.snippet:
                        full_report = evidence_obj.snippet

            # Update trace with full report as output
            trace_ctx.update_trace(output=full_report)

        # Extract results
        sections = result.get("sections") if isinstance(result, dict) else result.sections
        evidence = result.get("evidence", []) if isinstance(result, dict) else result.evidence
        strategy_slug = result.get("strategy_slug") if isinstance(result, dict) else getattr(result, "strategy_slug", None)

        sections = sections or []
        evidence = evidence or []

        # Format citations
        citations = []
        for e in evidence[:10]:
            if isinstance(e, dict):
                citations.append({
                    "title": e.get("title", "No title"),
                    "url": e.get("url", ""),
                    "snippet": e.get("snippet", "")
                })
            else:
                citations.append({
                    "title": getattr(e, "title", "No title"),
                    "url": getattr(e, "url", ""),
                    "snippet": getattr(e, "snippet", "")
                })

        # Flush traces
        flush_traces()

        logger.info(f"✅ Manual research completed: {len(sections)} sections, {len(evidence)} evidence")

        return schemas.ManualResearchResponse(
            status="completed",
            research_topic=request.research_topic,
            started_at=started_at.isoformat(),
            result={
                "sections": sections,
                "citations": citations,
                "metadata": {
                    "evidence_count": len(evidence),
                    "executed_at": datetime.utcnow().isoformat(),
                    "strategy_slug": strategy_slug
                }
            }
        )

    except Exception as e:
        logger.error(f"❌ Manual research failed: {e}")
        logger.exception("Full traceback:")

        return schemas.ManualResearchResponse(
            status="failed",
            research_topic=request.research_topic,
            started_at=started_at.isoformat(),
            error=str(e)
        )


# --- Background Execution Logic ---

async def run_batch_research(tasks: list, callback_url: str):
    """Execute research for each task sequentially.

    For each task:
    1. Run the research agent with the task's topic
    2. Format results into webhook payload
    3. Send webhook to Langdock
    4. Update last_run_at timestamp

    Args:
        tasks: List of ResearchTask objects
        callback_url: Langdock webhook URL
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"🎯 BACKGROUND TASK STARTED: Processing {len(tasks)} tasks")
    logger.info(f"{'='*60}\n")

    try:
        logger.info("📦 Importing research modules...")
        from core.graph import build_graph
        from core.state import State
        from tools import register_default_adapters
        from core.langfuse_tracing import workflow_span, flush_traces
        logger.info("✅ Imports successful")

        # Initialize research tools once
        logger.info("🔧 Registering default adapters...")
        register_default_adapters()
        logger.info("✅ Adapters registered")

        logger.info("🏗️ Building research graph...")
        graph = build_graph()
        logger.info("✅ Graph built successfully")

    except Exception as e:
        logger.error(f"❌ FATAL: Failed to initialize research environment: {e}")
        logger.exception("Full traceback:")

        # Send error webhook for all tasks
        for task in tasks:
            error_payload = {
                "task_id": str(task.id),
                "email": task.email,
                "research_topic": task.research_topic,
                "frequency": task.frequency,
                "status": "failed",
                "error": f"Failed to initialize research environment: {str(e)}",
                "executed_at": datetime.utcnow().isoformat()
            }
            await send_webhook(callback_url, error_payload)
        return

    # Process each task
    for idx, task in enumerate(tasks, 1):
        logger.info(f"\n[{idx}/{len(tasks)}] 🔬 Processing task {task.id}")
        logger.info(f"  Email: {task.email}")
        logger.info(f"  Topic: {task.research_topic}")

        try:
            # Execute research with unified tracing under a single parent trace
            logger.info(f"  🚀 Invoking research graph...")

            # Create parent trace for entire research workflow
            with workflow_span(
                name=f"Research Task: {task.research_topic[:50]}...",
                trace_input={
                    "task_id": str(task.id),
                    "email": task.email,
                    "research_topic": task.research_topic,
                    "frequency": task.frequency
                },
                user_id=task.email,
                session_id=str(task.id),
                tags=["api", "batch_execution", task.frequency],
                metadata={
                    "task_id": str(task.id),
                    "frequency": task.frequency,
                    "callback_url": callback_url
                }
            ) as trace_ctx:
                config = {"configurable": {"thread_id": str(task.id)}}
                result = await graph.ainvoke(State(user_request=task.research_topic), config)

                # Extract vars from result (same pattern as sections/evidence)
                vars_dict = result.get("vars", {}) if isinstance(result, dict) else result.vars

                # Extract the full report from briefing_content
                full_report = ""  # Default to empty string
                briefing_content = vars_dict.get("briefing_content")
                if briefing_content:
                    # briefing_content is a list of Evidence objects
                    if isinstance(briefing_content, list) and len(briefing_content) > 0:
                        evidence_obj = briefing_content[0]
                        if hasattr(evidence_obj, 'snippet') and evidence_obj.snippet:
                            full_report = evidence_obj.snippet

                # Update trace with ONLY the full report as output
                trace_ctx.update_trace(output=full_report)

            logger.info(f"  ✅ Research completed")

            # Handle both dict and State object (LangGraph may return either)
            sections = result.get("sections") if isinstance(result, dict) else result.sections
            evidence = result.get("evidence", []) if isinstance(result, dict) else result.evidence
            strategy_slug = result.get("strategy_slug") if isinstance(result, dict) else getattr(result, "strategy_slug", None)

            # Ensure sections and evidence are not None
            sections = sections or []
            evidence = evidence or []

            logger.info(f"  📊 Sections: {len(sections)}, Evidence: {len(evidence)}")

            # Format citations with safe attribute access
            citations = []
            for e in evidence[:10]:  # Top 10 citations
                if isinstance(e, dict):
                    citations.append({
                        "title": e.get("title", "No title"),
                        "url": e.get("url", ""),
                        "snippet": e.get("snippet", "")
                    })
                else:
                    citations.append({
                        "title": getattr(e, "title", "No title"),
                        "url": getattr(e, "url", ""),
                        "snippet": getattr(e, "snippet", "")
                    })

            # Format payload
            payload = {
                "task_id": str(task.id),
                "email": task.email,
                "research_topic": task.research_topic,
                "frequency": task.frequency,
                "status": "completed",
                "result": {
                    "sections": sections,
                    "citations": citations,
                    "metadata": {
                        "evidence_count": len(evidence),
                        "executed_at": datetime.utcnow().isoformat(),
                        "strategy_slug": strategy_slug
                    }
                }
            }

            # Send webhook
            logger.info(f"  📤 Sending webhook to: {callback_url}")
            success = await send_webhook(callback_url, payload)

            if success:
                logger.info(f"  ✅ Webhook sent successfully")
                # Update last_run_at timestamp
                try:
                    async for session in db_manager.get_session():
                        await crud.mark_task_executed(session, task.id)
                        logger.info(f"  ✅ Database updated (last_run_at)")
                        break  # Only need one session
                except Exception as db_error:
                    logger.error(f"  ⚠️ Database update failed: {db_error}")
                    # Don't fail the whole task if just the timestamp update fails
            else:
                logger.error(f"  ❌ Webhook failed to send")

        except Exception as e:
            logger.error(f"  ❌ Error processing task {task.id}: {e}")
            logger.exception("  Full traceback:")

            # Send error webhook for this task
            error_payload = {
                "task_id": str(task.id),
                "email": task.email,
                "research_topic": task.research_topic,
                "frequency": task.frequency,
                "status": "failed",
                "error": str(e),
                "executed_at": datetime.utcnow().isoformat()
            }
            logger.info(f"  📤 Sending error webhook...")
            await send_webhook(callback_url, error_payload)

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ BATCH EXECUTION COMPLETE: {len(tasks)} tasks processed")
    logger.info(f"{'='*60}\n")

    # Flush all traces to Langfuse
    try:
        flush_traces()
        logger.info("📊 Traces flushed to Langfuse")
    except Exception as flush_error:
        logger.warning(f"⚠️ Failed to flush traces: {flush_error}")


async def run_manual_research(research_topic: str, callback_url: str, email: str = None):
    """Execute manual research and send results to webhook.

    Args:
        research_topic: The research topic to investigate
        callback_url: Webhook URL to send results to
        email: Optional email for tracking (used in Langfuse)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"🎯 MANUAL RESEARCH STARTED")
    logger.info(f"   Topic: {research_topic}")
    logger.info(f"{'='*60}\n")

    try:
        logger.info("📦 Importing research modules...")
        from core.graph import build_graph
        from core.state import State
        from tools import register_default_adapters
        from core.langfuse_tracing import workflow_span, flush_traces
        logger.info("✅ Imports successful")

        # Initialize research tools
        logger.info("🔧 Registering default adapters...")
        register_default_adapters()
        logger.info("✅ Adapters registered")

        logger.info("🏗️ Building research graph...")
        graph = build_graph()
        logger.info("✅ Graph built successfully")

        # Execute research with tracing
        logger.info(f"🚀 Invoking research graph...")

        with workflow_span(
            name=f"Manual Research: {research_topic[:50]}...",
            trace_input={
                "research_topic": research_topic,
                "email": email,
                "mode": "manual_async"
            },
            user_id=email or "manual_user",
            tags=["api", "manual_execution", "asynchronous"],
            metadata={
                "mode": "manual_async",
                "callback_url": callback_url
            }
        ) as trace_ctx:
            result = await graph.ainvoke(State(user_request=research_topic), {})

            # Extract vars from result
            vars_dict = result.get("vars", {}) if isinstance(result, dict) else result.vars

            # Extract the full report from briefing_content
            full_report = ""
            briefing_content = vars_dict.get("briefing_content")
            if briefing_content:
                if isinstance(briefing_content, list) and len(briefing_content) > 0:
                    evidence_obj = briefing_content[0]
                    if hasattr(evidence_obj, 'snippet') and evidence_obj.snippet:
                        full_report = evidence_obj.snippet

            # Update trace with full report as output
            trace_ctx.update_trace(output=full_report)

        logger.info(f"✅ Research completed")

        # Extract results
        sections = result.get("sections") if isinstance(result, dict) else result.sections
        evidence = result.get("evidence", []) if isinstance(result, dict) else result.evidence
        strategy_slug = result.get("strategy_slug") if isinstance(result, dict) else getattr(result, "strategy_slug", None)

        sections = sections or []
        evidence = evidence or []

        logger.info(f"📊 Sections: {len(sections)}, Evidence: {len(evidence)}")

        # Format citations
        citations = []
        for e in evidence[:10]:
            if isinstance(e, dict):
                citations.append({
                    "title": e.get("title", "No title"),
                    "url": e.get("url", ""),
                    "snippet": e.get("snippet", "")
                })
            else:
                citations.append({
                    "title": getattr(e, "title", "No title"),
                    "url": getattr(e, "url", ""),
                    "snippet": getattr(e, "snippet", "")
                })

        # Format payload
        payload = {
            "email": email or "manual_user",
            "research_topic": research_topic,
            "frequency": "manual",
            "status": "completed",
            "result": {
                "sections": sections,
                "citations": citations,
                "metadata": {
                    "evidence_count": len(evidence),
                    "executed_at": datetime.utcnow().isoformat(),
                    "strategy_slug": strategy_slug
                }
            }
        }

        # Send webhook
        logger.info(f"📤 Sending webhook to: {callback_url}")
        success = await send_webhook(callback_url, payload)

        if success:
            logger.info(f"✅ Webhook sent successfully")
        else:
            logger.error(f"❌ Webhook failed to send")

    except Exception as e:
        logger.error(f"❌ Error processing manual research: {e}")
        logger.exception("Full traceback:")

        # Send error webhook
        error_payload = {
            "email": email or "manual_user",
            "research_topic": research_topic,
            "frequency": "manual",
            "status": "failed",
            "error": str(e),
            "executed_at": datetime.utcnow().isoformat()
        }
        logger.info(f"📤 Sending error webhook...")
        await send_webhook(callback_url, error_payload)

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ MANUAL RESEARCH COMPLETE")
    logger.info(f"{'='*60}\n")

    # Flush all traces to Langfuse
    try:
        flush_traces()
        logger.info("📊 Traces flushed to Langfuse")
    except Exception as flush_error:
        logger.warning(f"⚠️ Failed to flush traces: {flush_error}")


# ============================================================================
# STRATEGY MANAGEMENT ENDPOINTS
# ============================================================================

@app.get(
    "/api/strategies",
    response_model=list[schemas.StrategyResponse],
    tags=["Strategies"]
)
async def list_strategies(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """List all strategies."""
    strategies = await crud.list_strategies(db, active_only=active_only)
    return [s.to_dict() for s in strategies]


@app.get(
    "/api/strategies/{slug}",
    response_model=schemas.StrategyResponse,
    tags=["Strategies"]
)
async def get_strategy(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """Get a single strategy by slug."""
    strategy = await crud.get_strategy(db, slug)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{slug}' not found")
    return strategy.to_dict()


@app.post(
    "/api/strategies",
    response_model=schemas.StrategyResponse,
    status_code=201,
    tags=["Strategies"]
)
async def create_strategy(
    data: schemas.StrategyCreate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """Create a new strategy."""
    # Check if slug already exists
    existing = await crud.get_strategy(db, data.slug)
    if existing:
        raise HTTPException(status_code=400, detail=f"Strategy '{data.slug}' already exists")

    strategy = await crud.create_strategy(db, data.slug, data.yaml_content)

    logger.info(f"✓ Created strategy: {data.slug}")
    logger.warning("⚠️ Configuration updated. Restart application to apply changes.")
    return strategy.to_dict()


@app.put(
    "/api/strategies/{slug}",
    response_model=schemas.StrategyResponse,
    tags=["Strategies"]
)
async def update_strategy(
    slug: str,
    data: schemas.StrategyUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """Update an existing strategy."""
    strategy = await crud.update_strategy(db, slug, data.yaml_content)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy '{slug}' not found")

    logger.info(f"✓ Updated strategy: {slug}")
    logger.warning("⚠️ Configuration updated. Restart application to apply changes.")
    return strategy.to_dict()


@app.delete(
    "/api/strategies/{slug}",
    tags=["Strategies"]
)
async def delete_strategy(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """Delete a strategy."""
    success = await crud.delete_strategy(db, slug)
    if not success:
        raise HTTPException(status_code=404, detail=f"Strategy '{slug}' not found")

    logger.info(f"✓ Deleted strategy: {slug}")
    logger.warning("⚠️ Configuration updated. Restart application to apply changes.")
    return {"success": True, "message": f"Strategy '{slug}' deleted"}


# ============================================================================
# GLOBAL SETTINGS ENDPOINTS
# ============================================================================

@app.get(
    "/api/settings",
    response_model=list[schemas.GlobalSettingResponse],
    tags=["Settings"]
)
async def list_settings(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """List all global settings."""
    settings = await crud.list_global_settings(db)
    return [s.to_dict() for s in settings]


@app.get(
    "/api/settings/{key}",
    response_model=schemas.GlobalSettingResponse,
    tags=["Settings"]
)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """Get a single setting by key."""
    setting = await crud.get_global_setting(db, key)
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return setting.to_dict()


@app.put(
    "/api/settings/{key}",
    response_model=schemas.GlobalSettingResponse,
    tags=["Settings"]
)
async def update_setting(
    key: str,
    data: schemas.GlobalSettingUpdate,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """Update or create a global setting."""
    setting = await crud.update_global_setting(db, key, data.value)

    logger.info(f"✓ Updated setting: {key}")
    logger.warning("⚠️ Configuration updated. Restart application to apply changes.")
    return setting.to_dict()


# --- Optional: Parallel Execution (Future Enhancement) ---
#
# Uncomment and use this for parallel execution when ready:
#
# import asyncio
#
# async def run_batch_research_parallel(tasks: list, callback_url: str):
#     """Execute research in parallel with concurrency limit."""
#     semaphore = asyncio.Semaphore(5)  # Max 5 concurrent executions
#
#     async def execute_one(task):
#         async with semaphore:
#             # ... same logic as sequential version
#             pass
#
#     await asyncio.gather(*[execute_one(task) for task in tasks])
