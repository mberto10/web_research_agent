from __future__ import annotations

"""Renderer contracts and simple implementations."""

from typing import Dict, List, Protocol
import json

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


_RENDERERS = {
    r.name: r
    for r in [
        BriefingRenderer(),
        MemoRenderer(),
        DossierRenderer(),
        FactCheckRenderer(),
        QARenderer(),
        JSONRenderer(),
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
]
