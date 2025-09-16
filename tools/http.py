from __future__ import annotations

"""Minimal HTTP adapter.

Note: In restricted environments, this adapter may not perform real network
calls. The method is provided to fit into the deterministic architecture and
can be swapped with a real implementation in production.
"""

from typing import Any, Dict

from .types import ToolAdapter


class HttpAdapter:
    name = "http"

    def get(self, url: str, **kwargs: Any) -> Dict[str, Any]:
        # Placeholder implementation to keep the architecture working offline.
        # A production implementation would fetch the URL content.
        return {"url": url, "status": 200, "content": ""}

    # Protocol compat: default call maps to get()
    def call(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        if args:
            return self.get(args[0], **kwargs)
        raise ValueError("http.get requires a URL")


__all__ = ["HttpAdapter"]

