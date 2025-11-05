from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
import json
from jsonschema import validate
from pydantic import BaseModel, Field
from typing import Any


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
    limits: Dict[str, Any] = Field(default_factory=dict)
    finalize: Dict[str, Any] = Field(default_factory=dict)  # New field for reactive finalize


# Index ---------------------------------------------------------------------


class StrategyVariable(BaseModel):
    """Metadata describing a variable the strategy expects."""

    name: str
    description: Optional[str] = None


class StrategyIndexEntry(BaseModel):
    """Single entry in the strategy index."""

    slug: str
    category: str
    time_window: str
    depth: str
    title: Optional[str] = None
    description: Optional[str] = None
    priority: int = 100
    active: bool = True
    required_variables: List[StrategyVariable] = Field(default_factory=list)
    # Fan-out policy for research execution. Accepts either a string ("none"|"task")
    # or an object for variable-based fan-out: { mode: "var", var: "entities", map_to: "topic", limit: 3 }
    fan_out: Any = Field(default="none")

    def normalized_fan_out(self) -> str:
        if isinstance(self.fan_out, dict):
            mode = str(self.fan_out.get("mode", "none")).strip().lower()
            return mode if mode in {"none", "task", "var"} else "none"
        val = str(self.fan_out or "none").strip().lower()
        return val if val in {"none", "task", "var"} else "none"

    def fan_out_var_name(self) -> Optional[str]:
        if isinstance(self.fan_out, dict) and self.normalized_fan_out() == "var":
            name = self.fan_out.get("var")
            return str(name) if isinstance(name, str) and name else None
        return None

    def fan_out_map_to(self) -> str:
        if isinstance(self.fan_out, dict) and self.normalized_fan_out() == "var":
            target = self.fan_out.get("map_to")
            return str(target) if isinstance(target, str) and target else "topic"
        return "topic"

    def fan_out_limit(self) -> Optional[int]:
        if isinstance(self.fan_out, dict) and self.normalized_fan_out() == "var":
            lim = self.fan_out.get("limit")
            try:
                return int(lim) if lim is not None else None
            except Exception:
                return None
        return None


_INDEX_PATH = Path(__file__).resolve().parent / "index.yaml"
_STRATEGY_INDEX_CACHE: Optional[List[StrategyIndexEntry]] = None
_STRATEGY_LOOKUP_CACHE: Dict[Tuple[str, str, str], StrategyIndexEntry] = {}


def _build_strategy_lookup(entries: List[StrategyIndexEntry]) -> None:
    """Populate the tuple lookup cache from index entries."""

    global _STRATEGY_LOOKUP_CACHE
    lookup: Dict[Tuple[str, str, str], StrategyIndexEntry] = {}
    for entry in entries:
        if not entry.active:
            continue
        key = (entry.category, entry.time_window, entry.depth)
        current = lookup.get(key)
        if current is None or entry.priority < current.priority:
            lookup[key] = entry
    _STRATEGY_LOOKUP_CACHE = lookup


def load_strategy_index(refresh: bool = False) -> List[StrategyIndexEntry]:
    """Load the strategy index from disk, caching the result."""

    global _STRATEGY_INDEX_CACHE
    if _STRATEGY_INDEX_CACHE is not None and not refresh:
        return _STRATEGY_INDEX_CACHE

    if not _INDEX_PATH.exists():
        _STRATEGY_INDEX_CACHE = []
        _STRATEGY_LOOKUP_CACHE.clear()
        return _STRATEGY_INDEX_CACHE

    raw = yaml.safe_load(_INDEX_PATH.read_text())
    items = []
    if isinstance(raw, dict):
        data = raw.get("strategies", [])
        if isinstance(data, list):
            items = data

    entries: List[StrategyIndexEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            entry = StrategyIndexEntry.model_validate(item)
        except Exception:
            continue
        if entry.active:
            entries.append(entry)

    entries.sort(key=lambda e: (e.priority, e.slug))
    _STRATEGY_INDEX_CACHE = entries
    _build_strategy_lookup(entries)
    return entries


def get_index_entry_by_slug(slug: str) -> Optional[StrategyIndexEntry]:
    """Convenience helper: fetch a single index entry by slug."""
    entries = load_strategy_index()
    for e in entries:
        if e.slug == slug:
            return e
    return None


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

def select_strategy(category: str, time_window: str, depth: str) -> Optional[str]:
    """Deterministic rules to select a strategy slug."""
    entries = load_strategy_index()
    if not entries:
        return None

    key = (category, time_window, depth)
    entry = _STRATEGY_LOOKUP_CACHE.get(key)
    if entry:
        return entry.slug
    return None


__all__ = [
    "Strategy",
    "StrategyVariable",
    "StrategyIndexEntry",
    "load_strategy",
    "load_strategy_index",
    "get_index_entry_by_slug",
    "select_strategy",
]
