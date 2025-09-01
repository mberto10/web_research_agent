from core.scope import categorize_request, split_tasks


def test_categorize_request_news():
    result = categorize_request("latest AI news")
    assert result["category"] == "news"
    assert result["time_window"] == "day"
    assert result["depth"] == "brief"


def test_split_tasks():
    tasks = split_tasks("economy and politics, technology")
    assert tasks == ["economy", "politics", "technology"]
