from core.config import get_node_llm_config, get_node_prompt


def test_get_node_llm_config_defaults():
    cfg = get_node_llm_config("scope_classifier")
    assert isinstance(cfg, dict)
    assert cfg.get("model")


def test_get_node_prompt_defaults():
    prompt = get_node_prompt("query_refiner")
    assert isinstance(prompt, str)
    assert "{snippets}" in prompt
