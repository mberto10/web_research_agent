"""
Email Template Engine for Research Agent API.

Generates professional HTML newsletter emails with FAZ-inspired typography and styling.
Optimized for Outlook compatibility via Power Automate.

Design System:
- Primary: #110a35 (deep navy)
- Secondary: #e8edee (light gray)
- Accent: #967d28 (gold)
- Typography: Georgia/serif for headlines, system sans-serif for body
"""

import re
from datetime import datetime
from typing import Optional
import markdown2


# =============================================================================
# DESIGN TOKENS (FAZ-inspired)
# =============================================================================

COLORS = {
    "primary": "#110a35",      # Deep navy - headings, emphasis
    "secondary": "#e8edee",    # Light gray - backgrounds
    "accent": "#967d28",       # Gold - highlights, section markers
    "text": "#374151",         # Body text
    "text_light": "#6b7280",   # Secondary text, timestamps
    "background": "#f8fafc",   # Page background
    "white": "#ffffff",        # Content background
    "border": "#e5e7eb",       # Subtle borders
    "warning_bg": "#fefce8",   # AI notice background
    "warning_border": "#ca8a04", # AI notice border
    "warning_text": "#713f12", # AI notice text
}

# Logo - hosted version (globe with quill)
LOGO_URL = "https://webresearchagent.replit.app/static/logo.png"


# =============================================================================
# STRATEGY TEMPLATE CONFIGURATIONS
# =============================================================================

STRATEGY_TEMPLATES = {
    "news/real_time_briefing": {
        "title_template": "Breaking: {topic}",
        "subtitle_template": "Live updates as of {time}",
        "subject_prefix": "Breaking News:",
        "show_breaking_badge": True
    },
    "company/dossier": {
        "title_template": "Company Dossier: {topic}",
        "subtitle_template": "Comprehensive company analysis",
        "subject_prefix": "Company Report:",
        "show_breaking_badge": False
    },
    "financial_research": {
        "title_template": "Financial Research: {topic}",
        "subtitle_template": "Market analysis and insights",
        "subject_prefix": "Financial Analysis:",
        "show_breaking_badge": False
    },
    "daily_news_briefing": {
        "title_template": "Daily Briefing",
        "subtitle_template": "{topic}",
        "subject_prefix": "Daily Briefing:",
        "show_breaking_badge": False
    },
    "weekly_topic_overview": {
        "title_template": "Weekly Overview: {topic}",
        "subtitle_template": "Key developments this week",
        "subject_prefix": "Weekly Overview:",
        "show_breaking_badge": False
    },
    "company_dossier": {
        "title_template": "Company Update: {topic}",
        "subtitle_template": "Weekly developments",
        "subject_prefix": "Company Update:",
        "show_breaking_badge": False
    },
    "market_dossier": {
        "title_template": "Market Update: {topic}",
        "subtitle_template": "Market developments",
        "subject_prefix": "Market Update:",
        "show_breaking_badge": False
    },
}

DEFAULT_TEMPLATE = {
    "title_template": "Research Update: {topic}",
    "subtitle_template": "AI-powered research insights",
    "subject_prefix": "Research Update:",
    "show_breaking_badge": False
}


# =============================================================================
# MARKDOWN TO HTML CONVERSION
# =============================================================================

