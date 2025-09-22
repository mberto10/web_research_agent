from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from core.config import get_node_llm_config, get_node_prompt
from core.langfuse_tracing import get_langfuse_client, observe
from core.debug_log import dbg
from strategies import StrategyIndexEntry, load_strategy_index


_LLM_CACHE: Dict[str, Dict[str, Any]] = {}
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
        if name not in variables or not variables[name].strip():
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


@observe(as_type="generation", name="scope-classifier")
def _llm_scope(request: str) -> Optional[Dict[str, Any]]:
    """Try to use an LLM to scope a request. Returns None on failure."""
    if request in _LLM_CACHE:
        return _LLM_CACHE[request]
    try:  # Import inside the function so the dependency is optional.
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    entries = _active_strategies()
    if not entries:
        return None

    node_cfg = get_node_llm_config("scope_classifier")
    model = node_cfg.get("model", "gpt-4o-mini")
    response_kwargs = {k: v for k, v in node_cfg.items() if k != "model"}
    response_kwargs.pop("response_format", None)

    prompt_template = _scope_prompt_template()
    if not prompt_template:
        return None

    prompt = _format_scope_prompt(prompt_template, request, entries)
    if not prompt:
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
            lf_client.update_current_generation(
                model=model,
                input={
                    "request": request,
                    "strategies": [entry.model_dump() for entry in entries],
                },
                output=data,
                usage_details=usage_details,
                metadata={"component": "scope_classifier"},
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
        _LLM_CACHE[request] = result
        return result
    except Exception:
        return None
    return None


def categorize_request(request: str) -> Dict[str, Any]:
    """Return category, time window, and depth for a request."""
    llm = _llm_scope(request)
    if llm:
        return {
            "category": llm.get("category", "general"),
            "time_window": llm.get("time_window", "week"),
            "depth": llm.get("depth", "overview"),
            "strategy_slug": llm.get("strategy_slug"),
            "variables": llm.get("variables", {}),
        }

    fallback = _heuristic_scope(request, DEFAULT_MAX_TASKS)
    return {
        "category": fallback["category"],
        "time_window": fallback["time_window"],
        "depth": fallback["depth"],
        "strategy_slug": fallback.get("strategy_slug"),
        "variables": fallback.get("variables", {}),
    }


def split_tasks(request: str, max_tasks: int = DEFAULT_MAX_TASKS) -> List[str]:
    """Split a request into sub-tasks."""
    llm = _llm_scope(request)
    if llm:
        tasks = llm.get("tasks", [])
        if isinstance(tasks, list) and tasks:
            return [t for t in tasks if t][:max_tasks]

    return _heuristic_tasks(request, max_tasks)


def scope_request(request: str, max_tasks: int = DEFAULT_MAX_TASKS) -> Dict[str, Any]:
    """Return category/time window/depth and tasks for a request."""
    llm = _llm_scope(request)
    if llm:
        return {
            "category": llm.get("category", "general"),
            "time_window": llm.get("time_window", "week"),
            "depth": llm.get("depth", "overview"),
            "tasks": [t for t in llm.get("tasks", []) if t][:max_tasks],
            "strategy_slug": llm.get("strategy_slug"),
            "variables": llm.get("variables", {}),
        }
    fallback = _heuristic_scope(request, max_tasks)
    return {
        "category": fallback["category"],
        "time_window": fallback["time_window"],
        "depth": fallback["depth"],
        "tasks": fallback["tasks"][:max_tasks],
        "strategy_slug": fallback.get("strategy_slug"),
        "variables": fallback.get("variables", {}),
    }


__all__ = ["categorize_request", "split_tasks", "scope_request"]
