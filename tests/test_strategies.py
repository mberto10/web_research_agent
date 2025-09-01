from strategies import load_strategy, select_strategy


def test_select_and_load_strategy():
    slug = select_strategy("news", "day", "brief")
    assert slug == "news/real_time_briefing"
    strategy = load_strategy(slug)
    assert strategy.meta.slug == slug
    assert strategy.tool_chain[0].name == "sonar_snapshot"
