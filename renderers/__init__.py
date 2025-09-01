from __future__ import annotations

"""Renderer contracts and simple implementations."""

from typing import Dict, List, Protocol
import json
import os

from core.state import Evidence


class Renderer(Protocol):
    """Protocol for renderer implementations."""

    name: str

    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        """Render output sections and citations.

        Args:
            sections: Ordered section names to render.
            evidence: Evidence records to cite.

        Returns:
            Dictionary with ``sections`` (rendered text) and ``citations``.
        """
        ...


class _BaseRenderer:
    """Basic renderer that creates markdown sections with bullet points."""

    name = "base"

    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        rendered: List[str] = []
        for name in sections:
            lines = [f"## {name}"]
            for ev in evidence:
                desc = ev.title or ev.snippet or ev.url
                lines.append(f"- {desc}")
            rendered.append("\n".join(lines))

        citations: List[str] = []
        seen: set[str] = set()
        for ev in evidence:
            url = ev.url
            if url and url not in seen:
                seen.add(url)
                publisher = ev.publisher or "Unknown"
                date = ev.date or "n.d."
                citations.append(f"{publisher} ({date}) {url}")
        return {"sections": rendered, "citations": citations}


class BriefingRenderer(_BaseRenderer):
    name = "briefing"


class MemoRenderer(_BaseRenderer):
    name = "memo"


class DossierRenderer(_BaseRenderer):
    name = "dossier"


class FactCheckRenderer(_BaseRenderer):
    name = "fact-check"


class QARenderer(_BaseRenderer):
    name = "qa"


class JSONRenderer(_BaseRenderer):
    name = "json"

    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        citations: List[str] = []
        seen: set[str] = set()
        for ev in evidence:
            url = ev.url
            if url and url not in seen:
                seen.add(url)
                publisher = ev.publisher or "Unknown"
                date = ev.date or "n.d."
                citations.append(f"{publisher} ({date}) {url}")
        data = [ev.model_dump() for ev in evidence]
        rendered = [json.dumps(data, indent=2)]
        return {"sections": rendered, "citations": citations}


class LLMRenderer:
    """Renderer that asks an LLM to craft polished paragraphs."""

    name = "llm"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    # Separated for easier monkeypatching in tests
    def _chat_completion(self, messages: List[Dict[str, str]]) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        from openai import OpenAI  # Imported lazily to keep optional dependency

        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(model=self.model, messages=messages)
        choice = response["choices"][0] if isinstance(response, dict) else response.choices[0]
        message = choice["message"] if isinstance(choice, dict) else choice.message
        return (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", "")
        )

    def _cluster_evidence(
        self, sections: List[str], evidence: List[Evidence]
    ) -> Dict[str, List[Evidence]]:
        groups: Dict[str, List[Evidence]] = {name: [] for name in sections}
        for ev in evidence:
            text = f"{ev.title or ''} {ev.snippet or ''}".lower()
            best = sections[0] if sections else ""
            best_score = -1
            for name in sections:
                score = 0
                for word in name.lower().split():
                    if word in text:
                        score += 1
                if score > best_score:
                    best_score = score
                    best = name
            groups.setdefault(best, []).append(ev)
        return groups

    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        grouped = self._cluster_evidence(sections, evidence)
        rendered: List[str] = []
        for name in sections:
            evs = grouped.get(name, [])
            bullet = "\n".join(
                f"- {ev.title or ev.snippet or ev.url}" for ev in evs
            )
            prompt = (
                f"You are a skilled researcher. Write a polished paragraph for the section"
                f" '{name}' using the evidence below.\n{bullet}"
            )
            text = self._chat_completion([{"role": "user", "content": prompt}]) if evs else ""
            rendered.append(f"## {name}\n\n{text.strip()}" if text else f"## {name}")

        citations: List[str] = []
        seen: set[str] = set()
        for ev in evidence:
            url = ev.url
            if url and url not in seen:
                seen.add(url)
                publisher = ev.publisher or "Unknown"
                date = ev.date or "n.d."
                citations.append(f"{publisher} ({date}) {url}")
        return {"sections": rendered, "citations": citations}


_RENDERERS = {
    r.name: r
    for r in [
        BriefingRenderer(),
        MemoRenderer(),
        DossierRenderer(),
        FactCheckRenderer(),
        QARenderer(),
        JSONRenderer(),
        LLMRenderer(),
    ]
}


def get_renderer(name: str) -> Renderer:
    """Retrieve a renderer by name."""
    try:
        return _RENDERERS[name]
    except KeyError as exc:
        raise KeyError(f"Renderer '{name}' is not registered") from exc


__all__ = [
    "Renderer",
    "get_renderer",
    "BriefingRenderer",
    "MemoRenderer",
    "DossierRenderer",
    "FactCheckRenderer",
    "QARenderer",
    "JSONRenderer",
    "LLMRenderer",
]
