from __future__ import annotations

"""Common types for tool adapters."""

from typing import Protocol, Any, List

from core.state import Evidence


class ToolAdapter(Protocol):
    """Protocol for a tool adapter."""

    name: str

    def call(self, *args: Any, **kwargs: Any) -> List[Evidence]:
        """Execute the tool and return normalized evidence records."""
        ...
