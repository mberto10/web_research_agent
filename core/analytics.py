"""Strategy-level analytics using Langfuse scores."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
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

    def __init__(self, strategy_slug: str = "unknown"):
        self.strategy_slug = strategy_slug
        self._metrics = StrategyMetrics(strategy_slug=strategy_slug)
        self._current_phase: Optional[str] = None

    def set_strategy_slug(self, slug: str) -> None:
        """Update the strategy slug (called when determined during scope)."""
        self.strategy_slug = slug
        self._metrics.strategy_slug = slug

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

        # Compute unique domains, publishers, tools
        domains = set()
        publishers = set()
        tools = set()
        for ev in evidence:
            url = getattr(ev, 'url', '') or ''
            if url and url not in ('llm_analysis_result', 'exa_answer'):
                try:
                    netloc = urlparse(url).netloc
                    if netloc:
                        domains.add(netloc)
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
        self._metrics.tools_used = sorted(tools)

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
    valid_sources = 0
    for ev in evidence:
        url = getattr(ev, 'url', '') or ''
        # Skip synthetic URLs
        if url and url not in ('llm_analysis_result', 'exa_answer'):
            valid_sources += 1
            try:
                netloc = urlparse(url).netloc
                if netloc:
                    domains.add(netloc)
            except Exception:
                pass

    unique_domains = len(domains)

    if valid_sources == 0:
        return 0.0

    # Ratio score: how unique are the sources?
    ratio_score = unique_domains / valid_sources

    # Count score: do we have enough diversity? (10+ domains = perfect)
    count_score = min(unique_domains / 10, 1.0)

    return round((ratio_score * 0.5) + (count_score * 0.5), 3)


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
        scores_recorded = 0

        # Define numeric scores to record
        numeric_scores = [
            # Evidence metrics
            ("evidence_count", metrics.evidence_count, "Number of evidence items collected"),
            ("unique_domains", metrics.unique_domains, "Number of unique source domains"),
            ("unique_publishers", metrics.unique_publishers, "Number of unique publishers"),
            ("source_diversity", metrics.source_diversity_score, "Source diversity score (0-1)"),

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
                scores_recorded += 1
            except Exception as e:
                logger.warning(f"Failed to record score {name}: {e}")

        # Record categorical scores
        try:
            client.score(
                trace_id=trace_id,
                name="strategy_slug",
                value=metrics.strategy_slug,
                comment="Strategy used for execution",
            )
            scores_recorded += 1
        except Exception as e:
            logger.warning(f"Failed to record strategy_slug: {e}")

        if metrics.tools_used:
            try:
                client.score(
                    trace_id=trace_id,
                    name="tools_used",
                    value=",".join(metrics.tools_used),
                    comment="Tools used during research",
                )
                scores_recorded += 1
            except Exception as e:
                logger.warning(f"Failed to record tools_used: {e}")

        # Record API call counts as individual scores
        for tool, count in metrics.total_api_calls.items():
            try:
                client.score(
                    trace_id=trace_id,
                    name=f"api_calls_{tool}",
                    value=float(count),
                    comment=f"Number of {tool} API calls",
                )
                scores_recorded += 1
            except Exception as e:
                logger.warning(f"Failed to record api_calls_{tool}: {e}")

        logger.info(
            f"Recorded {scores_recorded} metrics for strategy '{metrics.strategy_slug}' "
            f"(trace: {trace_id[:12]}...)"
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


__all__ = [
    "PhaseMetrics",
    "StrategyMetrics",
    "MetricsCollector",
    "compute_source_diversity",
    "record_strategy_scores",
    "get_metrics_collector",
    "set_metrics_collector",
]
