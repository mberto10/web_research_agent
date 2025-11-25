"""Strategy-level analytics using Langfuse scores."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Call Result Tracking
# ---------------------------------------------------------------------------

@dataclass
class ToolCallResult:
    """Result of a single tool call."""
    tool_name: str
    success: bool
    evidence_count: int = 0
    error: Optional[str] = None
    duration_ms: float = 0.0


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

    # ----- NEW: Efficiency metrics -----
    evidence_before_dedup: int = 0  # Total evidence before deduplication
    redundancy_ratio: float = 0.0   # Duplicate evidence ratio (0-1, lower is better)
    cost_per_evidence: float = 0.0  # Tokens per evidence item (efficiency)

    # ----- NEW: Quality proxy metrics -----
    evidence_recency_score: float = 0.0  # % of sources within requested time window (0-1)
    query_coverage_score: float = 0.0    # How well evidence covers the tasks (0-1)
    tool_success_rate: float = 0.0       # % of tool calls that returned results (0-1)
    avg_evidence_per_tool_call: float = 0.0  # Average evidence items per successful call

    # ----- NEW: Tool call tracking -----
    tool_calls: List[ToolCallResult] = field(default_factory=list)

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
        collector.record_tool_call("sonar", success=True, evidence_count=5)
        collector.record_tool_call("exa", success=True, evidence_count=3)
        # ... research execution ...
        collector.end_phase("research", token_usage=500)

        metrics = collector.build(state)
        record_strategy_scores(trace_id, metrics)
    """

    def __init__(self, strategy_slug: str = "unknown"):
        self.strategy_slug = strategy_slug
        self._metrics = StrategyMetrics(strategy_slug=strategy_slug)
        self._current_phase: Optional[str] = None
        self._tool_call_start: Optional[float] = None
        self._evidence_before_dedup: int = 0
        self._time_window: Optional[str] = None
        self._tasks: List[str] = []

    def set_strategy_slug(self, slug: str) -> None:
        """Update the strategy slug (called when determined during scope)."""
        self.strategy_slug = slug
        self._metrics.strategy_slug = slug

    def set_time_window(self, time_window: str) -> None:
        """Set the requested time window for recency scoring."""
        self._time_window = time_window

    def set_tasks(self, tasks: List[str]) -> None:
        """Set the research tasks for coverage scoring."""
        self._tasks = tasks

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

    def start_tool_call(self) -> None:
        """Mark the start of a tool call for duration tracking."""
        self._tool_call_start = time.time()

    def record_tool_call(
        self,
        tool_name: str,
        success: bool,
        evidence_count: int = 0,
        error: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> None:
        """Record a tool call result with detailed metrics."""
        target_phase = phase or self._current_phase

        # Calculate duration if we have a start time
        duration_ms = 0.0
        if self._tool_call_start:
            duration_ms = (time.time() - self._tool_call_start) * 1000
            self._tool_call_start = None

        # Record detailed tool call result
        self._metrics.tool_calls.append(ToolCallResult(
            tool_name=tool_name,
            success=success,
            evidence_count=evidence_count,
            error=error,
            duration_ms=duration_ms,
        ))

        # Also update the legacy api_calls counter for backwards compatibility
        if target_phase:
            phase_metrics = getattr(self._metrics, target_phase, None)
            if phase_metrics:
                phase_metrics.api_calls[tool_name] = phase_metrics.api_calls.get(tool_name, 0) + 1

        # Track evidence before dedup
        if success:
            self._evidence_before_dedup += evidence_count

    def record_api_call(self, tool_name: str, phase: Optional[str] = None) -> None:
        """Record an API call to a tool (legacy method, prefer record_tool_call)."""
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
        tasks = getattr(state, 'tasks', []) or self._tasks
        time_window = getattr(state, 'time_window', None) or self._time_window

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

        # ----- NEW: Efficiency metrics -----
        # Evidence before dedup (from tool call tracking, or estimate from tool calls)
        if self._evidence_before_dedup > 0:
            self._metrics.evidence_before_dedup = self._evidence_before_dedup
        else:
            # Estimate from tool calls if we have detailed tracking
            self._metrics.evidence_before_dedup = sum(
                tc.evidence_count for tc in self._metrics.tool_calls
            ) or len(evidence)

        # Redundancy ratio: how much duplicate evidence was there?
        if self._metrics.evidence_before_dedup > 0:
            dedup_removed = self._metrics.evidence_before_dedup - len(evidence)
            self._metrics.redundancy_ratio = round(
                dedup_removed / self._metrics.evidence_before_dedup, 3
            )

        # Cost per evidence: tokens spent per evidence item
        total_tokens = self._metrics.total_tokens
        if len(evidence) > 0 and total_tokens > 0:
            self._metrics.cost_per_evidence = round(total_tokens / len(evidence), 2)

        # ----- NEW: Quality proxy metrics -----
        # Evidence recency score
        self._metrics.evidence_recency_score = compute_evidence_recency(
            evidence, time_window
        )

        # Query/task coverage score
        self._metrics.query_coverage_score = compute_query_coverage(evidence, tasks)

        # Tool success rate and avg evidence per call
        if self._metrics.tool_calls:
            successful_calls = [tc for tc in self._metrics.tool_calls if tc.success]
            total_calls = len(self._metrics.tool_calls)
            self._metrics.tool_success_rate = round(
                len(successful_calls) / total_calls, 3
            ) if total_calls > 0 else 0.0

            if successful_calls:
                total_evidence_from_calls = sum(tc.evidence_count for tc in successful_calls)
                self._metrics.avg_evidence_per_tool_call = round(
                    total_evidence_from_calls / len(successful_calls), 2
                )
        else:
            # Fallback: estimate from api_calls counter
            total_api_calls = sum(self._metrics.total_api_calls.values())
            if total_api_calls > 0:
                # Assume all calls succeeded if we don't have detailed tracking
                self._metrics.tool_success_rate = 1.0
                self._metrics.avg_evidence_per_tool_call = round(
                    len(evidence) / total_api_calls, 2
                )

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


def compute_evidence_recency(
    evidence: List[Any],
    time_window: Optional[str],
) -> float:
    """Compute what percentage of evidence falls within the requested time window.

    Args:
        evidence: List of evidence items with optional 'date' field
        time_window: Requested time window (e.g., "last 24 hours", "last week")

    Returns:
        0.0 to 1.0 - proportion of dated evidence within the time window
    """
    if not evidence:
        return 0.0

    # Parse time window to get the cutoff date
    cutoff_date = _parse_time_window_cutoff(time_window)
    if cutoff_date is None:
        # Can't determine recency without a time window, assume all are recent
        return 1.0

    dated_count = 0
    recent_count = 0

    for ev in evidence:
        date_str = getattr(ev, 'date', None)
        if not date_str:
            continue

        dated_count += 1
        ev_date = _parse_evidence_date(date_str)
        if ev_date and ev_date >= cutoff_date:
            recent_count += 1

    if dated_count == 0:
        # No dated evidence - can't compute recency
        return 0.5  # Neutral score

    return round(recent_count / dated_count, 3)


def _parse_time_window_cutoff(time_window: Optional[str]) -> Optional[datetime]:
    """Parse a time window string and return the cutoff datetime.

    Supports formats like:
    - "last 24 hours", "last 48 hours"
    - "last day", "last week", "last month"
    - "daily", "weekly", "monthly"
    """
    if not time_window:
        return None

    now = datetime.now()
    tw = time_window.lower().strip()

    # Handle "last X hours"
    if "hour" in tw:
        import re
        match = re.search(r'(\d+)\s*hour', tw)
        if match:
            hours = int(match.group(1))
            return now - timedelta(hours=hours)

    # Handle common time windows
    window_map = {
        "daily": timedelta(days=1),
        "day": timedelta(days=1),
        "last day": timedelta(days=1),
        "last 24 hours": timedelta(hours=24),
        "last 48 hours": timedelta(hours=48),
        "weekly": timedelta(weeks=1),
        "week": timedelta(weeks=1),
        "last week": timedelta(weeks=1),
        "monthly": timedelta(days=30),
        "month": timedelta(days=30),
        "last month": timedelta(days=30),
        "quarterly": timedelta(days=90),
        "last quarter": timedelta(days=90),
    }

    for pattern, delta in window_map.items():
        if pattern in tw:
            return now - delta

    # Default: last 24 hours
    return now - timedelta(hours=24)


def _parse_evidence_date(date_str: str) -> Optional[datetime]:
    """Parse a date string from evidence into a datetime.

    Handles various formats commonly seen in search results.
    """
    if not date_str:
        return None

    # Common date formats to try
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%B %d, %Y",  # "January 15, 2024"
        "%b %d, %Y",  # "Jan 15, 2024"
        "%d %B %Y",   # "15 January 2024"
        "%d %b %Y",   # "15 Jan 2024"
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]

    # Clean up common issues
    date_str = date_str.strip()

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try dateutil as fallback if available
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(date_str, fuzzy=True)
    except Exception:
        pass

    return None


