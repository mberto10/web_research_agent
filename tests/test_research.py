from core.graph import research
from core.state import State, Evidence
from strategies import Strategy, StrategyMeta, ToolStep
from tools import register_tool
import strategies


class DummySonar:
    name = "sonar"

    def call(self, prompt: str, **params):
        return [
            Evidence(url="http://a.com", score=0.9, tool="sonar"),
            Evidence(url="http://b.com", score=0.8, tool="sonar"),
        ]


class DummyExa:
    name = "exa"

    def call(self, query: str, **params):
        return [
            Evidence(url="http://a.com", score=0.95, tool="exa"),
            Evidence(url="http://c.com", score=0.7, tool="exa"),
        ]


def make_strategy(max_results=10):
    meta = StrategyMeta(slug="test", version=1, category="news", time_window="day", depth="brief")
    tool_chain = [ToolStep(name="sonar_snapshot"), ToolStep(name="exa_search_primary")]
    queries = {"sonar": "latest {{topic}}", "exa_search": "{{topic}} news"}
    limits = {"max_results": max_results}
    return Strategy(meta=meta, tool_chain=tool_chain, queries=queries, limits=limits)


def setup(monkeypatch, strategy):
    # Reset registry and register dummy tools
    from tools import registry as reg
    import core.graph as graph_module

    monkeypatch.setattr(reg, "_tool_registry", {})
    register_tool(DummySonar())
    register_tool(DummyExa())
    monkeypatch.setattr(strategies, "load_strategy", lambda slug: strategy)
    monkeypatch.setattr(graph_module, "load_strategy", lambda slug: strategy)


def test_research_dedupes(monkeypatch):
    strategy = make_strategy(max_results=10)
    setup(monkeypatch, strategy)
    state = State(user_request="test", tasks=["alpha"], strategy_slug="test")
    new_state = research(state)
    assert len(new_state.evidence) == 3  # one duplicate removed from four inputs
    urls = sorted(ev.url for ev in new_state.evidence)
    assert urls == ["http://a.com", "http://b.com", "http://c.com"]


def test_research_respects_budget(monkeypatch):
    strategy = make_strategy(max_results=1)
    setup(monkeypatch, strategy)
    state = State(user_request="test", tasks=["alpha"], strategy_slug="test")
    new_state = research(state)
    assert len(new_state.evidence) == 1
    assert new_state.evidence[0].url == "http://a.com"
