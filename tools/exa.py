from __future__ import annotations

"""Adapter for the Exa search API."""

from typing import Any, List
import os

from core.state import Evidence


class ExaAdapter:
    """Wrapper around ``exa-py`` client that normalizes outputs."""

    name = "exa"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("EXA_API_KEY")
        if not self.api_key:
            raise ValueError("Exa API key required")

    def _client(self):
        from exa_py import Exa  # Imported lazily

        return Exa(self.api_key)

    def search(self, query: str, **params: Any) -> List[Evidence]:
        client = self._client()
        response = client.search(query, **params)
        results = response.get("results") if isinstance(response, dict) else getattr(response, "results", [])
        evidence: List[Evidence] = []
        for r in results:
            url = r.get("url") if isinstance(r, dict) else getattr(r, "url", None)
            evidence.append(
                Evidence(
                    url=url or "",
                    title=r.get("title") if isinstance(r, dict) else getattr(r, "title", None),
                    publisher=r.get("source") if isinstance(r, dict) else getattr(r, "source", None),
                    date=r.get("publishedDate") if isinstance(r, dict) else getattr(r, "publishedDate", None),
                    snippet=r.get("snippet") if isinstance(r, dict) else getattr(r, "snippet", None),
                    tool=self.name,
                    score=r.get("score") if isinstance(r, dict) else getattr(r, "score", None),
                )
            )
        return evidence

    def contents(self, url: str, **params: Any) -> Evidence:
        client = self._client()
        response = client.contents(url, **params)
        text = response.get("text") if isinstance(response, dict) else getattr(response, "text", None)
        return Evidence(url=url, snippet=text, tool=self.name)

    def find_similar(self, url: str, **params: Any) -> List[Evidence]:
        client = self._client()
        response = client.findSimilar(url, **params)
        results = response.get("results") if isinstance(response, dict) else getattr(response, "results", [])
        evidence: List[Evidence] = []
        for r in results:
            u = r.get("url") if isinstance(r, dict) else getattr(r, "url", None)
            evidence.append(Evidence(url=u or "", title=r.get("title") if isinstance(r, dict) else getattr(r, "title", None), tool=self.name))
        return evidence

    def answer(self, query: str, **params: Any) -> str:
        client = self._client()
        response = client.answer(query, **params)
        return response.get("answer") if isinstance(response, dict) else getattr(response, "answer", "")

    def call(self, *args: Any, **kwargs: Any) -> List[Evidence]:
        """Default call proxies to ``search`` for registry uniformity."""
        return self.search(*args, **kwargs)


__all__ = ["ExaAdapter"]