def markdown_to_html(markdown_text: str, is_daily_briefing: bool = False) -> str:
    """Convert markdown to HTML with professional inline styling.

    Args:
        markdown_text: Markdown text to convert
        is_daily_briefing: If True, apply special styling for daily briefing sections

    Returns:
        HTML string with inline styles applied
    """
    if not markdown_text:
        return ''

    # Remove stray hash-only lines
    cleaned_lines = []
    for line in markdown_text.splitlines():
        if line.strip() in {"#", "##", "###", "####", "#####", "######"}:
            continue
        cleaned_lines.append(line)
    markdown_text = "\n".join(cleaned_lines)

    # Pre-process: Convert citation numbers [1], [2] to superscript format
    processed_text = re.sub(r'\[(\d+)\]', r'<sup>[\1]</sup>', markdown_text)

    # Convert markdown to HTML
    html = markdown2.markdown(
        processed_text,
        extras=['fenced-code-blocks', 'tables', 'strike', 'task_list']
    )

    # Apply inline styles for email client compatibility
    # Using FAZ-inspired typography
    style_mappings = [
        # H1 - Main title (rarely used in content)
        (r'<h1>', f'<h1 style="color: {COLORS["primary"]}; font-family: Georgia, \'Times New Roman\', serif; font-size: 28px; font-weight: 700; margin: 0 0 16px 0; letter-spacing: -0.02em;">'),

        # H2 - Section headers (TOP STORY, BREAKING, etc.)
        (r'<h2>', f'<h2 style="color: {COLORS["accent"]}; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; font-size: 12px; font-weight: 700; margin: 32px 0 12px 0; padding-bottom: 8px; text-transform: uppercase; letter-spacing: 0.1em; border-bottom: 2px solid {COLORS["accent"]};">'),

        # H3 - Subsection headers (theme names)
        (r'<h3>', f'<h3 style="color: {COLORS["primary"]}; font-family: Georgia, \'Times New Roman\', serif; font-size: 17px; font-weight: 700; margin: 20px 0 8px 0; letter-spacing: -0.01em;">'),

        # H4 - Minor headers
        (r'<h4>', f'<h4 style="color: {COLORS["primary"]}; font-family: Georgia, \'Times New Roman\', serif; font-size: 15px; font-weight: 700; margin: 16px 0 6px 0;">'),

        # Paragraphs
        (r'<p>', f'<p style="color: {COLORS["text"]}; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; font-size: 15px; line-height: 1.65; margin: 0 0 14px 0;">'),

        # Lists
        (r'<ul>', f'<ul style="margin: 0 0 16px 0; padding-left: 0; list-style: none;">'),
        (r'<ol>', f'<ol style="margin: 0 0 16px 0; padding-left: 20px;">'),
        (r'<li>', f'<li style="color: {COLORS["text"]}; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; font-size: 15px; line-height: 1.6; margin-bottom: 8px; padding-left: 0;">'),

        # Links
        (r'<a href="', f'<a style="color: {COLORS["accent"]}; text-decoration: none; font-weight: 500; border-bottom: 1px solid {COLORS["accent"]};" href="'),

        # Strong/Bold - for headlines within content
        (r'<strong>', f'<strong style="color: {COLORS["primary"]}; font-weight: 700;">'),

        # Emphasis
        (r'<em>', '<em style="font-style: italic;">'),

        # Tables
        (r'<table>', f'<table style="border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px;">'),
        (r'<th>', f'<th style="border: 1px solid {COLORS["border"]}; padding: 10px 12px; background: {COLORS["secondary"]}; text-align: left; font-weight: 600; color: {COLORS["primary"]};">'),
        (r'<td>', f'<td style="border: 1px solid {COLORS["border"]}; padding: 10px 12px; color: {COLORS["text"]};">'),

        # Code
        (r'<code>', f'<code style="background: {COLORS["secondary"]}; padding: 2px 6px; border-radius: 3px; font-family: \'SF Mono\', Monaco, monospace; font-size: 13px; color: {COLORS["primary"]};">'),
        (r'<pre>', f'<pre style="background: {COLORS["secondary"]}; padding: 16px; border-radius: 6px; overflow-x: auto; margin: 16px 0;">'),

        # Superscripts (citations) - gold accent color
        (r'<sup>', f'<sup style="color: {COLORS["accent"]}; font-weight: 600; font-size: 10px; vertical-align: super;">'),

        # Horizontal rules
        (r'<hr>', f'<hr style="border: none; border-top: 1px solid {COLORS["border"]}; margin: 24px 0;">'),
        (r'<hr />', f'<hr style="border: none; border-top: 1px solid {COLORS["border"]}; margin: 24px 0;" />'),
    ]

    for pattern, replacement in style_mappings:
        html = re.sub(pattern, replacement, html)

    # Post-process: Add bullet character for unordered list items
    html = re.sub(
        r'<li style="([^"]+)">',
        f'<li style="\\1"><span style="color: {COLORS["accent"]}; margin-right: 8px;">•</span>',
        html
    )

    return html


# =============================================================================
# CITATION HANDLING
# =============================================================================

def extract_and_number_citations(sections: list, evidence: list) -> tuple:
    """Extract citations from markdown, merge with evidence, assign numbers.

    Args:
        sections: List of markdown section strings
        evidence: List of evidence citation dicts/objects

    Returns:
        tuple: (modified_sections, citations_registry)
    """
    citations_registry = []
    url_to_number = {}

    for section in sections:
        if not section:
            continue

        for match in re.finditer(r'\[([^\]]+)\]\(([^\)]+)\)', section):
            link_text = match.group(1)
            url = match.group(2).strip()

            if url not in url_to_number:
                number = len(citations_registry) + 1
                url_to_number[url] = number
                citations_registry.append({
                    "number": number,
                    "url": url,
                    "text": link_text,
                    "snippet": None,
                    "date": None
                })

    for ev in evidence:
        if isinstance(ev, dict):
            url = ev.get('url', '').strip()
            title = ev.get('title', '')
            snippet = ev.get('snippet', '')
            date = ev.get('date', '')
        else:
            url = getattr(ev, 'url', '').strip()
            title = getattr(ev, 'title', '')
            snippet = getattr(ev, 'snippet', '')
            date = getattr(ev, 'date', '')

        if not url:
            continue

        if url in url_to_number:
            idx = url_to_number[url] - 1
            if not citations_registry[idx]['snippet'] and snippet:
                citations_registry[idx]['snippet'] = snippet
            if not citations_registry[idx]['date'] and date:
                citations_registry[idx]['date'] = date
        else:
            number = len(citations_registry) + 1
            url_to_number[url] = number
            citations_registry.append({
                "number": number,
                "url": url,
                "text": title,
                "snippet": snippet,
                "date": date
            })

    modified_sections = []
    for section in sections:
        if not section:
            modified_sections.append(section)
            continue

        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2).strip()
            number = url_to_number.get(url, '?')
            return f'{link_text}<sup>[{number}]</sup>'

        modified = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', replace_link, section)
        modified_sections.append(modified)

    return modified_sections, citations_registry


