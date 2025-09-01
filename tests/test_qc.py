from datetime import datetime

from core.graph import qc
from core.state import State, Evidence
from strategies import Strategy, StrategyMeta
import strategies
import core.graph as graph_module


def _make_strategy():
    return Strategy(
        meta=StrategyMeta(
            slug="test",
            version=1,
            category="news",
            time_window="day",
            depth="brief",
        ),
        tool_chain=[],
        render={"type": "briefing", "sections": ["summary"]},
        quorum={"min_sources": 1},
        filters={"recency": "week"},
    )


def test_qc_passes_with_valid_data(monkeypatch):
    strategy = _make_strategy()
    monkeypatch.setattr(strategies, "load_strategy", lambda slug: strategy)
    monkeypatch.setattr(graph_module, "load_strategy", lambda slug: strategy)

    today = datetime.utcnow().date().isoformat()
    state = State(
        user_request="test",
        strategy_slug="test",
        sections=["## summary"],
        citations=["A ({} ) http://a.com".format(today)],
        evidence=[Evidence(url="http://a.com", date=today)],
    )
    new_state = qc(state)
    assert new_state.errors == []


def test_qc_records_errors(monkeypatch):
    strategy = _make_strategy()
    strategy.quorum = {"min_sources": 2}
    monkeypatch.setattr(strategies, "load_strategy", lambda slug: strategy)
    monkeypatch.setattr(graph_module, "load_strategy", lambda slug: strategy)

    old_date = (datetime.utcnow().date().replace(day=1)).isoformat()
    state = State(
        user_request="test",
        strategy_slug="test",
        sections=[],
        citations=[],
        evidence=[Evidence(url="http://a.com", date=old_date)],
    )
    new_state = qc(state)
    assert any("missing section" in e for e in new_state.errors)
    assert any("insufficient sources" in e for e in new_state.errors)
