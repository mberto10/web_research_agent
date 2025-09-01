from __future__ import annotations

"""Adapter for the Perplexity Sonar API."""

from typing import Any, Dict, List
import os

from core.state import Evidence


class SonarAdapter:
    """Call the Sonar (Perplexity) chat completions API and normalize citations."""

    name = "sonar"

    def __init__(self, model: str = "sonar", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("SONAR_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("Sonar API key required")

    # Separate network call for easier testing
    def _chat_completion(self, messages: List[Dict[str, str]], **params: Any) -> Any:
        from openai import OpenAI  # Imported lazily to keep optional dependency

        client = OpenAI(api_key=self.api_key)
        return client.chat.completions.create(model=self.model, messages=messages, **params)

    def call(self, prompt: str, **params: Any) -> List[Evidence]:
        """Execute a chat completion and return normalized citation evidence."""
        messages = [{"role": "user", "content": prompt}]
        response = self._chat_completion(messages, **params)
        # Response may be OpenAIObject; convert generically
        choice = response["choices"][0] if isinstance(response, dict) else response.choices[0]
        message = choice["message"] if isinstance(choice, dict) else choice.message
        citations = message.get("citations", []) if isinstance(message, dict) else getattr(message, "citations", [])

        evidence: List[Evidence] = []
        for c in citations:
            # Citations may be dicts or objects; use dict-like access
            url = c.get("url") if isinstance(c, dict) else getattr(c, "url", None)
            evidence.append(
                Evidence(
                    url=url or "",
                    title=c.get("title") if isinstance(c, dict) else getattr(c, "title", None),
                    publisher=c.get("publisher") if isinstance(c, dict) else getattr(c, "publisher", None),
                    date=c.get("publishedAt") if isinstance(c, dict) else getattr(c, "publishedAt", None),
                    snippet=c.get("snippet") if isinstance(c, dict) else getattr(c, "snippet", None),
                    tool=self.name,
                )
            )
        return evidence


# The adapter conforms to ``ToolAdapter`` protocol
__all__ = ["SonarAdapter"]
