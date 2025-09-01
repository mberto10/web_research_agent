from core.graph import build_graph
from core.state import State


def test_graph_compiles():
    graph = build_graph()
    state = State(user_request="economy and politics")
    result = graph.invoke(state, config={"configurable": {"thread_id": "test"}})
    assert result["user_request"] == "economy and politics"
    assert result["category"] == "general"
    assert result["time_window"] == "week"
    assert result["strategy_slug"] == "general/week_overview"
    assert result["tasks"] == ["economy", "politics"]