def render_citations_html(citations: list) -> str:
    """Render citations as a clean, professional sources list.

    Args:
        citations: List of citation dicts

    Returns:
        HTML string with sources section
    """
    if not citations:
        return ''

    citation_rows = []
    for citation in citations:
        number = citation.get('number', '?')
        url = citation.get('url', '#')
        date = citation.get('date', '')
        title = citation.get('text', citation.get('title', 'Source'))

        # Extract domain for display
        domain = url.split('/')[2] if url.startswith('http') and len(url.split('/')) > 2 else ''

        date_str = f' · {date}' if date else ''

        citation_rows.append(f'''
            <tr>
                <td style="padding: 8px 12px 8px 0; vertical-align: top; width: 30px; color: {COLORS["accent"]}; font-weight: 600; font-size: 13px;">[{number}]</td>
                <td style="padding: 8px 0; vertical-align: top;">
                    <div style="font-size: 14px; color: {COLORS["primary"]}; font-weight: 500; margin-bottom: 2px;">{title}</div>
                    <div style="font-size: 12px; color: {COLORS["text_light"]};">{domain}{date_str}</div>
                    <a href="{url}" style="font-size: 12px; color: {COLORS["accent"]}; text-decoration: none; word-break: break-all;">{url}</a>
                </td>
            </tr>
        ''')

    return f'''
        <div style="margin-top: 32px; padding-top: 24px; border-top: 2px solid {COLORS["accent"]};">
            <h2 style="color: {COLORS["accent"]}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; margin: 0 0 16px 0; text-transform: uppercase; letter-spacing: 0.1em;">Sources</h2>
            <table style="width: 100%; border-collapse: collapse;">
                {''.join(citation_rows)}
            </table>
        </div>
    '''


# =============================================================================
# HEADER COMPONENTS
# =============================================================================

def render_header(
    research_topic: str,
    strategy_slug: str,
    executed_at: str
) -> str:
    """Render the briefing header with logo, title, and metadata.

    Args:
        research_topic: The research topic
        strategy_slug: Strategy identifier
        executed_at: ISO timestamp

    Returns:
        HTML string for header
    """
    # Format date
    try:
        dt = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
        formatted_date = dt.strftime('%d. %B %Y')
        formatted_time = dt.strftime('%H:%M')
    except (ValueError, AttributeError):
        formatted_date = executed_at
        formatted_time = ""

    return f'''
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 24px;">
            <tr>
                <td style="vertical-align: middle; width: 60px;">
                    <img src="{LOGO_URL}" alt="Web Research Agent" width="48" height="48" style="display: block;">
                </td>
                <td style="vertical-align: middle; padding-left: 16px;">
                    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px; font-weight: 600; color: {COLORS["accent"]}; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 4px;">Daily Briefing</div>
                    <h1 style="font-family: Georgia, 'Times New Roman', serif; font-size: 24px; font-weight: 700; color: {COLORS["primary"]}; margin: 0; letter-spacing: -0.02em; line-height: 1.2;">{research_topic}</h1>
                </td>
            </tr>
        </table>
        <div style="display: flex; flex-wrap: wrap; gap: 16px; padding: 12px 16px; background: {COLORS["secondary"]}; border-radius: 4px; margin-bottom: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; color: {COLORS["text_light"]}; border-left: 3px solid {COLORS["accent"]};">
            <span><strong style="color: {COLORS["primary"]};">Datum:</strong> {formatted_date}</span>
            <span style="color: {COLORS["border"]};">|</span>
            <span><strong style="color: {COLORS["primary"]};">Strategie:</strong> {strategy_slug}</span>
            <span style="color: {COLORS["border"]};">|</span>
            <span><strong style="color: {COLORS["primary"]};">Generiert:</strong> {formatted_time} Uhr</span>
        </div>
    '''


