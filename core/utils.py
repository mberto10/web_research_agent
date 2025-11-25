from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Sequence, Tuple, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar('T')


def render_template_string(template: str, variables: Dict[str, Any]) -> str:
    """Very small Jinja-like template renderer with {{var}} replacement.

    Also supports simple attribute and index dereferencing inside braces, e.g.
    {{seed_results[0].url}}. If an expression can't be resolved, it is left as-is.
    """
    def _resolve_expr(expr: str) -> Any:
        expr = expr.strip()
        # shortlist filter: var | shortlist:K
        m = re.match(r"^([a-zA-Z_][\w\.]*(?:\[[^\]]+\])*)(?:\s*\|\s*shortlist\s*:\s*(\d+))?$", expr)
        if m:
            base, k_str = m.group(1), m.group(2)
            val = resolve_path(base, variables)
            if k_str and isinstance(val, Sequence):
                try:
                    k = int(k_str)
                    return list(val)[:k]
                except Exception:
                    return val
            return val
        # Fallback: plain path
        return resolve_path(expr, variables)

    def repl(match: re.Match[str]) -> str:
        expr = match.group(1)
        val = _resolve_expr(expr)
        if isinstance(val, (str, int, float)):
            return str(val)
        # For lists/dicts, keep original token to avoid accidental stringification
        return match.group(0)

    return re.sub(r"\{\{([^}]+)\}\}", repl, template)


def resolve_path(path: str, variables: Dict[str, Any]) -> Any:
    """Resolve a dotted/indexed path like foo[0].bar against variables."""
    # Split keeping bracketed indices
    tokens = _tokenize_path(path)
    cur: Any = variables
    for tok in tokens:
        if tok == "":
            continue
        if isinstance(cur, dict) and tok in cur:
            cur = cur[tok]
            continue
        # index access
        m = re.match(r"^(\w+)\[(\d+)\]$", tok)
        if m:
            name, idx_s = m.group(1), m.group(2)
            cur = cur.get(name) if isinstance(cur, dict) else getattr(cur, name, None)
            try:
                idx = int(idx_s)
                if isinstance(cur, (list, tuple)) and 0 <= idx < len(cur):
                    cur = cur[idx]
                else:
                    return None
            except Exception:
                return None
            continue
        # attribute access
        if hasattr(cur, tok):
            cur = getattr(cur, tok)
        elif isinstance(cur, dict):
            cur = cur.get(tok)
        else:
            return None
    return cur


def _tokenize_path(path: str) -> List[str]:
    # Split on dots that are not within brackets
    out: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in path:
        if ch == '.' and depth == 0:
            out.append(''.join(buf))
            buf = []
        else:
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth = max(0, depth - 1)
            buf.append(ch)
    if buf:
        out.append(''.join(buf))
    return out


def render_inputs(inputs: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """Render a dict of inputs using template variables recursively for strings."""
    rendered: Dict[str, Any] = {}
    for k, v in inputs.items():
        if isinstance(v, str):
            rendered[k] = render_template_string(v, variables)
        else:
            rendered[k] = v
    return rendered


def eval_list_expr(expr: str, variables: Dict[str, Any]) -> List[Any] | None:
    """Evaluate a list-y template like {{seed_results | shortlist:5}} or {{pages}}.
    Returns the list or None if resolution failed.
    """
    expr = expr.strip()
    m = re.match(r"^\{\{([^}]+)\}\}$", expr)
    if not m:
        # treat as simple path
        val = resolve_path(expr, variables)
        return list(val) if isinstance(val, (list, tuple)) else None
    inner = m.group(1).strip()
    # shortlist filter
    m2 = re.match(r"^([a-zA-Z_][\w\.]*(?:\[[^\]]+\])*)\s*\|\s*shortlist\s*:\s*(\d+)$", inner)
    if m2:
        base, k_s = m2.group(1), m2.group(2)
        val = resolve_path(base, variables)
        if isinstance(val, (list, tuple)):
            try:
                return list(val)[: int(k_s)]
            except Exception:
                return list(val)
        return None
    val = resolve_path(inner, variables)
    return list(val) if isinstance(val, (list, tuple)) else None


def parse_date_range(timeframe: str, base_date: datetime | None = None) -> Tuple[datetime, datetime]:
    """Parse natural language date ranges like 'last 24 hours', 'past week', etc.
    
    Args:
        timeframe: Natural language description of date range
        base_date: Reference date (defaults to today)
    
    Returns:
        Tuple of (start_date, end_date)
    """
    base_date = base_date or datetime.now()
    timeframe_lower = timeframe.lower().strip()
    
    # Map common time window values to date ranges
    if timeframe_lower in ["day", "daily"]:
        start_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = base_date
    elif timeframe_lower in ["week", "weekly"]:
        start_date = base_date - timedelta(weeks=1)
        end_date = base_date
    elif timeframe_lower in ["month", "monthly"]:
        start_date = base_date - timedelta(days=30)
        end_date = base_date
    elif timeframe_lower in ["year", "yearly"]:
        start_date = base_date - timedelta(days=365)
        end_date = base_date
    # Handle specific patterns
    elif "last 24 hours" in timeframe_lower or "past 24 hours" in timeframe_lower:
        start_date = base_date - timedelta(days=1)
        end_date = base_date
    elif "last week" in timeframe_lower or "past week" in timeframe_lower or timeframe_lower == "letzte woche":
        start_date = base_date - timedelta(weeks=1)
        end_date = base_date
    elif "last month" in timeframe_lower or "past month" in timeframe_lower:
        start_date = base_date - timedelta(days=30)
        end_date = base_date
    elif "today" in timeframe_lower:
        start_date = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = base_date
    elif "yesterday" in timeframe_lower:
        yesterday = base_date - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        # Default to last 24 hours
        start_date = base_date - timedelta(days=1)
        end_date = base_date
    
    return (start_date, end_date)


def format_date_for_query(date: datetime, format_type: str = "natural") -> str:
    """Format a date for use in search queries.
    
    Args:
        date: The date to format
        format_type: 'natural' for human-readable, 'iso' for ISO format
    
    Returns:
        Formatted date string
    """
    if format_type == "natural":
        return date.strftime("%B %d, %Y")
    elif format_type == "iso":
        return date.strftime("%Y-%m-%d")
    else:
        return str(date)


def retry_on_exception(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for exponential backoff retry on transient failures.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay cap in seconds (default: 30.0)
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            "Retry %d/%d for %s after %.1fs: %s",
                            attempt + 1, max_retries, func.__name__, delay, e
                        )
                        time.sleep(delay)
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Unexpected retry state")  # Should never reach here
        return wrapper
    return decorator

