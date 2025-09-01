from core.graph import write
from core.state import State, Evidence
from strategies import Strategy, StrategyMeta
import strategies


def test_write_renders_sections_and_citations(monkeypatch):
    strategy = Strategy(
        meta=StrategyMeta(
            slug="test",
            version=1,
            category="news",
            time_window="day",
            depth="brief",
        ),
        tool_chain=[],
        render={"type": "briefing", "sections": ["summary", "analysis"]},
    )
    monkeypatch.setattr(strategies, "load_strategy", lambda slug: strategy)
    import core.graph as graph_module
    monkeypatch.setattr(graph_module, "load_strategy", lambda slug: strategy)
    state = State(
        user_request="test",
        strategy_slug="test",
        evidence=[
            Evidence(
                url="http://a.com",
                publisher="A",
                date="2024-01-01",
                snippet="alpha",
            )
        ],
    )
    new_state = write(state)
    assert len(new_state.sections) == 2
    assert new_state.sections[0].startswith("## summary")
    assert len(new_state.citations) == 1
    assert "http://a.com" in new_state.citations[0]
