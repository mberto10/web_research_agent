from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_node_llm_config, get_node_prompt
from core.langfuse_tracing import get_langfuse_client, observe
from core.debug_log import dbg
from strategies import StrategyIndexEntry, load_strategy_index
from api.crud import get_cached_scope_classification, save_scope_classification

logger = logging.getLogger(__name__)


DEFAULT_MAX_TASKS = 5


def _active_strategies() -> List[StrategyIndexEntry]:
    return load_strategy_index()


def _scope_prompt_template() -> Optional[str]:
    prompt_cfg = get_node_prompt("scope_classifier")
    if isinstance(prompt_cfg, str):
        return prompt_cfg
    if isinstance(prompt_cfg, dict):
        for key in ("template", "prompt", "system", "text"):
            val = prompt_cfg.get(key)
            if isinstance(val, str):
                return val
    return None


def _strategy_prompt_payload(entries: List[StrategyIndexEntry]) -> Dict[str, str]:
    catalog_lines: List[str] = []
    catalog_json: List[Dict[str, Any]] = []
    for entry in entries:
        required = ", ".join(var.name for var in entry.required_variables) or "(none)"
        catalog_lines.append(
            f"- {entry.title or entry.slug} ({entry.slug}): "
            f"category={entry.category}, time_window={entry.time_window}, depth={entry.depth}; "
            f"requires variables: {required}"
        )
        catalog_json.append(
            {
                "slug": entry.slug,
                "category": entry.category,
                "time_window": entry.time_window,
                "depth": entry.depth,
                "title": entry.title or entry.slug,
                "description": entry.description or "",
                "required_variables": [var.model_dump() for var in entry.required_variables],
            }
        )

    return {
        "strategies_table": "\n".join(catalog_lines),
        "strategies_json": json.dumps(catalog_json, ensure_ascii=False, indent=2),
    }


def _format_scope_prompt(template: str, request: str, entries: List[StrategyIndexEntry]) -> Optional[str]:
    safe_request = request.replace("{", "{{").replace("}", "}}")
    payload = _strategy_prompt_payload(entries)
    data = {"request": safe_request, **payload}
    try:
        return template.format(**data)
    except Exception:
        return None


def _tool_schema(entries: List[StrategyIndexEntry]) -> Dict[str, Any]:
    categories = sorted({e.category for e in entries})
    time_windows = sorted({e.time_window for e in entries})
    depths = sorted({e.depth for e in entries})
    slugs = [e.slug for e in entries]

    return {
        "type": "function",
        "function": {
            "name": "set_scope",
            "description": "Select the most appropriate research strategy and outline tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_slug": {"type": "string", "enum": slugs},
                    "category": {"type": "string", "enum": categories},
                    "time_window": {"type": "string", "enum": time_windows},
                    "depth": {"type": "string", "enum": depths},
                    "tasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Short task statements covering the request.",
                    },
                    "variables": {
                        "type": "object",
                        "description": "Map each required variable name to its value (string or list of strings).",
                        "additionalProperties": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}}
                            ]
                        },
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional reasoning for the chosen strategy.",
                    },
                },
                "required": ["strategy_slug", "category", "time_window", "depth", "tasks"],
                "additionalProperties": False,
            },
        },
    }


def _match_entry_by_slug(entries: List[StrategyIndexEntry], slug: str) -> Optional[StrategyIndexEntry]:
    for entry in entries:
        if entry.slug == slug:
            return entry
    return None


def _heuristic_tasks(request: str, max_tasks: int) -> List[str]:
    parts = re.split(r",| and | & |;|\+|/|\|", request)
    tasks: List[str] = []
    for part in parts:
        cleaned = part.strip()
        if cleaned and cleaned not in tasks:
            tasks.append(cleaned)
        if len(tasks) >= max_tasks:
            break
    if not tasks:
        tasks = [request.strip()]
    return tasks


