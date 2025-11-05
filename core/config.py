from __future__ import annotations

"""Lightweight configuration loader for prompts and LLM settings.

Loads a YAML file from `config/settings.yaml` when present. Provides helpers to
retrieve model/parameters per stage (fill, summarize, qc) and
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
                "analyzer": {"model": "gpt-4o-mini", "temperature": 0.3},
                "cluster": {"model": "gpt-4o-mini", "temperature": 0.2},
                "nodes": {
                    "scope_classifier": {"model": "gpt-4o-mini", "temperature": 0},
                    "query_refiner": {"model": "gpt-4o-mini", "temperature": 0},
                    "finalize_react": {"model": "gpt-4o-mini", "temperature": 0},
                    "llm_analyzer": {"model": "gpt-4o-mini", "temperature": 0.3},
                },
            },
            "per_strategy": {},  # strategy_slug -> { fill/summarize/qc/analyzer: {...}, nodes: {...} }
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
            "nodes": {
                "scope_classifier": (
                    "Classify the following user request into 'category', 'time_window', "
                    "and 'depth'. Also produce a JSON array of task strings covering the "
                    "request. Respond using JSON with keys: category, time_window, depth, tasks.\n" \
                    "Request: {request}"
                ),
                "query_refiner": (
                    "Given the snippets below, suggest refined search queries for the "
                    "listed tools. Return a JSON object mapping tool names to query strings.\n" \
                    "Snippets:\n{snippets}\n\nTools: {tools}"
                ),
                "finalize_react_system": (
                    "You are a ReAct agent. First analyze the evidence, decide if a tool "
                    "call is needed, then produce the requested report. Never offer "
                    "additional services or ask follow-up questions."
                ),
                "finalize_react_analysis": (
                    "You are a ReAct agent that analyzes evidence, can call tools if needed, "
                    "and writes report sections.\n\nCurrent evidence ({evidence_count} sources):\n"
                    "{evidence_text}\n\nTopic: {topic}\nTime window: {time_window}\nCurrent date: {current_date}\n\n"
                    "Instructions:\n{instructions}\n\nThink step by step:\n1. Review the evidence - is it complete and recent enough?\n"
                    "2. If critical information is missing, make ONE tool call to fill the gap\n"
                    "3. Then write the report sections\n\nAvailable tools you can use:\n"
                    "- exa_answer: Get a direct answer to a question\n"
                    "- exa_search: Search for information\n"
                    "- sonar_call: Get an AI-generated response with web search\n\nRespond with your analysis and actions."
                ),
                "finalize_react_writer": (
                    "Based on all the evidence (including new information from tool calls), write the report.\n\n"
                    "Updated evidence ({evidence_count} sources):\n{evidence_text}\n\n"
                    "Write these sections with markdown headers (##):\n{sections_prompt}\n\n"
                    "IMPORTANT RULES:\n"
                    "1. Each section starts with ## and the section name\n"
                    "2. Use [1], [2], [3] etc. to cite sources in the text\n"
                    "3. End with a ## Sources section listing all sources with numbers\n"
                    "4. Do NOT add any offers or follow-up questions\n"
                    "5. End the report immediately after the Sources section"
                ),
                "llm_analyzer_system": (
                    "You are a research analyst that provides clear, structured analysis."
                ),
            },
            "per_strategy": {},
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
    """Return LLM config for a stage (fill/summarize/qc), with overrides."""
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


def _node_config_lookup(cfg: Dict[str, Any], node: str) -> Dict[str, Any]:
    nodes = cfg.get("nodes", {})
    entry = nodes.get(node)
    return dict(entry) if isinstance(entry, dict) else {}


def get_node_llm_config(node: str, strategy_slug: Optional[str] = None) -> Dict[str, Any]:
    """Return model configuration for a specific graph node."""
    cfg = load_config()
    result: Dict[str, Any] = {}

    defaults = cfg.get("llm", {}).get("defaults", {})
    result.update(_node_config_lookup(defaults, node))

    if strategy_slug:
        strat_cfg = cfg.get("llm", {}).get("per_strategy", {}).get(strategy_slug, {})
        if isinstance(strat_cfg, dict):
            result.update(_node_config_lookup(strat_cfg, node))

    return result


def get_node_prompt(node: str, strategy_slug: Optional[str] = None) -> Any:
    """Return the configured prompt (string or dict) for a specific node."""
    cfg = load_config()
    prompts = cfg.get("prompts", {})

    prompt: Any = None
    nodes = prompts.get("nodes", {})
    if isinstance(nodes, dict) and node in nodes:
        prompt = nodes[node]

    if strategy_slug:
        per_strategy = prompts.get("per_strategy", {}).get(strategy_slug, {})
        if isinstance(per_strategy, dict):
            strat_nodes = per_strategy.get("nodes", {})
            if isinstance(strat_nodes, dict) and node in strat_nodes:
                prompt = strat_nodes[node]

    return prompt
