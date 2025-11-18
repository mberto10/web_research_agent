from __future__ import annotations

"""Adapter for the Parallel Search API."""

from typing import Any, Dict, List, Sequence
import os
import json
from urllib.parse import urlparse

import requests

from core.state import Evidence
from core.langfuse_tracing import get_langfuse_client, observe


class ParallelSearchAdapter:
    """Call the Parallel Search API and normalize the response to Evidence objects."""

    name = "parallel_search"
    _BETA_HEADER_DEFAULT = "search-extract-2025-10-10"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.parallel.ai",
        beta_header: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.getenv("PARALLEL_API_KEY")
        if not self.api_key:
            raise ValueError("Parallel API key required (set PARALLEL_API_KEY)")
        self.base_url = base_url.rstrip("/")
        self.beta_header = beta_header or os.getenv("PARALLEL_BETA_HEADER") or self._BETA_HEADER_DEFAULT
        self.timeout = timeout

    @staticmethod
    def _parse_list(value: Any) -> List[str] | None:
        if value is None:
            return None
        if isinstance(value, list):
            return [str(v) for v in value if v is not None]
        if isinstance(value, tuple) or isinstance(value, set):
            return [str(v) for v in value if v is not None]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, Sequence) and not isinstance(parsed, str):
                    return [str(v) for v in parsed if v is not None]
            except json.JSONDecodeError:
                pass
            if "," in stripped:
                return [item.strip() for item in stripped.split(",") if item.strip()]
            return [stripped]
        # Fallback to single item list
        return [str(value)]

    @staticmethod
    def _parse_object(value: Any) -> Dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None
        return None

    def _build_payload(self, **params: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        objective = params.get("objective")
        search_queries = self._parse_list(params.get("search_queries"))
        if objective:
            payload["objective"] = objective
        if search_queries:
            payload["search_queries"] = search_queries

        if not payload.get("objective") and not payload.get("search_queries"):
            raise ValueError("Parallel Search requires at least one of objective or search_queries")

        mode = params.get("mode")
        if mode:
            payload["mode"] = mode

        max_results = params.get("max_results")
        if max_results is not None:
            try:
                payload["max_results"] = int(max_results)
            except (TypeError, ValueError):
                pass

        # Handle excerpts configuration (including deprecated top-level value)
        excerpts = self._parse_object(params.get("excerpts"))
        max_chars_per_result = params.get("max_chars_per_result")
        if max_chars_per_result is not None:
            try:
                max_chars = int(max_chars_per_result)
                excerpts = excerpts or {}
                excerpts["max_chars_per_result"] = max_chars
            except (TypeError, ValueError):
                pass
        if excerpts:
            payload["excerpts"] = excerpts

        source_policy = self._parse_object(params.get("source_policy"))
        if source_policy:
            payload["source_policy"] = source_policy

        fetch_policy = self._parse_object(params.get("fetch_policy"))
        if fetch_policy:
            payload["fetch_policy"] = fetch_policy

        return payload

    def _request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "parallel-beta": self.beta_header,
        }
        url = f"{self.base_url}/v1beta/search"
        response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _normalize_results(self, data: Dict[str, Any]) -> List[Evidence]:
        results = data.get("results") or []
        evidence: List[Evidence] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            url = item.get("url") or ""
            title = item.get("title")
            publish_date = item.get("publish_date")
            excerpts = item.get("excerpts") or []
            snippet = "\n".join(excerpts) if isinstance(excerpts, list) else None
            publisher = None
            if url:
                try:
                    publisher = urlparse(url).netloc or None
                except Exception:
                    publisher = None
            evidence.append(
                Evidence(
                    url=url,
                    title=title,
                    publisher=publisher,
                    date=publish_date,
                    snippet=snippet,
                    tool=self.name,
                )
            )
        return evidence

    @observe(as_type="span", name="parallel-search")
    def call(self, **params: Any) -> List[Evidence]:
        payload = self._build_payload(**params)

        lf_client = get_langfuse_client()
        if lf_client:
            lf_client.update_current_span(
                input={"payload": payload},
                metadata={"adapter": "parallel_search", "method": "search"},
            )

        try:
            data = self._request(payload)
        except requests.RequestException as exc:
            if lf_client:
                lf_client.update_current_span(
                    output={"error": str(exc)},
                    metadata={"status": "error"},
                )
            print(f"Parallel Search API error: {exc}")
            return []

        evidence = self._normalize_results(data)

        if lf_client:
            lf_client.update_current_span(
                output={
                    "search_id": data.get("search_id"),
                    "results": data.get("results", [])[:5],
                    "warnings": data.get("warnings"),
                },
                metadata={"status": "success"},
            )
        return evidence


__all__ = ["ParallelSearchAdapter"]
