from __future__ import annotations

import re
from typing import Dict, List


def categorize_request(request: str) -> Dict[str, str]:
    """Return category, time window, and depth for a request using simple rules."""
    text = request.lower()
    if any(word in text for word in ["company", "dossier", "profile"]):
        return {"category": "company", "time_window": "month", "depth": "deep"}
    if any(word in text for word in ["latest", "today", "news", "breaking"]):
        return {"category": "news", "time_window": "day", "depth": "brief"}
    return {"category": "general", "time_window": "week", "depth": "overview"}


def split_tasks(request: str, max_tasks: int = 5) -> List[str]:
    """Deterministically split a request into sub-tasks."""
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

__all__ = ["categorize_request", "split_tasks"]
