from __future__ import annotations

"""Renderer contracts and simple implementations."""

from typing import Dict, List, Protocol
import json
import os
import re
from datetime import datetime

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


class MarkdownRenderer:
    """Pass-through renderer that preserves markdown content from LLM."""
    
    name = "markdown"
    
    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        """Pass through markdown content with citations.
        
        For strategies using LLM Analyzer, sections[0] contains the full markdown.
        For other strategies, sections contain individual section content.
        """
        # If we have LLM-generated content (like from daily_news_briefing)
        # it will be in the first Evidence item's snippet
        rendered: List[str] = []
        
        # Check if this is LLM-generated content
        llm_content = None
        for ev in evidence:
            if ev.url == "llm_analysis_result" and ev.snippet:
                llm_content = ev.snippet
                break
        
        if llm_content:
            # Pass through the LLM-generated markdown as-is
            rendered = [llm_content]
        elif sections:
            # Use provided sections
            rendered = sections
        else:
            # Fallback: create simple markdown from evidence
            lines = ["# Research Results\n"]
            for ev in evidence:
                if ev.title:
                    lines.append(f"## {ev.title}")
                if ev.snippet:
                    lines.append(f"{ev.snippet}\n")
            rendered = ["\n".join(lines)]
        
        # Format citations
        citations: List[str] = []
        seen: set[str] = set()
        for ev in evidence:
            url = ev.url
            if url and url not in seen and url != "llm_analysis_result":
                seen.add(url)
                publisher = ev.publisher or "Unknown"
                date = ev.date or "n.d."
                citations.append(f"{publisher} ({date}) {url}")
        
        return {"sections": rendered, "citations": citations}