def render_ai_notice() -> str:
    """Render the AI-generated content notice.

    Returns:
        HTML string for notice banner
    """
    return f'''
        <div style="background: {COLORS["warning_bg"]}; border-left: 3px solid {COLORS["warning_border"]}; padding: 12px 16px; margin-bottom: 24px; border-radius: 0 4px 4px 0;">
            <p style="margin: 0; color: {COLORS["warning_text"]}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.5;">
                <strong>Hinweis:</strong> Dieses Briefing wurde von einem KI-Agenten in Eigenrecherche erstellt. Bitte prüfen Sie alle Quellen sorgfältig.
            </p>
        </div>
    '''


# =============================================================================
# FOOTER
# =============================================================================

def render_footer() -> str:
    """Render the email footer.

    Returns:
        HTML string for footer
    """
    return f'''
        <div style="background: {COLORS["primary"]}; color: {COLORS["secondary"]}; padding: 24px 32px; text-align: center; border-radius: 0 0 6px 6px; margin-top: 32px;">
            <div style="font-family: Georgia, 'Times New Roman', serif; font-weight: 700; font-size: 14px; color: #ffffff; margin-bottom: 4px;">Web Research Agent</div>
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; color: {COLORS["text_light"]};">AI-powered research delivered to your inbox</div>
        </div>
    '''


# =============================================================================
# COMPLETE EMAIL WRAPPER
# =============================================================================

def create_email_html(research_topic: str, date_str: str, content_html: str) -> str:
    """Wrap content in complete email template.

    Args:
        research_topic: The research topic
        date_str: Date string
        content_html: Main content HTML

    Returns:
        Complete HTML email
    """
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{research_topic} - Daily Briefing</title>
    <style>
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
        body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; background-color: {COLORS["background"]}; }}
        .email-container {{ max-width: 680px; margin: 0 auto; background-color: {COLORS["white"]}; }}
        @media only screen and (max-width: 600px) {{
            .content {{ padding: 20px !important; }}
        }}
    </style>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{ font-family: Arial, Helvetica, sans-serif !important; }}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: {COLORS["background"]};">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: {COLORS["background"]};">
        <tr>
            <td align="center" style="padding: 24px 16px;">
                <table role="presentation" class="email-container" cellspacing="0" cellpadding="0" border="0" style="max-width: 680px; width: 100%; margin: 0 auto; background-color: {COLORS["white"]}; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <tr>
                        <td class="content" style="padding: 32px 40px;">
                            {content_html}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''


# =============================================================================
# MAIN RENDERING FUNCTION
# =============================================================================

def render_complete_email(
    research_topic: str,
    sections: list,
    citations: list,
    strategy_slug: str,
    evidence_count: int,
    executed_at: str,
    current_date: Optional[str] = None
) -> str:
    """Render a complete HTML newsletter email.

    This is the main function called from the API.

    Args:
        research_topic: The research topic/query
        sections: List of markdown section strings
        citations: List of citation dicts
        strategy_slug: Strategy identifier
        evidence_count: Number of sources analyzed
        executed_at: ISO timestamp
        current_date: Optional date string

    Returns:
        Complete HTML email string
    """
    if not current_date:
        current_date = datetime.utcnow().strftime('%d. %B %Y')

    is_daily_briefing = strategy_slug == 'daily_news_briefing'

    # Build content
    content_parts = []

    # 1. Header with logo, topic, metadata
    header_html = render_header(research_topic, strategy_slug, executed_at)
    content_parts.append(header_html)

    # 2. AI notice
    ai_notice = render_ai_notice()
    content_parts.append(ai_notice)

    # 3. Main content sections
    for section in sections:
        if section:
            section_html = markdown_to_html(section, is_daily_briefing)
            content_parts.append(section_html)

    # 4. Citations/Sources
    citations_html = render_citations_html(citations)
    if citations_html:
        content_parts.append(citations_html)

    # 5. Footer
    footer_html = render_footer()
    content_parts.append(footer_html)

    content_html = '\n'.join(content_parts)

    return create_email_html(research_topic, current_date, content_html)


def generate_strategy_subject_line(
    research_topic: str,
    strategy_slug: str,
    current_date: Optional[str] = None
) -> str:
    """Generate email subject line.

    Args:
        research_topic: The research topic
        strategy_slug: Strategy identifier
        current_date: Optional date string

    Returns:
        Formatted subject line
    """
    template_config = STRATEGY_TEMPLATES.get(strategy_slug, DEFAULT_TEMPLATE)
    prefix = template_config['subject_prefix']

    if not current_date:
        current_date = datetime.utcnow().strftime('%d.%m.%Y')

    if strategy_slug == 'daily_news_briefing':
        return f"{prefix} {research_topic} ({current_date})"

    return f"{prefix} {research_topic}"
