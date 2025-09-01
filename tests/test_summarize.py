from core.graph import summarize
from core.state import State, Evidence


def test_summarize_adds_bullets(monkeypatch):
    state = State(user_request="test")
    state.evidence = [
        Evidence(url="http://a.com", title="Title A", snippet="Snippet A"),
        Evidence(url="http://b.com", title="Title B", snippet="Snippet B"),
    ]
    monkeypatch.setattr("core.graph._cluster_llm", lambda prompt: "- Bullet 1\n- Bullet 2")
    new_state = summarize(state)
    assert new_state.summaries == ["Bullet 1", "Bullet 2"]
