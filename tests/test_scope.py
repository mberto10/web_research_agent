from core.scope import categorize_request, split_tasks, scope_request


def test_categorize_request_news(monkeypatch):
    """Test categorization with mocked LLM."""
    import core.scope

    # Mock _llm_scope to return a valid result
    def mock_llm_scope(request):
        return {
            "category": "news",
            "time_window": "day",
            "depth": "brief",
            "strategy_slug": "news/real_time_briefing",
            "tasks": ["AI news"],
            "variables": {"topic": "AI"}
        }
    monkeypatch.setattr(core.scope, "_llm_scope", mock_llm_scope)

    result = categorize_request("latest AI news")
    assert result["category"] == "news"
    assert result["time_window"] == "day"
    assert result["depth"] == "brief"
    assert result["strategy_slug"]
    assert result["variables"]["topic"]


def test_split_tasks(monkeypatch):
    """Test task splitting with mocked LLM."""
    import core.scope

    # Mock _llm_scope to return a valid result
    def mock_llm_scope(request):
        return {
            "category": "general",
            "time_window": "week",
            "depth": "overview",
            "strategy_slug": "general/week_overview",
            "tasks": ["economy", "politics", "technology"],
            "variables": {"topic": "economy"}
        }
    monkeypatch.setattr(core.scope, "_llm_scope", mock_llm_scope)

    tasks = split_tasks("economy and politics, technology")
    assert tasks == ["economy", "politics", "technology"]


def test_scope_request_requires_llm(monkeypatch):
    """Test that scope_request raises error when LLM fails."""
    import pytest
    import core.scope

    # Mock _llm_scope to return None (simulate API key missing)
    monkeypatch.setattr(core.scope, "_llm_scope", lambda request: None)

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="LLM classification failed"):
        scope_request("economy and politics")
