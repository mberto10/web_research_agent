import pytest
from unittest.mock import AsyncMock, MagicMock
from core.config import (
    get_node_llm_config,
    get_node_prompt,
    load_config,
    load_config_from_db,
    clear_config_cache,
    _CONFIG_CACHE
)


def test_get_node_llm_config_defaults():
    """Test node LLM config when cache is populated."""
    # Populate cache with default config
    import core.config
    core.config._CONFIG_CACHE = core.config._default_config()

    try:
        cfg = get_node_llm_config("scope_classifier")
        assert isinstance(cfg, dict)
        assert cfg.get("model")
    finally:
        clear_config_cache()


def test_get_node_prompt_defaults():
    """Test node prompt when cache is populated."""
    # Populate cache with default config
    import core.config
    core.config._CONFIG_CACHE = core.config._default_config()

    try:
        prompt = get_node_prompt("query_refiner")
        assert isinstance(prompt, str)
        assert "{snippets}" in prompt
    finally:
        clear_config_cache()


@pytest.mark.anyio(backends=["asyncio"])
async def test_load_config_from_db():
    """Test loading config from database populates cache."""
    # Clear cache first
    clear_config_cache()

    # Mock database session and settings
    db_mock = AsyncMock()

    llm_setting = MagicMock()
    llm_setting.value = {
        "fill": {"model": "gpt-4o-mini", "temperature": 0},
        "summarize": {"model": "gpt-4o-mini", "temperature": 0}
    }

    prompts_setting = MagicMock()
    prompts_setting.value = {
        "fill": {"instructions": "Test instructions"}
    }

    # Mock the crud functions
    async def mock_get_setting(db, key):
        if key == "llm_defaults":
            return llm_setting
        elif key == "prompts":
            return prompts_setting
        return None

    # Patch the get_global_setting function inside load_config_from_db
    import api.crud
    original_crud = api.crud.get_global_setting

    try:
        api.crud.get_global_setting = mock_get_setting

        # Load from DB
        result = await load_config_from_db(db_mock)

        # Verify result
        assert result is not None
        assert "llm" in result
        assert "prompts" in result
        assert result["llm"]["defaults"]["fill"]["model"] == "gpt-4o-mini"

    finally:
        api.crud.get_global_setting = original_crud
        clear_config_cache()


def test_load_config_raises_without_db():
    """Test that load_config raises error when cache not populated."""
    clear_config_cache()

    with pytest.raises(RuntimeError, match="Configuration not loaded from database"):
        load_config()


def test_config_cache_invalidation():
    """Test that cache is properly cleared."""
    # This test relies on the default config being loaded first
    # Then we clear and verify it's gone
    clear_config_cache()

    # Verify cache is cleared
    import core.config
    assert core.config._CONFIG_CACHE is None
