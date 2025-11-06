from __future__ import annotations

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from datetime import datetime
import json
import logging
import os
import re
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict, List, Optional

from .state import State, Evidence
from .utils import render_template_string, render_inputs, resolve_path, eval_list_expr
from .config import (
    get_llm_config,
    get_prompt,
    get_step_call_overrides,
    get_node_llm_config,
    get_node_prompt,
)
from .langfuse_tracing import get_langfuse_client, observe
from tools import get_tool, register_default_adapters
from .scope import scope_request
from strategies import load_strategy, select_strategy, get_index_entry_by_slug
from api.database import db_manager


logger = logging.getLogger(__name__)

DEFAULT_QUERY_REFINER_PROMPT = (
    "Given the snippets below, suggest refined search queries for the listed tools. "
    "Return a JSON object mapping tool names to query strings.\nSnippets:\n{snippets}\n\n"
    "Tools: {tools}"
)

DEFAULT_FINALIZE_SYSTEM_PROMPT = (
    "You are a ReAct agent. First analyze the evidence, decide if a tool call is needed, "
    "then produce the requested report. Never offer additional services or ask follow-up "
    "questions."
)

DEFAULT_FINALIZE_ANALYSIS_TEMPLATE = (
    "You are a ReAct agent that analyzes evidence, can call tools if needed, and writes "
    "report sections.\n\nCurrent evidence ({evidence_count} sources):\n{evidence_text}\n\n"
    "Topic: {topic}\nTime window: {time_window}\nCurrent date: {current_date}\n\n"
    "Instructions:\n{instructions}\n\nThink step by step:\n"
    "1. Review the evidence - is it complete and recent enough?\n"
    "2. If critical information is missing, make ONE tool call to fill the gap\n"
    "3. Then write the report sections\n\nAvailable tools you can use:\n"
    "- exa_answer: Get a direct answer to a question\n"
    "- exa_search: Search for information\n"
    "- sonar_call: Get an AI-generated response with web search\n\nRespond with your analysis and actions."
)

DEFAULT_FINALIZE_WRITER_TEMPLATE = (
    "Based on all the evidence (including new information from tool calls), write the report.\n\n"
    "Updated evidence ({evidence_count} sources):\n{evidence_text}\n\n"
    "Write these sections with markdown headers (##):\n{sections_prompt}\n\n"
    "IMPORTANT RULES:\n"
    "1. Each section starts with ## and the section name\n"
    "2. Use [1], [2], [3] etc. to cite sources in the text\n"
    "3. End with a ## Sources section listing all sources with numbers\n"
    "4. Do NOT add any offers or follow-up questions\n"
    "5. End the report immediately after the Sources section"
)


def _format_prompt(template: str, **kwargs: Any) -> str:
    """Format a template while escaping braces in values."""
    safe_kwargs: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            safe_kwargs[key] = value.replace("{", "{{").replace("}", "}}")
        else:
            safe_kwargs[key] = value
    return template.format(**safe_kwargs)


