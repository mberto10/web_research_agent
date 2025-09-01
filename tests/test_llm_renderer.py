from core.graph import write
from core.state import State, Evidence
from strategies import Strategy, StrategyMeta
import strategies
import renderers


def test_llm_renderer_generates_sections(monkeypatch):
    strategy = Strategy(
        meta=StrategyMeta(
            slug="test",
            version=1,
            category="news",
            time_window="day",
            depth="brief",
        ),
        tool_chain=[],
        render={"type": "llm", "sections": ["alpha", "beta"]},
    )
    monkeypatch.setattr(strategies, "load_strategy", lambda slug: strategy)
    import core.graph as graph_module
    monkeypatch.setattr(graph_module, "load_strategy", lambda slug: strategy)

    llm_renderer = renderers.get_renderer("llm")
    monkeypatch.setattr(llm_renderer, "_chat_completion", lambda messages: "Rendered paragraph")

    state = State(
        user_request="test",
        strategy_slug="test",
        evidence=[
            Evidence(url="http://a.com", title="alpha news", snippet="details alpha"),
            Evidence(url="http://b.com", title="beta update", snippet="details beta"),
        ],
    )
    new_state = write(state)
    assert len(new_state.sections) == 2
    assert new_state.sections[0].startswith("## alpha")
    assert "Rendered paragraph" in new_state.sections[0]
    assert len(new_state.citations) == 2
