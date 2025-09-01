from core.graph import build_graph
from core.state import State


def test_graph_compiles():
    graph = build_graph()
    state = State(user_request="test")
    result = graph.invoke(state, config={"configurable": {"thread_id": "test"}})
    assert result["user_request"] == "test"
