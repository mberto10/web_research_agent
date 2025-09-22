from core.scope import categorize_request, split_tasks, scope_request


def test_categorize_request_news():
    result = categorize_request("latest AI news")
    assert result["category"] == "news"
    assert result["time_window"] == "day"
    assert result["depth"] == "brief"
    assert result["strategy_slug"]
    assert result["variables"]["topic"]


def test_split_tasks():
    tasks = split_tasks("economy and politics, technology")
    assert tasks == ["economy", "politics", "technology"]


def test_scope_request_fallback():
    result = scope_request("economy and politics")
    assert result["category"] == "general"
    assert result["time_window"] == "week"
    assert result["tasks"] == ["economy", "politics"]
    assert result["strategy_slug"]
    assert result["variables"]["topic"]
