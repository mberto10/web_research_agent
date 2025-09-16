from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
import json
from jsonschema import validate
from pydantic import BaseModel, Field


# Pydantic models -----------------------------------------------------------

class ToolStep(BaseModel):
    """Single step in a tool chain.

    Supports legacy shape (name/params/loop) and extended shape (use/inputs/...)
    for deterministic provider.method routing and optional LLM filling.
    """

    # Legacy fields
    name: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    loop: Optional[int] = None

    # Extended fields
    use: Optional[str] = None
    description: Optional[str] = None
    inputs: Dict[str, Any] = Field(default_factory=dict)
    llm_fill: List[str] = Field(default_factory=list)
    save_as: Optional[str] = None
    foreach: Optional[str] = None
    when: Optional[str] = None
    phase: Optional[str] = None  # e.g., "research" (default) or "finalize"


class StrategyMeta(BaseModel):
    slug: str
    version: int
    category: str
    time_window: str
    depth: str


class Strategy(BaseModel):
    meta: StrategyMeta
    tool_chain: List[ToolStep]
    queries: Dict[str, str] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    quorum: Dict[str, Any] = Field(default_factory=dict)
    render: Dict[str, Any] = Field(default_factory=dict)
    limits: Dict[str, Any] = Field(default_factory=dict)
    finalize: Dict[str, Any] = Field(default_factory=dict)  # New field for reactive finalize


# Loader --------------------------------------------------------------------

_PACKAGE_DIR = Path(__file__).resolve().parent
_SCHEMA = json.loads((_PACKAGE_DIR / "schema.json").read_text())


def _resolve_includes(data: Any) -> Any:
    """Recursively resolve `include:` directives using macros."""
    if isinstance(data, dict):
        if set(data.keys()) == {"include"}:
            macro_path = _PACKAGE_DIR / "macros" / f"{data['include']}.yaml"
            included = yaml.safe_load(macro_path.read_text())
            return _resolve_includes(included)
        return {k: _resolve_includes(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_includes(item) for item in data]
    return data


def load_strategy(slug: str) -> Strategy:
    """Load and validate a strategy by slug."""
    path = _PACKAGE_DIR / f"{slug}.yaml"
    raw = yaml.safe_load(path.read_text())
    raw = _resolve_includes(raw)
    validate(instance=raw, schema=_SCHEMA)
    return Strategy.model_validate(raw)


# Selector ------------------------------------------------------------------

_STRATEGY_TABLE: Dict[Tuple[str, str, str], str] = {
    ("news", "day", "brief"): "news/real_time_briefing",
    ("general", "week", "overview"): "general/week_overview",
    ("company", "month", "deep"): "company/dossier",
}


def select_strategy(category: str, time_window: str, depth: str) -> Optional[str]:
    """Deterministic rules to select a strategy slug."""
    return _STRATEGY_TABLE.get((category, time_window, depth))


__all__ = ["Strategy", "load_strategy", "select_strategy"]
