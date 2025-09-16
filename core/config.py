from __future__ import annotations

"""Lightweight configuration loader for prompts and LLM settings.

Loads a YAML file from `config/settings.yaml` when present. Provides helpers to
retrieve model/parameters per stage (fill, summarize, qc, renderer) and
per-strategy per-step overrides.
"""

from typing import Any, Dict, Optional
from pathlib import Path
import copy

try:
    import yaml
except Exception:  # pragma: no cover - yaml is a dependency in this repo
    yaml = None  # type: ignore


_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _default_config() -> Dict[str, Any]:
    return {
        "llm": {
            "defaults": {
                "fill": {"model": "gpt-4o-mini", "temperature": 0},
                "summarize": {"model": "gpt-4o-mini", "temperature": 0},
                "qc": {"model": "gpt-4o-mini", "temperature": 0},
                "renderer": {"model": "gpt-4o-mini", "temperature": 0},
            },
            "per_strategy": {},  # strategy_slug -> { fill/summarize/qc/renderer: {...} }
            "per_step": {},  # "slug:use" -> { fill: {...}, call: {inputs: {...}} }
        },
        "prompts": {
            "fill": {
                "instructions": (
                    "Fill the following JSON keys with concise values. "
                    "Only include provided keys; no extras."
                )
            },
            "summarize": {
                "template": (
                    "Cluster the following evidence into topical groups and provide "
                    "a brief bullet summary for each cluster:\n{lines}"
                )
            },
            "qc": {
                "system": (
                    "You check whether report sections are grounded in the provided "
                    "citations. Respond in JSON with keys 'grounded' (boolean), "
                    "'warnings' (list of strings), and 'inconsistencies' (list of strings)."
                )
            },
        },
    }


def load_config() -> Dict[str, Any]:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE
    base = _default_config()
    path = Path("config/settings.yaml")
    if yaml and path.exists():
        try:
            data = yaml.safe_load(path.read_text()) or {}
            if isinstance(data, dict):
                merged = copy.deepcopy(base)
                _deep_merge(merged, data)
                _CONFIG_CACHE = merged
                return merged
        except Exception:
            pass
    _CONFIG_CACHE = base
    return base


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v


def get_llm_config(stage: str, strategy_slug: Optional[str] = None, step_use: Optional[str] = None) -> Dict[str, Any]:
    """Return LLM config for a stage (fill/summarize/qc/renderer), with overrides."""
    cfg = load_config()
    result: Dict[str, Any] = {}
    # defaults
    result.update(cfg.get("llm", {}).get("defaults", {}).get(stage, {}))
    # per-strategy override
    if strategy_slug:
        strat = cfg.get("llm", {}).get("per_strategy", {}).get(strategy_slug, {})
        result.update(strat.get(stage, {}))
    # per-step override (mainly for fill or call)
    if strategy_slug and step_use:
        key = f"{strategy_slug}:{step_use}"
        pstep = cfg.get("llm", {}).get("per_step", {}).get(key, {})
        result.update(pstep.get(stage, {}))
    return result


def get_prompt(stage: str, strategy_slug: Optional[str] = None, step_use: Optional[str] = None) -> str | None:
    cfg = load_config()
    # per-step override
    if strategy_slug and step_use:
        key = f"{strategy_slug}:{step_use}"
        pstep = cfg.get("llm", {}).get("per_step", {}).get(key, {})
        p = pstep.get("prompt") or pstep.get(stage, {}).get("prompt")
        if p:
            return str(p)
    # global
    prompts = cfg.get("prompts", {}).get(stage, {})
    return str(prompts.get("instructions")) if stage == "fill" else (
        str(prompts.get("template")) if stage == "summarize" else (
            str(prompts.get("system")) if stage == "qc" else None
        )
    )


def get_step_call_overrides(strategy_slug: Optional[str], step_use: Optional[str]) -> Dict[str, Any]:
    """Return overrides to merge into step call inputs, e.g., model selection for sonar/chat."""
    cfg = load_config()
    result: Dict[str, Any] = {}
    if strategy_slug and step_use:
        key = f"{strategy_slug}:{step_use}"
        pstep = cfg.get("llm", {}).get("per_step", {}).get(key, {})
        call = pstep.get("call", {})
        inputs = call.get("inputs", {})
        if isinstance(inputs, dict):
            result.update(inputs)
    return result