def _prompt_text(value: Any, default: str) -> str:
    """Normalize prompt config entries."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("template", "prompt", "system", "text"):
            text = value.get(key)
            if isinstance(text, str):
                return text
    return default


def _normalize_step(step: Any) -> Dict[str, Any]:
    """Return a plain-dict representation of a strategy/tool step."""

    if isinstance(step, dict):
        base = dict(step)
    else:
        base = {
            "use": getattr(step, "use", None),
            "name": getattr(step, "name", None),
            "inputs": getattr(step, "inputs", None),
            "params": getattr(step, "params", None),
            "llm_fill": getattr(step, "llm_fill", None),
            "save_as": getattr(step, "save_as", None),
            "foreach": getattr(step, "foreach", None),
            "when": getattr(step, "when", None),
            "phase": getattr(step, "phase", None),
            "description": getattr(step, "description", None),
        }

    base.setdefault("phase", base.get("phase") or "research")
    base["inputs"] = dict(base.get("inputs") or {})
    base["params"] = dict(base.get("params") or {})
    base["llm_fill"] = list(base.get("llm_fill") or [])
    return base


def _resolve_step_inputs(
    step_inputs: Dict[str, Any],
    variables: Dict[str, Any],
    state_vars: Dict[str, Any],
    *,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = {**variables, **state_vars}
    rendered = render_inputs(step_inputs or {}, context)
    if overrides:
        rendered.update(overrides)
    return rendered


def _record_evidence(results: Any, bucket: List[Evidence]) -> None:
    _maybe_add_evidence(results, bucket)


def _log_step_error(step_label: str, exc: Exception) -> None:
    logger.exception("Research step '%s' failed", step_label, exc_info=exc)


def _as_evidence_list(results: Any) -> List[Evidence]:
    if isinstance(results, Evidence):
        return [results]
    if isinstance(results, list) and results and isinstance(results[0], Evidence):
        return results
    return []


@observe(as_type="generation", name="cluster-evidence")
def _cluster_llm(prompt: str, model: str | None = None) -> str:
    """Call an LLM to cluster evidence and return the raw text response."""
    from openai import OpenAI  # Lazy import to keep optional dependency
    import time
    
    # Get model from config if not provided
    if model is None:
        from core.config import get_llm_config
        cfg = get_llm_config("cluster")
        model = cfg.get("model", "gpt-4o-mini")

    client = OpenAI()
    lf_client = get_langfuse_client()
    if lf_client:
        lf_client.update_current_generation(
            model=model,
            input={"prompt": prompt},
            metadata={"component": "cluster_llm"},
        )
    
    start_time = time.time()
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    choice = response["choices"][0] if isinstance(response, dict) else response.choices[0]
    message = choice["message"] if isinstance(choice, dict) else choice.message
    content = message.get("content") if isinstance(message, dict) else message.content
    duration = time.time() - start_time
    logger.info(f"🤖 LLM: Cluster call completed in {duration:.2f}s")

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
            output=content,
            usage_details=usage_details,
        )
    return content


def _render_template(template: str, variables: Dict[str, str]) -> str:
    """Kept for backward compatibility; delegates to utils."""
    return render_template_string(template, variables)


def _canonical_url(url: str) -> str:
    """Normalize URLs for deduplication."""
    parsed = urlparse(url)
    clean_path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))


def _dedupe_and_score(evidence: List[Evidence], limit: int | None) -> List[Evidence]:
    """Dedupe by canonical URL while preserving original order and applying the limit."""
    deduped: List[Evidence] = []
    seen: set[str] = set()
    for ev in evidence:
        key = _canonical_url(ev.url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ev)

    if limit is not None:
        return deduped[:limit]
    return deduped


def _step_query_key(name: str) -> str | None:
    """Map a tool step name to its query dictionary key."""
    if name.startswith("sonar"):
        return "sonar"
    if name.startswith("exa_search"):
        return "exa_search"
    if name.startswith("exa_answer"):
        return "exa_answer"
    return None


@observe(as_type="generation", name="query-refinement")
def _refine_queries_with_llm(
    last_results: List[Evidence],
    allowed_keys: List[str],
    max_queries: int | None = None,
    strategy_slug: str | None = None,
) -> Dict[str, str]:
    """Use an LLM to suggest refined queries based on recent results."""
    if not last_results or not allowed_keys:
        return {}

    snippets: List[str] = []
    for ev in last_results:
        if ev.snippet:
            snippets.append(ev.snippet)
        elif ev.title:
            snippets.append(ev.title)
        if len(snippets) >= 3:
            break
    if not snippets:
        return {}

    snippets_block = "\n".join(f"- {s}" for s in snippets)
    prompt_template = _prompt_text(
        get_node_prompt("query_refiner", strategy_slug),
        DEFAULT_QUERY_REFINER_PROMPT,
    )
    prompt = _format_prompt(
        prompt_template,
        snippets=snippets_block or "-",
        tools=", ".join(allowed_keys),
    )

    try:
        from openai import OpenAI  # Imported lazily

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {}

        node_cfg = get_node_llm_config("query_refiner", strategy_slug)
        model = node_cfg.get("model", "gpt-4o-mini")
        call_kwargs = {k: v for k, v in node_cfg.items() if k != "model"}

        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_generation(
                model=model,
                input={
                    "snippets": snippets_block.split("\n"),
                    "tools": allowed_keys,
                    "strategy": strategy_slug,
                },
                metadata={"component": "query_refiner"},
            )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            **call_kwargs,
        )
        content = response.choices[0].message["content"]
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
                output=content,
                usage_details=usage_details,
            )
        data = json.loads(content)
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    refined: Dict[str, str] = {}
    for key in allowed_keys:
        if key in data:
            refined[key] = data[key]
            if max_queries is not None and len(refined) >= max_queries:
                break
    return refined


async def scope(state: State) -> State:
    """Scope phase categorizes the request and selects a strategy."""
    logger.info(f"🔍 SCOPE: Starting scope analysis for: {state.user_request[:100]}...")

    # Create database session for caching
    scope_result = None
    try:
        async with db_manager.async_session_maker() as db_session:
            # Always perform complete scope analysis (single unified LLM call with optional caching)
            scope_result = await scope_request(state.user_request, db_session=db_session)
    except Exception as e:
        logger.warning(f"⚠️ SCOPE: Database session creation failed, proceeding without cache: {e}")
        # Fallback: call without database session
        scope_result = await scope_request(state.user_request, db_session=None)

    if not scope_result:
        raise RuntimeError("Scope analysis failed")

    # Apply categorization fields (overwrite any pre-populated values)
    state.category = scope_result["category"]
    state.time_window = scope_result["time_window"]
    state.depth = scope_result["depth"]

    # Apply strategy
    slug = scope_result.get("strategy_slug")
    if isinstance(slug, str) and slug:
        state.strategy_slug = slug

    # Apply tasks
    state.tasks = scope_result["tasks"]
    state.queries = list(state.tasks)

    # Merge variables into state
    scope_vars = scope_result.get("variables")
    if isinstance(scope_vars, dict):
        for key, value in scope_vars.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, str):
                state.vars[key] = value
            elif isinstance(value, list):
                # Only store list of strings
                vv = [str(it) for it in value if isinstance(it, (str, int, float))]
                state.vars[key] = vv

    # Select strategy if not provided by LLM
    if (
        state.strategy_slug is None
        and state.category
        and state.time_window
        and state.depth
    ):
        slug = select_strategy(state.category, state.time_window, state.depth)
        if slug:
            state.strategy_slug = slug
            # Load strategy to surface validation errors early.
            load_strategy(slug)

    # Log detailed scope decision for debugging
    logger.info(f"📋 SCOPE Decision:")
    logger.info(f"  Category: {state.category}")
    logger.info(f"  Time Window: {state.time_window}")
    logger.info(f"  Depth: {state.depth}")
    logger.info(f"  Strategy: {state.strategy_slug}")
    logger.info(f"  Tasks: {state.tasks}")
    logger.info(f"  Variables: {state.vars}")

    return state


def research(state: State) -> State:
    """Execute the research phase based on the selected strategy using a single pass.

    Variables from the scope/fill phases (e.g., topic, dates) are rendered into the
    strategy's steps. We no longer fan-out across multiple tasks; instead we derive
    a canonical topic and run the chain once.
    """
    logger.info(f"🔬 RESEARCH: Starting research phase")
    if not state.strategy_slug:
        logger.warning(f"⚠️ RESEARCH: No strategy selected, skipping")
        return state

    register_default_adapters(silent=True)
    strategy = load_strategy(state.strategy_slug)
    max_results = strategy.limits.get("max_results") if strategy.limits else None
    max_llm_queries = strategy.limits.get("max_llm_queries") if strategy.limits else None

    runtime_plan: List[Dict[str, Any]] = state.vars.get("runtime_plan", [])  # type: ignore
    source_steps: List[Any] = runtime_plan if runtime_plan else strategy.tool_chain
    normalized_steps = [_normalize_step(step) for step in source_steps]
    research_steps = [s for s in normalized_steps if (s.get("phase") or "research") == "research"]
    if not research_steps:
        return state

    base_queries = dict(strategy.queries or {})

    # Determine fan-out policy and iteration patches
    patches: List[Dict[str, Any]] = []
    idx_entry = get_index_entry_by_slug(state.strategy_slug) if state.strategy_slug else None
    fan_out_policy = idx_entry.normalized_fan_out() if idx_entry else "none"

    # Base variables (single canonical topic)
    single_topic = (
        (state.vars.get("topic") or (state.tasks[0] if state.tasks else state.user_request))
        if state.user_request is not None
        else ""
    )
    canonical_topic = single_topic if isinstance(single_topic, str) else str(single_topic)
    logger.info(f"🔬 RESEARCH: Using strategy '{state.strategy_slug}' with topic: {canonical_topic[:100]}")

    if fan_out_policy == "task" and state.tasks:
        for t in state.tasks:
            if isinstance(t, str) and t:
                patches.append({"topic": t, "subtopic": t})
        if not patches:
            patches.append({})
    elif fan_out_policy == "var" and idx_entry is not None:
        var_name = idx_entry.fan_out_var_name()
        map_to = idx_entry.fan_out_map_to()
        limit = idx_entry.fan_out_limit()
        values: List[Any] = []
        if var_name:
            v = state.vars.get(var_name)
            if isinstance(v, list):
                values = v
            elif isinstance(v, str) and v:
                values = [v]
        if limit is not None:
            values = values[: max(0, limit)]
        for val in values:
            sval = val if isinstance(val, str) else str(val)
            patch: Dict[str, Any] = {map_to: sval}
            if map_to == "topic":
                patch.setdefault("subtopic", sval)
            patches.append(patch)
        if not patches:
            patches.append({})
    else:
        patches = [{}]

    aggregated_evidence: List[Evidence] = []

    for patch in patches:
        variables: Dict[str, Any] = {
            "topic": canonical_topic,
            "subtopic": canonical_topic,
            "time_window": state.time_window or "",
            "region": "",
        }
        variables.update(state.vars)
        variables.update(patch)

        task_evidence: List[Evidence] = []
        last_results: List[Evidence] = []
        task_queries = dict(base_queries)

        for idx, step in enumerate(research_steps):
            step_label = step.get("use") or step.get("name") or f"step-{idx}"

            if step.get("when") and not _eval_when(step["when"], state):
                continue

            use = step.get("use")
            if not use and not step.get("name"):
                continue

            # Legacy tool-chain support -------------------------------------------------
            if not use and step.get("name"):
                name: str = step["name"]
                results: Any = []
                try:
                    if name.startswith("sonar"):
                        prompt_t = task_queries.get("sonar", "{{topic}}")
                        prompt = _render_template(prompt_t, variables)
                        tool = get_tool("sonar")
                        results = tool.call(prompt, **step.get("params", {}))
                    elif name.startswith("exa_search"):
                        query_t = task_queries.get("exa_search", "{{topic}}")
                        query = _render_template(query_t, variables)
                        params = {
                            key: _render_template(val, variables) if isinstance(val, str) else val
                            for key, val in step.get("params", {}).items()
                        }
                        tool = get_tool("exa")
                        results = tool.call(query, **params)
                    elif name.startswith("exa_contents"):
                        top_k = step.get("params", {}).get("top_k", 0)
                        tool = get_tool("exa")
                        fetched: List[Evidence] = []
                        for ev in last_results[:top_k]:
                            call_params = {k: v for k, v in step.get("params", {}).items() if k != "top_k"}
                            # Preserve original score before enhancement
                            original_score = ev.score
                            content = tool.contents(ev.url, **call_params)
                            # Normalize various return shapes (list[Evidence] | Evidence)
                            snippet_val = None
                            if isinstance(content, list) and content:
                                first = content[0]
                                snippet_val = getattr(first, "snippet", None)
                            elif isinstance(content, Evidence):
                                snippet_val = content.snippet
                            if snippet_val:
                                ev.snippet = snippet_val
                            # Restore original search relevance score
                            if original_score is not None:
                                ev.score = original_score
                            fetched.append(ev)
                        results = fetched
                    elif name.startswith("exa_find_similar"):
                        seed = last_results[0].url if last_results else ""
                        if seed:
                            tool = get_tool("exa")
                            results = tool.find_similar(seed, **step.get("params", {}))
                        else:
                            results = []
                    elif name.startswith("exa_answer"):
                        query_t = task_queries.get("exa_answer", "{{topic}}")
                        query = _render_template(query_t, variables)
                        tool = get_tool("exa")
                        answer_text = tool.answer(query, **step.get("params", {}))
                        results = [
                            Evidence(
                                url="exa_answer",
                                title="Exa Answer",
                                snippet=answer_text,
                                tool="exa",
                            )
                        ]
                    else:
                        results = []
                except Exception as exc:  # pragma: no cover - network errors mocked in tests
                    _log_step_error(step_label, exc)
                    results = []

                _record_evidence(results, task_evidence)
                last_results = _as_evidence_list(results)

                remaining = research_steps[idx + 1 :]
                allowed_keys = [
                    key
                    for key in (
                        _step_query_key(s.get("name", ""))
                        for s in remaining
                    )
                    if key
                ]
                if last_results and allowed_keys:
                    suggestions = _refine_queries_with_llm(
                        last_results,
                        allowed_keys,
                        max_llm_queries,
                        state.strategy_slug,
                    )
                    if suggestions:
                        task_queries.update(suggestions)
                        base_queries.update(suggestions)
                continue

            # Extended provider.method routing ---------------------------------------
            overrides = get_step_call_overrides(state.strategy_slug, use)
            foreach_expr = step.get("foreach")
            try:
                if foreach_expr:
                    items = eval_list_expr(
                        foreach_expr,
                        {**variables, **state.vars, "last_results": last_results},
                    ) or []
                    step_outputs: List[Any] = []
                    collected: List[Evidence] = []
                    for item in items:
                        render_context = {
                            **variables,
                            **state.vars,
                            "item": item,
                            "last_results": last_results,
                        }
                        inputs = _resolve_step_inputs(
                            step.get("inputs", {}),
                            render_context,
                            state.vars,
                            overrides=overrides,
                        )
                        # Log generic tool call
                        try:
                            provider, method = use.split(".", 1)
                        except Exception:
                            provider, method = use, "call"
                        result = _execute_use(use, inputs)
                        step_outputs.append(result)
                        _record_evidence(result, task_evidence)
                        collected.extend(_as_evidence_list(result))
                    if step.get("save_as"):
                        state.vars[step["save_as"]] = step_outputs
                    if collected:
                        last_results = collected
                    continue

                render_context = {**variables, **state.vars, "last_results": last_results}
                inputs = _resolve_step_inputs(
                    step.get("inputs", {}),
                    render_context,
                    state.vars,
                    overrides=overrides,
                )
                try:
                    provider, method = use.split(".", 1)
                except Exception:
                    provider, method = use, "call"
                results = _execute_use(use, inputs)
            except Exception as exc:  # pragma: no cover - defensive
                _log_step_error(step_label, exc)
                results = []

            _record_evidence(results, task_evidence)
            if step.get("save_as"):
                state.vars[step["save_as"]] = results
            new_results = _as_evidence_list(results)
            if new_results:
                last_results = new_results

        # End for over research steps

        processed = _dedupe_and_score(task_evidence, max_results)
        aggregated_evidence.extend(processed)

    # Aggregate across topics (if any), then dedupe and apply budget once
    state.evidence.extend(aggregated_evidence)
    state.evidence = _dedupe_and_score(state.evidence, max_results)
    logger.info(f"✅ RESEARCH: Complete - Collected {len(state.evidence)} unique evidence items")
    return state


def fill(state: State) -> State:
    """Fill phase: ask an LLM to provide values for whitelisted inputs per step.

    Minimal implementation: creates a runtime plan and stores under state.vars["runtime_plan"].
    Skips if no llm_fill present or no API key; keeps architecture working even without fills.
    """
    logger.info(f"📝 FILL: Starting fill phase")

    if not state.strategy_slug:
        logger.warning(f"⚠️ FILL: No strategy selected, skipping")
        return state
    try:
        strategy = load_strategy(state.strategy_slug)
    except Exception as e:
        logger.error(f"❌ FILL: Failed to load strategy: {e}")
        return state

    # Calculate dates based on time window to make them available to the LLM
    from datetime import datetime
    from core.utils import parse_date_range, format_date_for_query
    
    current_date = datetime.now()
    if state.time_window:
        start_date, end_date = parse_date_range(state.time_window, current_date)
    else:
        # Default to last 24 hours
        start_date, end_date = parse_date_range("last 24 hours", current_date)
    
    # Store dates in state.vars for use throughout the pipeline
    state.vars["current_date"] = format_date_for_query(current_date, "natural")
    state.vars["start_date"] = format_date_for_query(start_date, "iso")
    state.vars["end_date"] = format_date_for_query(end_date, "iso")
    state.vars["start_date_natural"] = format_date_for_query(start_date, "natural")
    state.vars["end_date_natural"] = format_date_for_query(end_date, "natural")
    
    # Map time_window to Sonar's search_recency_filter
    recency_map = {
        "day": "day",
        "daily": "day",
        "last 24 hours": "day",
        "week": "week",
        "weekly": "week",
        "month": "month",
        "monthly": "month",
        "year": "year",
        "yearly": "year"
    }
    state.vars["search_recency_filter"] = recency_map.get(state.time_window.lower() if state.time_window else "day", "week")
    logger.info(f"📅 FILL: Date range: {state.vars.get('start_date')} to {state.vars.get('end_date')}")

    runtime_plan: List[Dict[str, Any]] = []

    # Collect ALL steps that need LLM fill
    fill_requests = []
    for step in strategy.tool_chain:
        if step.use and step.llm_fill:
            fill_requests.append({
                "step_name": step.name or f"{step.use}",
                "description": step.description or f"Fill inputs for {step.use}",
                "keys": list(step.llm_fill),
            })

    # Make ONE batched LLM call for all steps
    batch_results = {}
    if fill_requests:
        try:
            from openai import OpenAI
            import os
            import json

            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                client = OpenAI(api_key=api_key)

                # Build prompt with all steps
                prompt = "Fill inputs for these research steps. Return JSON object with structure: {step_name: {key: value, ...}}.\n\nSteps:\n"
                for req in fill_requests:
                    prompt += f"- {req['step_name']}: Fill keys {req['keys']} for: {req['description']}\n"

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                batch_results = json.loads(content)
                logger.info(f"✅ FILL: Batched LLM fill for {len(fill_requests)} steps")
        except Exception as e:
            logger.warning(f"⚠️ FILL: Batch LLM fill failed: {e}")

    # Build runtime plan with filled values
    for step in strategy.tool_chain:
        entry: Dict[str, Any] = {
            "use": step.use,
            "name": step.name,
            "inputs": dict(step.inputs) if step.inputs else {},
            "llm_fill": list(step.llm_fill) if step.llm_fill else [],
            "save_as": step.save_as,
            "foreach": step.foreach,
            "when": step.when,
            "phase": step.phase or "research",
            "description": step.description,
        }

        # Apply batched fill results
        step_name = step.name or f"{step.use}"
        if step_name in batch_results and isinstance(batch_results[step_name], dict):
            for k, v in batch_results[step_name].items():
                if k in step.llm_fill:
                    entry["inputs"][k] = str(v) if not isinstance(v, str) else v

        runtime_plan.append(entry)

    state.vars["runtime_plan"] = runtime_plan
    logger.info(f"✅ FILL: Created runtime plan with {len(runtime_plan)} steps")
    return state


def finalize(state: State) -> State:
    """ReAct-style finalize node that can call tools then write report sections."""
    # Check if we should use ReAct mode based on strategy
    if not state.strategy_slug:
        return state
    
    strategy = load_strategy(state.strategy_slug)
    finalize_config = getattr(strategy, 'finalize', None) or {}
    
    # If reactive mode is enabled, use ReAct approach
    if finalize_config.get("reactive"):
        return _finalize_reactive(state, strategy, finalize_config)
    
    # Otherwise, fall back to original behavior
    runtime_plan: List[Dict[str, Any]] = state.vars.get("runtime_plan", [])  # type: ignore
    if not runtime_plan:
        return state

    register_default_adapters(silent=True)

    # Get evidence limit from strategy configuration
    strategy = load_strategy(state.strategy_slug)
    evidence_limit = strategy.limits.get("max_results") if strategy.limits else 100

    steps = [s for s in runtime_plan if (s.get("phase") or "research") == "finalize"]
    if not steps:
        return state

    # Format evidence as text for LLM consumption
    evidence_text = []
    evidence_full_text = []  # Full snippets for LLM analysis
    for i, ev in enumerate(state.evidence[:evidence_limit], 1):
        text = f"{i}. "
        full_text = f"{i}. "
        if ev.title:
            text += f"{ev.title} "
            full_text += f"{ev.title} "
        if ev.snippet:
            text += f"- {ev.snippet[:500]} "
            # For full text, include the entire snippet
            full_text += f"- {ev.snippet} "
        # Add date before URL for better formatting
        if ev.date:
            text += f"({ev.date}) "
            full_text += f"({ev.date}) "
        elif ev.publisher:
            text += f"({ev.publisher}) "
            full_text += f"({ev.publisher}) "
        if ev.url:
            text += f"[{ev.url}]"
            full_text += f"[{ev.url}]"
        evidence_text.append(text)
        evidence_full_text.append(full_text)
    
    variables: Dict[str, Any] = {
        "topic": state.tasks[0] if state.tasks else "",
        "time_window": state.time_window or "",
        "evidence": state.evidence,  # Keep original for compatibility
        "evidence_text": "\n".join(evidence_text),  # Formatted text for display
        "evidence_full_text": "\n".join(evidence_full_text),  # Full text for LLM analysis
        "evidence_count": len(state.evidence),
        "current_date": state.vars.get("current_date", ""),
        "start_date": state.vars.get("start_date", ""),
        "end_date": state.vars.get("end_date", ""),
    }
    variables.update(state.vars)

    task_evidence: List[Evidence] = []
    for sdict in steps:
        if sdict.get("when") and not _eval_when(sdict["when"], state):
            continue
        foreach = sdict.get("foreach")
        if foreach:
            items = eval_list_expr(foreach, {**variables, **state.vars}) or []
            step_results: List[Any] = []
            for item in items:
                call_vars = {**variables, **state.vars, "item": item}
                inputs = render_inputs(sdict.get("inputs", {}), call_vars)
                overrides = get_step_call_overrides(state.strategy_slug, sdict.get("use", ""))
                if overrides:
                    inputs.update(overrides)
                results = _execute_use(sdict.get("use", ""), inputs)
                _maybe_add_evidence(results, task_evidence)
                step_results.append(results)
            if sdict.get("save_as"):
                state.vars[sdict["save_as"]] = step_results
            continue
        inputs = render_inputs(sdict.get("inputs", {}), {**variables, **state.vars})
        overrides = get_step_call_overrides(state.strategy_slug, sdict.get("use", ""))
        if overrides:
            inputs.update(overrides)
        results = _execute_use(sdict.get("use", ""), inputs)
        
        # Only add to evidence if NOT saving to vars (avoid duplication)
        if sdict.get("save_as"):
            state.vars[sdict["save_as"]] = results
        else:
            _maybe_add_evidence(results, task_evidence)

    # Merge evidence
    state.evidence.extend(_dedupe_and_score(task_evidence, None))
    return state


def _finalize_reactive(state: State, strategy: Any, finalize_config: Dict[str, Any]) -> State:
    """ReAct implementation of finalize - can call tools then write report."""
    register_default_adapters(silent=True)

    # Get evidence limit from strategy configuration
    evidence_limit = strategy.limits.get("max_results") if strategy.limits else 100

    def format_evidence_lines(
        items: List[Evidence],
        limit: int = 50,
        skip_urls: Optional[set[str]] = None,
    ) -> List[str]:
        lines: List[str] = []
        for i, ev in enumerate(items[:limit], 1):
            text = f"{i}. "
            if ev.title:
                text += f"{ev.title} "
            if ev.snippet:
                text += f"- {ev.snippet[:500]}... "
            if ev.date:
                text += f"({ev.date}) "
            elif ev.publisher:
                text += f"({ev.publisher}) "
            if ev.url and (not skip_urls or ev.url not in skip_urls):
                text += f"[{ev.url}]"
            lines.append(text)
        return lines

    node_cfg = get_node_llm_config("finalize_react", state.strategy_slug)
    model = node_cfg.get("model", "gpt-4o-mini")
    call_kwargs = {k: v for k, v in node_cfg.items() if k != "model"}
    if model == "gpt-5-mini":
        call_kwargs.pop("temperature", None)

    evidence_lines = format_evidence_lines(state.evidence, limit=evidence_limit)
    instructions = finalize_config.get("instructions", "")
    # Prefer topic provided by scope/fill, then first task, then user request
    topic_guess = (
        state.vars.get("topic")
        or (state.tasks[0] if state.tasks else None)
        or state.user_request
        or ""
    )
    if not isinstance(topic_guess, str):
        topic_guess = str(topic_guess)
    instructions = instructions.replace("{{topic}}", topic_guess)

    system_prompt = _prompt_text(
        get_node_prompt("finalize_react_system", state.strategy_slug),
        DEFAULT_FINALIZE_SYSTEM_PROMPT,
    )
    analysis_template = _prompt_text(
        get_node_prompt("finalize_react_analysis", state.strategy_slug),
        DEFAULT_FINALIZE_ANALYSIS_TEMPLATE,
    )
    analysis_prompt = _format_prompt(
        analysis_template,
        evidence_count=len(state.evidence),
        evidence_text="\n".join(evidence_lines),
        topic=topic_guess,
        time_window=state.time_window or "recent",
        current_date=state.vars.get("current_date", ""),
        instructions=instructions,
    )

    tools_payload = [
        {
            "type": "function",
            "function": {
                "name": "exa_answer",
                "description": "Get a direct answer to a question",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The question to answer"}
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "exa_search",
                "description": "Search for information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {"type": "integer", "default": 5},
                        "search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "sonar_call",
                "description": "Get an AI response with web search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "The prompt/question"},
                        "search_mode": {"type": "string", "enum": ["web", "academic"], "default": "web"},
                        "search_recency_filter": {"type": "string", "enum": ["day", "week", "month", "year"]},
                    },
                    "required": ["prompt"],
                },
            },
        },
    ]

    try:
        from openai import OpenAI
        client = OpenAI()
        lf_client = get_langfuse_client()

        if lf_client:
            lf_client.update_current_generation(
                model=model,
                input={
                    "analysis_prompt": analysis_prompt,
                    "instructions": instructions,
                    "topic": topic_guess,
                },
                metadata={"component": "finalize_react_analysis"},
            )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt},
            ],
            tools=tools_payload,
            tool_choice="auto",
            **call_kwargs,
        )

        message = response.choices[0].message
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
                output=getattr(message, "content", None),
                usage_details=usage_details,
            )

        # Handle tool calls if any (enforce at most one tool call)
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # Execute only the first tool call
            try:
                if function_name == "exa_answer":
                    tool = get_tool("exa")
                    result = tool.answer(arguments["query"])
                    # Add result as evidence
                    state.evidence.append(Evidence(
                        url="exa_answer_verification",
                        title="Additional Information",
                        snippet=result,
                        tool="exa",
                        date=state.vars.get('current_date', '')
                    ))

                elif function_name == "exa_search":
                    tool = get_tool("exa")
                    params = {k: v for k, v in arguments.items() if k != "query"}
                    results = tool.search(arguments["query"], **params)
                    state.evidence.extend(results)

                elif function_name == "sonar_call":
                    tool = get_tool("sonar")
                    params = {k: v for k, v in arguments.items() if k != "prompt"}
                    results = tool.call(arguments["prompt"], **params)
                    state.evidence.extend(results)
            except Exception:
                # Log but don't fail
                pass
            
            # Dedupe evidence after tool call and before writing
            try:
                state.evidence = _dedupe_and_score(state.evidence, None)
            except Exception:
                pass

            # Now get the report with enhanced evidence
            updated_lines = format_evidence_lines(
                state.evidence,
                limit=evidence_limit,
                skip_urls={"exa_answer_verification"},
            )

            sections_part = ""
            if "Then write these sections:" in instructions:
                sections_part = instructions.split("Then write these sections:")[1].strip()
            elif "sections:" in instructions.lower():
                sections_part = instructions.split("sections:")[1].strip()

            sections_prompt = sections_part or "Write a comprehensive report with appropriate sections"
            writer_template = _prompt_text(
                get_node_prompt("finalize_react_writer", state.strategy_slug),
                DEFAULT_FINALIZE_WRITER_TEMPLATE,
            )
            writer_prompt = _format_prompt(
                writer_template,
                evidence_count=len(state.evidence),
                evidence_text="\n".join(updated_lines),
                sections_prompt=sections_prompt,
            )

            if lf_client:
                lf_client.update_current_generation(
                    model=model,
                    input={"writer_prompt": writer_prompt},
                    metadata={"component": "finalize_react_writer"},
                )

            final_response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": writer_prompt},
                ],
                **call_kwargs,
            )

            report_content = final_response.choices[0].message.content

            # DEBUG: Log report before parsing
            logger.info(f"📄 FINALIZE: Generated report ({len(report_content)} chars)")
            logger.info(f"Preview: {report_content[:500]}...")

            if lf_client:
                usage = getattr(final_response, "usage", None)
                usage_details = None
                if usage:
                    usage_details = {
                        "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                        "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                    }
                lf_client.update_current_generation(
                    output=report_content,
                    usage_details=usage_details,
                )
        else:
            # No tools needed, extract report from initial message
            report_content = message.content
            # If the response includes thinking, extract just the report part
            if "## " in report_content:
                # Find where the actual report sections start
                report_start = report_content.find("## ")
                if report_start > 0:
                    report_content = report_content[report_start:]
        
        # Try to extract citations from a '## Sources' section
        try:
            # Prefer explicit markdown header; fallback to any 'sources' marker
            src_idx = report_content.lower().find("## sources")
            if src_idx == -1:
                src_idx = report_content.lower().find("\nsources\n")
            if src_idx == -1:
                src_idx = report_content.lower().find("\n## sources")
            if src_idx != -1:
                sources_block = report_content[src_idx:]
                lines = sources_block.splitlines()
                # drop the header line
                if lines and lines[0].strip().lower().startswith("## sources"):
                    lines = lines[1:]
                elif lines and lines[0].strip().lower() == "sources":
                    lines = lines[1:]
                parsed: List[str] = []
                for ln in lines:
                    s = ln.strip()
                    if not s:
                        continue
                    if s.startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.", "[", "(") ) or ":" in s:
                        parsed.append(s)
                if parsed:
                    # Merge uniquely with existing citations
                    existing = set(state.citations)
                    for c in parsed:
                        if c not in existing:
                            state.citations.append(c)
                            existing.add(c)
        except Exception:
            pass

        # Parse sections from the report
        if "## " in report_content:
            # Split by ## but keep the headers
            parts = report_content.split("## ")
            for part in parts[1:]:  # Skip the first empty part
                if part.strip():
                    state.sections.append(f"## {part.strip()}")
        else:
            # If no sections found, add as single section
            state.sections.append(report_content)

        # DEDUPLICATION: Remove duplicate sections
        if len(state.sections) > 1:
            unique_sections = []
            seen = set()

            for section in state.sections:
                # Use first 200 chars as fingerprint
                fingerprint = section[:200].strip()
                if fingerprint not in seen:
                    unique_sections.append(section)
                    seen.add(fingerprint)
                else:
                    logger.warning(f"⚠️ FINALIZE: Removed duplicate section")

            if len(unique_sections) != len(state.sections):
                logger.info(f"📝 FINALIZE: Deduplication: {len(state.sections)} → {len(unique_sections)} sections")
                state.sections = unique_sections

        # DEBUG: Log parsed sections
        logger.info(f"📝 FINALIZE: Parsed into {len(state.sections)} sections:")
        for i, section in enumerate(state.sections):
            preview = section[:150].replace('\n', ' ')
            logger.info(f"  Section {i+1}: {len(section)} chars - {preview}...")

    except Exception as e:
        # Fallback to original behavior if ReAct fails
        import traceback
        traceback.print_exc()
        return state

    return state


def _execute_use(use: str, inputs: Dict[str, Any]) -> Any:
    """Execute a routed adapter method use=provider.method with inputs."""
    import time
    try:
        provider, method = use.split(".", 1)
    except ValueError:
        logger.error("Invalid use specification '%s'", use)
        return []
    try:
        adapter = get_tool(provider)
    except Exception as exc:
        logger.exception("Adapter '%s' not registered", provider, exc_info=exc)
        return []
    fn = getattr(adapter, method, None)
    if fn is None:
        # try snake_case conversion from camelCase
        snake = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), method)
        fn = getattr(adapter, snake, None)
    if fn is None:
        # default to call
        fn = getattr(adapter, "call", None)
    if fn is None:
        logger.error("Adapter '%s' has no callable for method '%s'", provider, method)
        return []
    try:
        start_time = time.time()
        result = fn(**inputs) if isinstance(inputs, dict) else fn(inputs)
        duration = time.time() - start_time

        try:
            evs = _as_evidence_list(result)
            logger.info(f"🔧 {provider}.{method}: Returned {len(evs)} results in {duration:.2f}s")
        except Exception:
            pass
        return result
    except TypeError as exc:
        logger.debug("Attempting positional fallback for %s due to TypeError: %s", use, exc)
        # Try positional fallback
        try:
            return fn(*inputs.values())  # type: ignore[arg-type]
        except Exception as inner_exc:
            logger.exception("Failed fallback invocation for %s", use, exc_info=inner_exc)
            return []
    except Exception as exc:
        logger.exception("Error executing use '%s'", use, exc_info=exc)
        return []


def _maybe_add_evidence(results: Any, bucket: List[Evidence]) -> None:
    if isinstance(results, Evidence):
        bucket.append(results)
    elif isinstance(results, list) and results and isinstance(results[0], Evidence):
        bucket.extend(results)  # type: ignore[arg-type]


def _eval_when(expr: str, state: State) -> bool:
    """Very small evaluator for `when` predicates.

    Supports patterns like "unique_sources < 3" or truthiness of a saved var.
    """
    expr = expr.strip()
    unique_sources = len({ev.url for ev in state.evidence}) if state.evidence else 0
    context: Dict[str, Any] = {**state.vars, "unique_sources": unique_sources}

    # Simple comparator: var < N  | var > N | var == N
    m = re.match(r"^(\w+)\s*(==|<=|>=|<|>)\s*(\d+)$", expr)
    if m:
        key, op, num_s = m.group(1), m.group(2), m.group(3)
        left = context.get(key, 0)
        try:
            right = int(num_s)
        except Exception:
            return False
        try:
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
            if op == "==":
                return left == right
        except Exception:
            return False
        return False

    # Fallback: truthiness of a saved variable name
    return bool(context.get(expr))


@observe(as_type="generation", name="fill-llm")
def _llm_fill_inputs_simple(description: str, allowed: Dict[str, Any], model: str | None = None, base_instructions: str | None = None) -> Dict[str, str]:
    """Ask an LLM to fill a few strings. Minimal, best-effort implementation.

    Returns an empty dict when API key or client is unavailable.
    """
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return {}
    import os
    import time
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {}
    client = OpenAI(api_key=api_key)
    lf_client = get_langfuse_client()
    instructions = (
        (base_instructions or "Fill the following JSON keys with concise values (strings or small lists). Only include the provided keys; no extras.")
        + "\n"
        + f"Keys: {list(allowed.keys())}\n"
        + f"Task: {description or 'fill search query parameters'}\n"
        + "Respond as a JSON object."
    )
    if lf_client:
        lf_client.update_current_generation(
            model=model or "gpt-4o-mini",
            input={"allowed_keys": list(allowed.keys()), "description": description},
            metadata={"component": "fill_llm"},
        )
    try:
        start_time = time.time()
        messages = [{"role": "user", "content": instructions}]
        resp = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=messages,
        )
        choice = resp["choices"][0] if isinstance(resp, dict) else resp.choices[0]
        message = choice["message"] if isinstance(choice, dict) else choice.message
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", "{}")
        )
        if lf_client:
            usage = getattr(resp, "usage", None)
            usage_details = None
            if usage:
                usage_details = {
                    "input_tokens": getattr(usage, "prompt_tokens", None) or getattr(usage, "promptTokens", None),
                    "output_tokens": getattr(usage, "completion_tokens", None) or getattr(usage, "completionTokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None) or getattr(usage, "totalTokens", None),
                }
            lf_client.update_current_generation(
                output=content,
                usage_details=usage_details,
            )
        import json as _json

        data = _json.loads(content)
        if isinstance(data, dict):
            return {k: str(v) if not isinstance(v, str) else v for k, v in data.items() if k in allowed}
    except Exception:
        return {}
    return {}


def build_graph() -> StateGraph:
    """Construct the LangGraph workflow."""
    builder = StateGraph(State)
    builder.add_node("scope", scope)
    builder.add_node("fill", fill)
    builder.add_node("research", research)
    builder.add_node("finalize", finalize)

    builder.set_entry_point("scope")
    builder.add_edge("scope", "fill")
    builder.add_edge("fill", "research")
    builder.add_edge("research", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=MemorySaver())

