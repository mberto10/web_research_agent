from __future__ import annotations

"""Minimal parsing adapter.

Provides a readability-like method that converts HTML into a text snippet.
This is a naive placeholder to keep the architecture functional without
external dependencies.
"""

from typing import Any
from core.state import Evidence


class ParseAdapter:
    name = "parse"

    def readability(self, html: str, url: str | None = None, **kwargs: Any) -> Evidence:
        # Super-naive HTML stripper: remove tags and collapse whitespace.
        import re

        text = re.sub(r"<[^>]+>", " ", html or "")
        text = re.sub(r"\s+", " ", text).strip()
        return Evidence(url=url or "", snippet=text or None, tool=self.name)

    def call(self, *args: Any, **kwargs: Any):  # protocol compatibility
        html = kwargs.get("html") if not args else args[0]
        return self.readability(html=html, url=kwargs.get("url"))


__all__ = ["ParseAdapter"]

