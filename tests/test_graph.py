from core.graph import build_graph
from core.state import State, Evidence
from tools import register_tool
from tools import registry as reg


class DummySonar:
    name = "sonar"

    def call(self, prompt, **params):
        return [Evidence(url="http://sonar.example", tool="sonar")]


class DummyExa:
    name = "exa"

    def call(self, query, **params):
        return [Evidence(url="http://exa.example", tool="exa")]

    def contents(self, url, **params):
        return Evidence(url=url, snippet="content", tool="exa")

    def find_similar(self, url, **params):
        return []


def test_graph_compiles(monkeypatch):
    monkeypatch.setattr(reg, "_tool_registry", {})
    register_tool(DummySonar())
    register_tool(DummyExa())
codex/add-graph-node-to-cluster-evidence-summaries
    monkeypatch.setattr("core.graph._cluster_llm", lambda prompt: "- summary")
    import core.graph as graph_module
    monkeypatch.setattr(graph_module, "_refine_queries_with_llm", lambda *a, **k: {})
main
    graph = build_graph()
    state = State(user_request="economy and politics")
    result = graph.invoke(state, config={"configurable": {"thread_id": "test"}})
    assert result["user_request"] == "economy and politics"
    assert result["category"] == "general"
    assert result["time_window"] == "week"
    assert result["strategy_slug"] == "general/week_overview"
    assert result["tasks"] == ["economy", "politics"]
    assert "summary" in result["summaries"]
