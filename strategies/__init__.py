from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
import json
import logging
from jsonschema import validate
from pydantic import BaseModel, Field
from typing import Any

logger = logging.getLogger(__name__)


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


# Constants and caches ------------------------------------------------------

_PACKAGE_DIR = Path(__file__).resolve().parent
_SCHEMA = json.loads((_PACKAGE_DIR / "schema.json").read_text())
_INDEX_PATH = _PACKAGE_DIR / "index.yaml"
_STRATEGY_INDEX_CACHE: Optional[List[StrategyIndexEntry]] = None
_STRATEGY_LOOKUP_CACHE: Dict[Tuple[str, str, str], StrategyIndexEntry] = {}
_DB_STRATEGIES_CACHE: Dict[str, Strategy] = {}  # Cache for DB-loaded strategies
_CACHES_INITIALIZED: bool = False  # Flag to enforce immutability after startup


async def load_strategies_from_db(db_session) -> Dict[str, Strategy]:
    """Load all active strategies from database.

    Returns dict mapping slug -> Strategy.
    Populates the global _DB_STRATEGIES_CACHE.
    """
    global _DB_STRATEGIES_CACHE, _CACHES_INITIALIZED

    if _CACHES_INITIALIZED:
        raise RuntimeError("Strategy caches are immutable after initialization. Restart application to reload strategies.")

    try:
        from api.crud import list_strategies

        db_strategies = await list_strategies(db_session, active_only=True)

        result = {}
        for db_strat in db_strategies:
            try:
                # Validate and parse strategy
                yaml_content = db_strat.yaml_content
                validate(instance=yaml_content, schema=_SCHEMA)
                strategy = Strategy.model_validate(yaml_content)
                result[db_strat.slug] = strategy
            except Exception as e:
                logger.error(f"Failed to parse strategy {db_strat.slug} from DB: {e}")
                raise RuntimeError(f"Invalid strategy '{db_strat.slug}' in database. Fix the strategy data before starting the application.") from e

        _DB_STRATEGIES_CACHE = result
        logger.info(f"✓ Loaded {len(result)} strategies from database")
        return result

    except Exception as e:
        logger.warning(f"Failed to load strategies from database: {e}")
        return {}


def clear_strategy_cache():
    """Clear all strategy caches.

    WARNING: This is intended for testing only. In production, strategy changes
    require an application restart. Clears the immutability flag to allow re-initialization.
    """
    global _STRATEGY_INDEX_CACHE, _STRATEGY_LOOKUP_CACHE, _DB_STRATEGIES_CACHE, _CACHES_INITIALIZED
    _STRATEGY_INDEX_CACHE = None
    _STRATEGY_LOOKUP_CACHE.clear()
    _DB_STRATEGIES_CACHE.clear()
    _CACHES_INITIALIZED = False  # Reset immutability flag for re-initialization
    logger.debug("Strategy caches cleared")


def _build_strategy_lookup(entries: List[StrategyIndexEntry]) -> None:
    """Populate the tuple lookup cache from index entries."""

    global _STRATEGY_LOOKUP_CACHE, _CACHES_INITIALIZED

    if _CACHES_INITIALIZED:
        raise RuntimeError("Strategy caches are immutable after initialization. Restart application to reload strategies.")
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
    """Load the strategy index from database cache only.

    Cache must be populated via load_strategies_from_db() during startup.
    Extracts fan_out and required_variables metadata from index.yaml.
    """

    global _STRATEGY_INDEX_CACHE, _CACHES_INITIALIZED

    if _CACHES_INITIALIZED and refresh:
        raise RuntimeError("Strategy caches are immutable after initialization. Restart application to reload strategies.")

    if _STRATEGY_INDEX_CACHE is not None and not refresh:
        return _STRATEGY_INDEX_CACHE

    entries: List[StrategyIndexEntry] = []

    # Load index.yaml to get metadata (fan_out, required_variables, etc.)
    index_metadata = {}
    try:
        if _INDEX_PATH.exists():
            raw_index = yaml.safe_load(_INDEX_PATH.read_text())
            if raw_index and "strategies" in raw_index:
                for entry in raw_index["strategies"]:
                    index_metadata[entry["slug"]] = entry
    except Exception as e:
        logger.warning(f"Failed to load index.yaml metadata: {e}")

    # Load from database cache only
    for slug, strategy in _DB_STRATEGIES_CACHE.items():
        try:
            # Get metadata from index.yaml if available
            metadata = index_metadata.get(slug, {})

            # Extract fan_out and required_variables from metadata
            fan_out = metadata.get("fan_out", "none")
            required_vars = []
            if "required_variables" in metadata:
                for var in metadata["required_variables"]:
                    if isinstance(var, dict) and "name" in var:
                        required_vars.append(StrategyVariable(**var))

            # Build index entry from strategy metadata
            entry = StrategyIndexEntry(
                slug=slug,
                title=metadata.get("title", slug.replace('_', ' ').replace('/', ' - ').title()),
                category=strategy.meta.category,
                time_window=strategy.meta.time_window,
                depth=strategy.meta.depth,
                description=metadata.get("description", f"Database strategy: {slug}"),
                priority=metadata.get("priority", 10),
                active=True,
                fan_out=fan_out,
                required_variables=required_vars
            )
            entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to create index entry for DB strategy {slug}: {e}")

    if not entries:
        raise RuntimeError(
            "No strategies loaded from database. "
            "Database must be populated first. "
            "Please run: python scripts/migrate_main_strategies.py"
        )

    entries.sort(key=lambda e: (e.priority, e.slug))
    _STRATEGY_INDEX_CACHE = entries
    _build_strategy_lookup(entries)
    _CACHES_INITIALIZED = True  # Mark caches as immutable after successful initialization
    logger.info(f"✓ Strategy index loaded: {len(entries)} strategies from database")
    return entries


def get_index_entry_by_slug(slug: str) -> Optional[StrategyIndexEntry]:
    """Convenience helper: fetch a single index entry by slug."""
    entries = load_strategy_index()
    for e in entries:
        if e.slug == slug:
            return e
    return None


# Loader --------------------------------------------------------------------

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
    """Load and validate a strategy by slug.

    Only loads from database cache. Cache must be populated at startup.
    """
    # Check database cache
    if slug in _DB_STRATEGIES_CACHE:
        logger.debug(f"Loading strategy '{slug}' from database cache")
        return _DB_STRATEGIES_CACHE[slug]

    # Strategy not found in database
    available = list(_DB_STRATEGIES_CACHE.keys())
    raise ValueError(
        f"Strategy '{slug}' not found in database cache. "
        f"Available strategies: {available}. "
        f"Please ensure the strategy exists in the database."
    )


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
    "load_strategies_from_db",
    "get_index_entry_by_slug",
    "select_strategy",
    "clear_strategy_cache",
]
