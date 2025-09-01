from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional


_LLM_CACHE: Dict[str, Dict[str, Any]] = {}


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

    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            "Classify the following user request into 'category' (news, company, "
            "general), determine 'time_window' (day, week, month) and 'depth' "
            "(brief, overview, deep). Also provide a list of short 'tasks' that "
            "cover the request. Respond using JSON with keys: category, "
            "time_window, depth, tasks.\nRequest: " + request
        )
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt,
            response_format={"type": "json_object"},
        )
        raw = response.output[0].content[0].text  # type: ignore
        data = json.loads(raw)
        if isinstance(data, dict):
            _LLM_CACHE[request] = data
            return data
    except Exception:
        return None
    return None


def categorize_request(request: str) -> Dict[str, str]:
    """Return category, time window, and depth for a request."""
    llm = _llm_scope(request)
    if llm:
        return {
            "category": llm.get("category", "general"),
            "time_window": llm.get("time_window", "week"),
            "depth": llm.get("depth", "overview"),
        }

    # Heuristic fallback
    text = request.lower()
    if any(word in text for word in ["company", "dossier", "profile"]):
        return {"category": "company", "time_window": "month", "depth": "deep"}
    if any(word in text for word in ["latest", "today", "news", "breaking"]):
        return {"category": "news", "time_window": "day", "depth": "brief"}
    return {"category": "general", "time_window": "week", "depth": "overview"}


def split_tasks(request: str, max_tasks: int = 5) -> List[str]:
    """Split a request into sub-tasks."""
    llm = _llm_scope(request)
    if llm:
        tasks = llm.get("tasks", [])
        if isinstance(tasks, list) and tasks:
            return [t for t in tasks if t][:max_tasks]

    # Heuristic fallback
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


def scope_request(request: str, max_tasks: int = 5) -> Dict[str, Any]:
    """Return category/time window/depth and tasks for a request."""
    llm = _llm_scope(request)
    if llm:
        return {
            "category": llm.get("category", "general"),
            "time_window": llm.get("time_window", "week"),
            "depth": llm.get("depth", "overview"),
            "tasks": [t for t in llm.get("tasks", []) if t][:max_tasks],
        }
    cat = categorize_request(request)
    tasks = split_tasks(request, max_tasks)
    return {**cat, "tasks": tasks}


__all__ = ["categorize_request", "split_tasks", "scope_request"]