def _ensure_variables(
    entry: StrategyIndexEntry,
    tasks: List[str],
    request: str,
    provided: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    variables: Dict[str, Any] = {}
    if provided:
        for key, value in provided.items():
            if not isinstance(key, str):
                continue
            # Accept strings or list[str]
            if isinstance(value, str):
                if value.strip():
                    variables[key] = value.strip()
            elif isinstance(value, list):
                vv = [str(it).strip() for it in value if isinstance(it, (str, int, float)) and str(it).strip()]
                if vv:
                    variables[key] = vv

    first_task = tasks[0] if tasks else request.strip()
    fallback_value = request.strip()

    for var in entry.required_variables:
        name = var.name
        if not name:
            continue
        if name not in variables or (isinstance(variables[name], str) and not variables[name].strip()):
            if name == "topic":
                variables[name] = first_task or fallback_value
            else:
                variables[name] = fallback_value

    return variables


def _heuristic_entry(request: str, entries: List[StrategyIndexEntry]) -> Optional[StrategyIndexEntry]:
    if not entries:
        return None

    ordered = sorted(entries, key=lambda e: (e.priority, e.slug))
    text = request.lower()

    def pick(categories: List[str]) -> Optional[StrategyIndexEntry]:
        for entry in ordered:
            if entry.category in categories:
                return entry
        return None

    if any(word in text for word in ["company", "dossier", "profile", "corporate"]):
        target = pick(["company"])
        if target:
            return target
    if any(word in text for word in ["research", "paper", "academic", "study"]):
        target = pick(["academic"])
        if target:
            return target
    if any(word in text for word in ["finance", "financial", "market", "stock", "earnings"]):
        target = pick(["financial", "finance"])
        if target:
            return target
    if any(word in text for word in ["latest", "today", "news", "breaking", "update"]):
        target = pick(["news"])
        if target:
            return target

    target = pick(["general"])
    if target:
        return target
    return ordered[0]


def _heuristic_scope(request: str, max_tasks: int) -> Dict[str, Any]:
    """DEPRECATED: Heuristic-based scoping fallback.

    This function is no longer used in production workflows. It is retained
    for backward compatibility with direct imports only.

    WARNING: Do not use this function. LLM classification is now required.
    All production workflows will fail if LLM classification is unavailable.
    """
    entries = _active_strategies()
    entry = _heuristic_entry(request, entries)
    tasks = _heuristic_tasks(request, max_tasks)
    if entry:
        variables = _ensure_variables(entry, tasks, request)
        return {
            "category": entry.category,
            "time_window": entry.time_window,
            "depth": entry.depth,
            "strategy_slug": entry.slug,
            "tasks": tasks,
            "variables": variables,
        }

    # Fallback legacy values if no index exists
    return {
        "category": "general",
        "time_window": "week",
        "depth": "overview",
        "strategy_slug": None,
        "tasks": tasks,
        "variables": {"topic": tasks[0] if tasks else request.strip()},
    }


def _llm_scope(request: str) -> Optional[Dict[str, Any]]:
    """Try to use an LLM to scope a request. Returns None on failure.

    NOTE: This is an internal implementation function. Tracing happens at the
    categorize_request() level to avoid duplicate traces.
    """
    try:  # Import inside the function so the dependency is optional.
        from openai import OpenAI  # type: ignore
    except Exception:
        logger.warning("⚠️ SCOPE: OpenAI import failed. Workflow will fail.")
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("⚠️ SCOPE: No OPENAI_API_KEY set. Workflow will fail.")
        return None

    entries = _active_strategies()
    if not entries:
        logger.warning("⚠️ SCOPE: No active strategies found")
        return None

    node_cfg = get_node_llm_config("scope_classifier")
    model = node_cfg.get("model", "gpt-4o-mini")
    response_kwargs = {k: v for k, v in node_cfg.items() if k != "model"}
    response_kwargs.pop("response_format", None)

    prompt_template = _scope_prompt_template()
    if not prompt_template:
        logger.warning("⚠️ SCOPE: No prompt template configured")
        return None

    prompt = _format_scope_prompt(prompt_template, request, entries)
    if not prompt:
        logger.warning("⚠️ SCOPE: Prompt formatting failed")
        return None
    try:
        model = get_node_llm_config("scope_classifier").get("model", "gpt-4o-mini")
        dbg.prompt("scope.classifier", prompt, model=model)
    except Exception:
        pass

    lf_client = get_langfuse_client()

    if lf_client:
        lf_client.update_current_generation(
            model=model,
            input={
                "request": request,
                "strategies": [entry.model_dump() for entry in entries],
            },
            metadata={"component": "scope_classifier"},
        )

    try:
        client = OpenAI(api_key=api_key)
        tool = _tool_schema(entries)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": "set_scope"}},
            **response_kwargs,
        )

        choice = response.choices[0]
        message = choice.message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not tool_calls:
            return None

        call = tool_calls[0]
        function = getattr(call, "function", None) or call.get("function")
        if not function:
            return None
        arguments = getattr(function, "arguments", None) or function.get("arguments")
        if not arguments:
            return None

        raw_args = arguments if isinstance(arguments, str) else json.dumps(arguments)
        data = json.loads(raw_args)
        try:
            dbg.event("scope.classifier.result", data=data)
        except Exception:
            pass

        if lf_client:
            usage = getattr(response, "usage", None)
            usage_details = None
            if usage:
                usage_details = {
                    "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                }
            # Second update: Add output and usage (input already set above)
            lf_client.update_current_generation(
                output=data,
                usage_details=usage_details,
            )

        slug = data.get("strategy_slug")
        entry = _match_entry_by_slug(entries, slug) if slug else None
        if not entry:
            entry = _heuristic_entry(request, entries)
            if not entry:
                return None

        tasks_data = data.get("tasks", [])
        if isinstance(tasks_data, list):
            tasks = [t.strip() for t in tasks_data if isinstance(t, str) and t.strip()]
        else:
            tasks = []
        if not tasks:
            tasks = _heuristic_tasks(request, DEFAULT_MAX_TASKS)

        raw_variables = data.get("variables")
        provided_variables: Dict[str, Any] = {}
        if isinstance(raw_variables, dict):
            for k, v in raw_variables.items():
                if not isinstance(k, str):
                    continue
                if isinstance(v, str) and v.strip():
                    provided_variables[k] = v.strip()
                elif isinstance(v, list):
                    vv = [str(it).strip() for it in v if isinstance(it, (str, int, float)) and str(it).strip()]
                    if vv:
                        provided_variables[k] = vv

        result = {
            "category": entry.category,
            "time_window": entry.time_window,
            "depth": entry.depth,
            "strategy_slug": entry.slug,
            "tasks": tasks,
        }
        variables = _ensure_variables(entry, tasks, request, provided_variables) if entry else {}
        result["variables"] = variables
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ SCOPE: Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response: {raw_args[:500] if 'raw_args' in locals() else 'Not available'}...")
        return None
    except Exception as e:
        logger.error(f"❌ SCOPE: Categorization failed with error: {e}")
        logger.exception("Full traceback:")
        return None


async def categorize_request(request: str) -> Dict[str, Any]:
    """Return category, time window, depth, strategy, and variables for a request.

    DEPRECATED: Consider using scope_request() for complete scoping.
    This function is maintained for backward compatibility but internally
    calls scope_request() and extracts only categorization fields (excluding tasks).

    Returns a subset of scope_request() output with only:
    - category, time_window, depth, strategy_slug, variables
    """
    result = await scope_request(request)
    return {
        "category": result["category"],
        "time_window": result["time_window"],
        "depth": result["depth"],
        "strategy_slug": result.get("strategy_slug"),
        "variables": result.get("variables", {}),
    }


async def split_tasks(request: str, max_tasks: int = DEFAULT_MAX_TASKS) -> List[str]:
    """Split a request into sub-tasks.

    DEPRECATED: Consider using scope_request() for complete scoping.
    This function is maintained for backward compatibility but internally
    calls scope_request() and extracts only the tasks field.

    Returns only the tasks list from scope_request() output.
    """
    result = await scope_request(request, max_tasks=max_tasks)
    return result["tasks"]


@observe(as_type="generation", name="scope-request")
async def scope_request(
    request: str,
    max_tasks: int = DEFAULT_MAX_TASKS,
    db_session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """Primary scoping function - returns complete scope analysis in one call.

    This is the main entry point for scope analysis. It checks the database cache first,
    and if there's no cache hit, makes a single LLM call and stores the result.

    Args:
        request: The user's research request to scope
        max_tasks: Maximum number of tasks to return (default: 5)
        db_session: Optional database session for caching (default: None)

    Returns:
        Complete scope analysis with fields:
        - category: Type of research (e.g., "news", "financial", "general")
        - time_window: Time scope (e.g., "day", "week", "month")
        - depth: Research depth (e.g., "brief", "overview", "deep")
        - strategy_slug: Selected strategy identifier
        - tasks: List of sub-tasks
        - variables: Extracted variables (e.g., {"topic": "AI agents"})

    Raises:
        RuntimeError: If LLM classification fails (no API key, import error, etc.)
    """
    lf_client = get_langfuse_client()

    # Log input for tracing
    if lf_client:
        lf_client.update_current_generation(
            input={"request": request, "max_tasks": max_tasks},
            metadata={"component": "scope_request"}
        )

    # Try cache lookup first if db_session provided
    if db_session:
        try:
            cached = await get_cached_scope_classification(db_session, request)
            if cached:
                logger.info(f"✅ SCOPE: Cache hit for: {request[:50]}...")
                if lf_client:
                    lf_client.update_current_generation(
                        output=cached,
                        metadata={"source": "cache", "cache_hit": True}
                    )
                return cached
            else:
                logger.debug(f"🔍 SCOPE: Cache miss for: {request[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ SCOPE: Cache lookup failed: {e}")

    # Try LLM-based scoping (required)
    llm = _llm_scope(request)

    if not llm:
        error_msg = "LLM classification failed. Check OPENAI_API_KEY and configuration."
        logger.error(f"❌ SCOPE: {error_msg}")
        if lf_client:
            lf_client.update_current_generation(
                output={"error": error_msg},
                metadata={"source": "llm_failed"}
            )
        raise RuntimeError(error_msg)

    # Extract and validate tasks
    tasks = llm.get("tasks", [])
    if isinstance(tasks, list) and tasks:
        tasks = [t for t in tasks if t][:max_tasks]
    else:
        tasks = _heuristic_tasks(request, max_tasks)

    result = {
        "category": llm.get("category", "general"),
        "time_window": llm.get("time_window", "week"),
        "depth": llm.get("depth", "overview"),
        "strategy_slug": llm.get("strategy_slug"),
        "tasks": tasks,
        "variables": llm.get("variables", {}),
    }

    # Store in cache if db_session provided
    if db_session:
        try:
            await save_scope_classification(db_session, request, result)
            logger.info(f"💾 SCOPE: Stored classification in cache")
        except Exception as e:
            logger.warning(f"⚠️ SCOPE: Cache storage failed: {e}")

    if lf_client:
        lf_client.update_current_generation(
            output=result,
            metadata={
                "source": "llm",
                "strategy": result.get("strategy_slug"),
                "task_count": len(tasks),
                "cache_stored": db_session is not None
            }
        )

    logger.info(f"✅ SCOPE: Complete scope - {result['category']}/{result['time_window']}/{result['depth']} -> {result.get('strategy_slug')} with {len(tasks)} tasks")
    return result


__all__ = ["categorize_request", "split_tasks", "scope_request"]
