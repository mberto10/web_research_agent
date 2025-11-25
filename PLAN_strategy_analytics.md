# Implementation Plan: Langfuse Scores for Strategy Analytics

## Overview

Add strategy-level performance metrics tracking using Langfuse Scores API. This enables:
- Monitoring strategy performance over time
- Comparing strategies by quality metrics
- Identifying regressions in evidence quality
- Tracking cost/token usage per strategy

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Execution Flow                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  workflow_span() ──┬── scope() ──► MetricsCollector.scope_done()│
│       │            │                                            │
│       │            ├── fill() ──► MetricsCollector.fill_done()  │
│       │            │                                            │
│       │            ├── research() ──► MetricsCollector.research_done()
│       │            │                                            │
│       │            └── finalize() ──► MetricsCollector.finalize_done()
│       │                                                         │
│       └── record_strategy_scores() ◄── MetricsCollector.build() │
│                        │                                        │
│                        ▼                                        │
│              Langfuse Scores API                                │
│              - evidence_count                                   │
│              - source_diversity                                 │
│              - execution_time_ms                                │
│              - token_usage                                      │
│              - api_calls                                        │
└─────────────────────────────────────────────────────────────────┘
```

## Files to Create/Modify

### 1. NEW: `core/analytics.py`
Strategy metrics collection and Langfuse score recording.

### 2. MODIFY: `core/graph.py`
Integrate MetricsCollector into graph phases.

### 3. MODIFY: `core/langfuse_tracing.py`
Add helper to get current trace ID.

### 4. MODIFY: `run_daily_briefing.py`
Record scores at end of workflow.

---

## Detailed Implementation

### Step 1: Create `core/analytics.py`

```python
"""Strategy-level analytics using Langfuse scores."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class PhaseMetrics:
    """Metrics for a single execution phase."""
    start_time: float = 0.0
    end_time: float = 0.0
    token_usage: int = 0
    api_calls: Dict[str, int] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0


@dataclass
class StrategyMetrics:
    """Aggregated metrics for a strategy execution."""
    strategy_slug: str
    trace_id: Optional[str] = None

    # Phase timing
    scope: PhaseMetrics = field(default_factory=PhaseMetrics)
    fill: PhaseMetrics = field(default_factory=PhaseMetrics)
    research: PhaseMetrics = field(default_factory=PhaseMetrics)
    finalize: PhaseMetrics = field(default_factory=PhaseMetrics)

    # Evidence metrics
    evidence_count: int = 0
    unique_domains: int = 0
    unique_publishers: int = 0
    tools_used: List[str] = field(default_factory=list)

    # Quality scores (0-1)
    source_diversity_score: float = 0.0

    # Output metrics
    sections_count: int = 0
    citations_count: int = 0

    @property
    def total_duration_ms(self) -> float:
        return (
            self.scope.duration_ms +
            self.fill.duration_ms +
            self.research.duration_ms +
            self.finalize.duration_ms
        )

    @property
    def total_tokens(self) -> int:
        return (
            self.scope.token_usage +
            self.fill.token_usage +
            self.research.token_usage +
            self.finalize.token_usage
        )

    @property
    def total_api_calls(self) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for phase in [self.scope, self.fill, self.research, self.finalize]:
            for tool, count in phase.api_calls.items():
                merged[tool] = merged.get(tool, 0) + count
        return merged


class MetricsCollector:
    """Collects metrics during strategy execution.

    Usage:
        collector = MetricsCollector(strategy_slug="daily_news_briefing")

        collector.start_phase("scope")
        # ... scope execution ...
        collector.end_phase("scope", token_usage=150)

        collector.start_phase("research")
        collector.record_api_call("sonar")
        collector.record_api_call("exa")
        # ... research execution ...
        collector.end_phase("research", token_usage=500)

        metrics = collector.build(state)
        record_strategy_scores(trace_id, metrics)
    """

    def __init__(self, strategy_slug: str):
        self.strategy_slug = strategy_slug
        self._metrics = StrategyMetrics(strategy_slug=strategy_slug)
        self._current_phase: Optional[str] = None

    def start_phase(self, phase: str) -> None:
        """Mark the start of a phase."""
        phase_metrics = getattr(self._metrics, phase, None)
        if phase_metrics:
            phase_metrics.start_time = time.time()
            self._current_phase = phase

    def end_phase(self, phase: str, token_usage: int = 0) -> None:
        """Mark the end of a phase with optional token count."""
        phase_metrics = getattr(self._metrics, phase, None)
        if phase_metrics:
            phase_metrics.end_time = time.time()
            phase_metrics.token_usage = token_usage
        self._current_phase = None

    def record_api_call(self, tool_name: str, phase: Optional[str] = None) -> None:
        """Record an API call to a tool."""
        target_phase = phase or self._current_phase
        if target_phase:
            phase_metrics = getattr(self._metrics, target_phase, None)
            if phase_metrics:
                phase_metrics.api_calls[tool_name] = phase_metrics.api_calls.get(tool_name, 0) + 1

    def set_trace_id(self, trace_id: str) -> None:
        """Set the Langfuse trace ID."""
        self._metrics.trace_id = trace_id

    def build(self, state: Any) -> StrategyMetrics:
        """Build final metrics from execution state."""
        evidence = getattr(state, 'evidence', []) or []
        sections = getattr(state, 'sections', []) or []
        citations = getattr(state, 'citations', []) or []

        # Evidence metrics
        self._metrics.evidence_count = len(evidence)
        self._metrics.sections_count = len(sections)
        self._metrics.citations_count = len(citations)

        # Compute unique domains
        domains = set()
        publishers = set()
        tools = set()
        for ev in evidence:
            url = getattr(ev, 'url', '') or ''
            if url:
                try:
                    domains.add(urlparse(url).netloc)
                except Exception:
                    pass
            publisher = getattr(ev, 'publisher', None)
            if publisher:
                publishers.add(publisher)
            tool = getattr(ev, 'tool', None)
            if tool:
                tools.add(tool)

        self._metrics.unique_domains = len(domains)
        self._metrics.unique_publishers = len(publishers)
        self._metrics.tools_used = list(tools)

        # Compute diversity score
        self._metrics.source_diversity_score = compute_source_diversity(evidence)

        return self._metrics


def compute_source_diversity(evidence: List[Any]) -> float:
    """Compute diversity score based on unique domains.

    Score formula:
    - 50% weight: ratio of unique domains to total sources
    - 50% weight: absolute domain count (capped at 10 for perfect score)

    Returns: 0.0 to 1.0
    """
    if not evidence:
        return 0.0

    domains = set()
    for ev in evidence:
        url = getattr(ev, 'url', '') or ''
        if url and url not in ('llm_analysis_result', 'exa_answer'):
            try:
                netloc = urlparse(url).netloc
                if netloc:
                    domains.add(netloc)
            except Exception:
                pass

    unique_domains = len(domains)
    total_sources = len([e for e in evidence if getattr(e, 'url', '') not in ('llm_analysis_result', 'exa_answer')])

    if total_sources == 0:
        return 0.0

    # Ratio score: how unique are the sources?
    ratio_score = unique_domains / total_sources

    # Count score: do we have enough diversity? (10+ domains = perfect)
    count_score = min(unique_domains / 10, 1.0)

    return (ratio_score * 0.5) + (count_score * 0.5)


def record_strategy_scores(trace_id: str, metrics: StrategyMetrics) -> bool:
    """Record strategy metrics as Langfuse scores.

    Args:
        trace_id: Langfuse trace ID
        metrics: Collected strategy metrics

    Returns:
        True if scores recorded successfully
    """
    from core.langfuse_tracing import get_langfuse_client

    client = get_langfuse_client()
    if not client:
        logger.debug("Langfuse disabled, skipping metrics recording")
        return False

    if not trace_id:
        logger.warning("No trace_id provided, skipping metrics recording")
        return False

    try:
        # Define scores to record
        numeric_scores = [
            # Evidence metrics
            ("evidence_count", metrics.evidence_count, "Number of evidence items collected"),
            ("unique_domains", metrics.unique_domains, "Number of unique source domains"),
            ("unique_publishers", metrics.unique_publishers, "Number of unique publishers"),
            ("source_diversity", round(metrics.source_diversity_score, 3), "Source diversity score (0-1)"),

            # Timing metrics
            ("total_duration_ms", round(metrics.total_duration_ms, 1), "Total execution time in ms"),
            ("scope_duration_ms", round(metrics.scope.duration_ms, 1), "Scope phase duration"),
            ("fill_duration_ms", round(metrics.fill.duration_ms, 1), "Fill phase duration"),
            ("research_duration_ms", round(metrics.research.duration_ms, 1), "Research phase duration"),
            ("finalize_duration_ms", round(metrics.finalize.duration_ms, 1), "Finalize phase duration"),

            # Token metrics
            ("total_tokens", metrics.total_tokens, "Total LLM tokens used"),

            # Output metrics
            ("sections_count", metrics.sections_count, "Number of report sections"),
            ("citations_count", metrics.citations_count, "Number of citations"),
        ]

        # Record numeric scores
        for name, value, comment in numeric_scores:
            try:
                client.score(
                    trace_id=trace_id,
                    name=name,
                    value=float(value),
                    comment=comment,
                )
            except Exception as e:
                logger.warning(f"Failed to record score {name}: {e}")

        # Record categorical scores
        categorical_scores = [
            ("strategy_slug", metrics.strategy_slug, "Strategy used for execution"),
            ("tools_used", ",".join(sorted(metrics.tools_used)), "Tools used during research"),
        ]

        for name, value, comment in categorical_scores:
            try:
                client.score(
                    trace_id=trace_id,
                    name=name,
                    value=value,
                    comment=comment,
                )
            except Exception as e:
                logger.warning(f"Failed to record categorical score {name}: {e}")

        # Record API call counts as individual scores
        for tool, count in metrics.total_api_calls.items():
            try:
                client.score(
                    trace_id=trace_id,
                    name=f"api_calls_{tool}",
                    value=float(count),
                    comment=f"Number of {tool} API calls",
                )
            except Exception as e:
                logger.warning(f"Failed to record api_calls_{tool}: {e}")

        logger.info(
            f"📊 Recorded {len(numeric_scores) + len(categorical_scores)} metrics "
            f"for strategy '{metrics.strategy_slug}' (trace: {trace_id[:12]}...)"
        )
        return True

    except Exception as e:
        logger.exception(f"Failed to record strategy scores: {e}")
        return False


# Global collector instance (set per-request)
_current_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> Optional[MetricsCollector]:
    """Get the current metrics collector."""
    return _current_collector


def set_metrics_collector(collector: Optional[MetricsCollector]) -> None:
    """Set the current metrics collector."""
    global _current_collector
    _current_collector = collector
```

### Step 2: Modify `core/langfuse_tracing.py`

Add helper to extract trace ID from current context:

```python
# Add to langfuse_tracing.py

def get_current_trace_id() -> Optional[str]:
    """Get the trace ID from the current Langfuse context.

    Returns:
        Trace ID string or None if not in a traced context
    """
    client = get_langfuse_client()
    if not client:
        return None

    try:
        # Try to get current observation/span
        if hasattr(client, 'get_current_observation_id'):
            obs_id = client.get_current_observation_id()
            if obs_id:
                # Observation ID format: trace_id-observation_id or just trace_id
                return obs_id.split('-')[0] if '-' in obs_id else obs_id

        # Alternative: check if we're in a span context
        if hasattr(client, 'get_current_trace_id'):
            return client.get_current_trace_id()

    except Exception:
        pass

    return None
```

Also modify `WorkflowContext` to expose trace ID:

```python
@dataclass
class WorkflowContext:
    """Encapsulates workflow-level span and callback state."""

    span: Any
    handler: Any
    client: Any

    @property
    def trace_id(self) -> Optional[str]:
        """Get the trace ID for this workflow."""
        if self.span and hasattr(self.span, 'trace_id'):
            return self.span.trace_id
        return None

    # ... rest of existing methods ...
```

### Step 3: Integrate into `core/graph.py`

Add metrics collection hooks to each phase:

```python
# At top of graph.py, add import:
from core.analytics import get_metrics_collector

# In scope() function, after determining strategy:
def scope(state: State) -> State:
    collector = get_metrics_collector()
    if collector:
        collector.start_phase("scope")

    # ... existing scope logic ...

    if collector:
        collector.end_phase("scope", token_usage=_get_last_token_usage())

    return state


# In fill() function:
def fill(state: State) -> State:
    collector = get_metrics_collector()
    if collector:
        collector.start_phase("fill")

    # ... existing fill logic ...

    if collector:
        collector.end_phase("fill", token_usage=_get_last_token_usage())

    return state


# In research() function:
def research(state: State) -> State:
    collector = get_metrics_collector()
    if collector:
        collector.start_phase("research")

    # ... existing research logic ...

    # After each tool call, record it:
    # collector.record_api_call("sonar")  # etc.

    if collector:
        collector.end_phase("research", token_usage=_get_last_token_usage())

    return state


# In finalize() function:
def finalize(state: State) -> State:
    collector = get_metrics_collector()
    if collector:
        collector.start_phase("finalize")

    # ... existing finalize logic ...

    if collector:
        collector.end_phase("finalize", token_usage=_get_last_token_usage())

    return state
```

### Step 4: Integrate into `run_daily_briefing.py`

```python
# Add imports at top:
from core.analytics import (
    MetricsCollector,
    set_metrics_collector,
    record_strategy_scores,
)

# In run_briefing(), before graph.invoke():
def run_briefing(...):
    # ... existing setup ...

    with workflow_span(...) as tracing:
        # ... existing setup ...

        # Initialize metrics collector
        collector = MetricsCollector(strategy_slug=state.strategy_slug or "unknown")
        set_metrics_collector(collector)

        # Set trace ID if available
        if tracing.trace_id:
            collector.set_trace_id(tracing.trace_id)

        # ... existing graph.invoke() ...

        result = graph.invoke(state, invoke_config)

        # Build and record metrics
        if tracing.trace_id:
            metrics = collector.build(result)
            record_strategy_scores(tracing.trace_id, metrics)

        # Clear collector
        set_metrics_collector(None)

        # ... rest of existing code ...
```

---

## Metrics Reference

### Numeric Scores

| Score Name | Type | Description |
|------------|------|-------------|
| `evidence_count` | int | Total evidence items collected |
| `unique_domains` | int | Unique source domains |
| `unique_publishers` | int | Unique publishers |
| `source_diversity` | float | Diversity score (0-1) |
| `total_duration_ms` | float | Total execution time |
| `scope_duration_ms` | float | Scope phase time |
| `fill_duration_ms` | float | Fill phase time |
| `research_duration_ms` | float | Research phase time |
| `finalize_duration_ms` | float | Finalize phase time |
| `total_tokens` | int | Total LLM tokens |
| `sections_count` | int | Report sections |
| `citations_count` | int | Citations extracted |
| `api_calls_{tool}` | int | Per-tool call counts |

### Categorical Scores

| Score Name | Description |
|------------|-------------|
| `strategy_slug` | Strategy identifier |
| `tools_used` | Comma-separated tool list |

---

## Querying Metrics in Langfuse

### Filter by Strategy
```
scores.strategy_slug = "daily_news_briefing"
```

### Find Low Diversity Runs
```
scores.source_diversity < 0.5
```

### Performance Analysis
```sql
-- Average metrics by strategy (via Langfuse dashboard or API)
SELECT
  scores.strategy_slug,
  AVG(scores.evidence_count) as avg_evidence,
  AVG(scores.source_diversity) as avg_diversity,
  AVG(scores.total_duration_ms) as avg_duration
GROUP BY scores.strategy_slug
```

---

## Testing Plan

1. **Unit Tests** (`tests/test_analytics.py`):
   - `test_compute_source_diversity_empty`
   - `test_compute_source_diversity_single_domain`
   - `test_compute_source_diversity_diverse`
   - `test_metrics_collector_phases`
   - `test_metrics_collector_api_calls`

2. **Integration Tests**:
   - Run `python run_daily_briefing.py --topic "Test"`
   - Verify scores appear in Langfuse dashboard
   - Check all expected scores are present

3. **Manual Verification**:
   - Compare reported metrics with actual trace data
   - Verify timing accuracy
   - Check diversity score makes sense for different runs

---

## Implementation Order

1. **Create `core/analytics.py`** - Core metrics logic
2. **Modify `core/langfuse_tracing.py`** - Add trace ID helper
3. **Modify `core/graph.py`** - Add phase hooks
4. **Modify `run_daily_briefing.py`** - Initialize and record
5. **Add tests** - Verify correctness
6. **Test end-to-end** - Verify Langfuse integration

---

## Future Enhancements

1. **Evidence Quality Scoring**: Add semantic relevance scoring
2. **Cost Tracking**: Calculate estimated API costs
3. **Alerting**: Set up alerts for regressions
4. **Dashboards**: Create Langfuse dashboard templates
5. **A/B Comparison**: Compare strategy variants