class NewsletterRenderer:
    """Transform markdown into professional HTML newsletter."""
    
    name = "newsletter"
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """Convert markdown to HTML."""
        html = markdown_text
        
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Bold and italic
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        
        # Links
        html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
        
        # Lists
        lines = html.split('\n')
        in_list = False
        new_lines = []
        for line in lines:
            if line.strip().startswith('- '):
                if not in_list:
                    new_lines.append('<ul>')
                    in_list = True
                new_lines.append(f'<li>{line.strip()[2:]}</li>')
            elif line.strip().startswith(('1. ', '2. ', '3. ', '4. ', '5. ')):
                if not in_list:
                    new_lines.append('<ol>')
                    in_list = True
                new_lines.append(f'<li>{line.strip()[3:]}</li>')
            else:
                if in_list:
                    tag = '</ul>' if new_lines[-1].startswith('<li>') and '- ' in lines[lines.index(line)-1] else '</ol>'
                    new_lines.append(tag)
                    in_list = False
                if line.strip():
                    new_lines.append(f'<p>{line}</p>')
                else:
                    new_lines.append('<br/>')
        
        if in_list:
            new_lines.append('</ul>')
        
        return '\n'.join(new_lines)
    
    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        """Transform markdown to professional HTML newsletter."""
        # First get the markdown content
        markdown_renderer = MarkdownRenderer()
        markdown_result = markdown_renderer.render(sections, evidence)
        markdown_content = markdown_result["sections"][0] if markdown_result["sections"] else ""
        
        # Convert to HTML
        html_body = self._markdown_to_html(markdown_content)
        
        # Create professional newsletter template
        today = datetime.now().strftime('%B %d, %Y')
        newsletter_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f4f4f4;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 700px;
            margin: 20px auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
            font-weight: 300;
            letter-spacing: 1px;
        }}
        .header .date {{
            margin-top: 10px;
            font-size: 14px;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        h2 {{
            color: #1e3c72;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
            margin-top: 30px;
            margin-bottom: 20px;
        }}
        h3 {{
            color: #2a5298;
            margin-top: 25px;
            margin-bottom: 15px;
        }}
        p {{
            margin-bottom: 15px;
            text-align: justify;
        }}
        ul, ol {{
            margin-bottom: 20px;
            padding-left: 30px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        a {{
            color: #2a5298;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            background: #f8f8f8;
            padding: 20px 30px;
            border-top: 1px solid #e0e0e0;
        }}
        .citations {{
            font-size: 12px;
            color: #666;
        }}
        .citations h4 {{
            color: #444;
            margin-bottom: 10px;
        }}
        .citations ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        .citations li {{
            margin-bottom: 5px;
            padding-left: 15px;
            position: relative;
        }}
        .citations li:before {{
            content: "▸";
            position: absolute;
            left: 0;
        }}
        strong {{
            color: #1e3c72;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Intelligence Briefing</h1>
            <div class="date">{today}</div>
        </div>
        <div class="content">
            {html_body}
        </div>
        <div class="footer">
            <div class="citations">
                <h4>Sources ({len(evidence)} references)</h4>
                <ul>
"""
        
        # Add citations
        for citation in markdown_result["citations"][:10]:  # Limit to 10 citations for newsletter
            newsletter_html += f"                    <li>{citation}</li>\n"
        
        newsletter_html += """                </ul>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        return {"sections": [newsletter_html], "citations": markdown_result["citations"]}


class PDFRenderer:
    """Transform markdown into PDF-ready HTML (can be converted with weasyprint)."""
    
    name = "pdf"
    
    def render(self, sections: List[str], evidence: List[Evidence]) -> Dict[str, List[str]]:
        """Create PDF-ready HTML document."""
        # First get the markdown content
        markdown_renderer = MarkdownRenderer()
        markdown_result = markdown_renderer.render(sections, evidence)
        markdown_content = markdown_result["sections"][0] if markdown_result["sections"] else ""
        
        # Convert markdown to HTML (reuse newsletter converter)
        newsletter = NewsletterRenderer()
        html_content = newsletter._markdown_to_html(markdown_content)
        
        # Create PDF-optimized HTML
        today = datetime.now().strftime('%B %d, %Y')
        pdf_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 10pt;
                color: #666;
            }}
            @bottom-left {{
                content: "Confidential";
                font-size: 10pt;
                color: #666;
            }}
        }}
        body {{
            font-family: 'Times New Roman', Times, serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #000;
            text-align: justify;
        }}
        .cover-page {{
            page-break-after: always;
            text-align: center;
            padding-top: 200px;
        }}
        .cover-page h1 {{
            font-size: 32pt;
            margin-bottom: 20px;
            color: #1e3c72;
        }}
        .cover-page .date {{
            font-size: 14pt;
            color: #666;
        }}
        .cover-page .classification {{
            margin-top: 50px;
            font-size: 12pt;
            color: #c00;
            font-weight: bold;
        }}
        h2 {{
            font-size: 18pt;
            color: #1e3c72;
            margin-top: 24pt;
            margin-bottom: 12pt;
            page-break-after: avoid;
        }}
        h3 {{
            font-size: 14pt;
            color: #2a5298;
            margin-top: 18pt;
            margin-bottom: 9pt;
            page-break-after: avoid;
        }}
        p {{
            orphans: 3;
            widows: 3;
        }}
        ul, ol {{
            margin-bottom: 12pt;
        }}
        .bibliography {{
            page-break-before: always;
            font-size: 10pt;
        }}
        .bibliography h2 {{
            font-size: 16pt;
        }}
        .bibliography ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        .bibliography li {{
            margin-bottom: 6pt;
            text-indent: -20pt;
            padding-left: 20pt;
        }}
    </style>
</head>
<body>
    <div class="cover-page">
        <h1>Intelligence Briefing</h1>
        <div class="date">{today}</div>
        <div class="classification">CONFIDENTIAL</div>
    </div>
    
    <div class="content">
        {html_content}
    </div>
    
    <div class="bibliography">
        <h2>References</h2>
        <ul>
"""
        
        # Add all citations in bibliography format
        for i, citation in enumerate(markdown_result["citations"], 1):
            pdf_html += f"            <li>[{i}] {citation}</li>\n"
        
        pdf_html += """        </ul>
    </div>
</body>
</html>"""
        
        return {"sections": [pdf_html], "citations": markdown_result["citations"]}


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
        MarkdownRenderer(),
        NewsletterRenderer(),
        PDFRenderer(),
    ]
}


def get_renderer(name: str) -> Renderer:
    """Retrieve a renderer by name, instantiating LLM renderer with config."""
    if name == "llm":
        try:
            from core.config import get_llm_config  # local import to avoid cycles
        except Exception:
            return LLMRenderer()
        cfg = get_llm_config("renderer")
        model = cfg.get("model") or "gpt-4o-mini"
        return LLMRenderer(model=model)
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
    "MarkdownRenderer",
    "NewsletterRenderer",
    "PDFRenderer",
]
