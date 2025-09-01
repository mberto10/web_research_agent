from __future__ import annotations

"""Simple registry for tool adapters."""

from typing import Dict

from .types import ToolAdapter


_tool_registry: Dict[str, ToolAdapter] = {}


def register_tool(adapter: ToolAdapter) -> None:
    """Register a tool adapter by its name.

    Args:
        adapter: Tool adapter instance implementing ``ToolAdapter`` protocol.
    """
    _tool_registry[adapter.name] = adapter


def get_tool(name: str) -> ToolAdapter:
    """Retrieve a registered tool adapter by name.

    Raises:
        KeyError: If the tool is not registered.
    """
    try:
        return _tool_registry[name]
    except KeyError as exc:
        raise KeyError(f"Tool '{name}' is not registered") from exc