def compute_query_coverage(
    evidence: List[Any],
    tasks: List[str],
) -> float:
    """Compute how well the evidence covers the research tasks/queries.

    Uses simple keyword matching to estimate coverage. Each task is considered
    "covered" if at least one evidence item's title or snippet contains
    significant words from the task.

    Args:
        evidence: List of evidence items
        tasks: List of research tasks/queries

    Returns:
        0.0 to 1.0 - proportion of tasks with matching evidence
    """
    if not tasks:
        return 1.0  # No tasks = nothing to cover
    if not evidence:
        return 0.0

    # Extract keywords from tasks (skip common stop words)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'about', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'between', 'under', 'again', 'further', 'then', 'once',
        'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
        'am', 'it', 'its', 'as', 'if', 'each', 'how', 'when', 'where', 'why',
        'all', 'both', 'any', 'some', 'no', 'not', 'only', 'same', 'so',
        'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there',
        'news', 'latest', 'recent', 'update', 'updates', 'today',
    }

    def extract_keywords(text: str) -> set:
        """Extract meaningful keywords from text."""
        if not text:
            return set()
        # Simple tokenization - split on non-alphanumeric
        import re
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return {w for w in words if w not in stop_words}

    # Build evidence text corpus
    evidence_keywords: set = set()
    for ev in evidence:
        title = getattr(ev, 'title', '') or ''
        snippet = getattr(ev, 'snippet', '') or ''
        evidence_keywords.update(extract_keywords(title))
        evidence_keywords.update(extract_keywords(snippet))

    # Check coverage for each task
    covered_tasks = 0
    for task in tasks:
        task_keywords = extract_keywords(task)
        if not task_keywords:
            covered_tasks += 1  # Empty task counts as covered
            continue

        # Task is covered if at least 30% of its keywords appear in evidence
        matching = task_keywords & evidence_keywords
        coverage_ratio = len(matching) / len(task_keywords)
        if coverage_ratio >= 0.3:
            covered_tasks += 1

    return round(covered_tasks / len(tasks), 3)


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

            # ----- NEW: Efficiency metrics -----
            ("evidence_before_dedup", metrics.evidence_before_dedup, "Evidence count before deduplication"),
            ("redundancy_ratio", metrics.redundancy_ratio, "Duplicate evidence ratio (0-1, lower is better)"),
            ("cost_per_evidence", metrics.cost_per_evidence, "Tokens per evidence item"),

            # ----- NEW: Quality proxy metrics -----
            ("evidence_recency", metrics.evidence_recency_score, "% of sources within time window (0-1)"),
            ("query_coverage", metrics.query_coverage_score, "How well evidence covers tasks (0-1)"),
            ("tool_success_rate", metrics.tool_success_rate, "% of tool calls returning results (0-1)"),
            ("avg_evidence_per_call", metrics.avg_evidence_per_tool_call, "Avg evidence items per tool call"),
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
    "ToolCallResult",
    "PhaseMetrics",
    "StrategyMetrics",
    "MetricsCollector",
    "compute_source_diversity",
    "compute_evidence_recency",
    "compute_query_coverage",
    "record_strategy_scores",
    "get_metrics_collector",
    "set_metrics_collector",
]
