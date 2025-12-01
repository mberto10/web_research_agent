#!/usr/bin/env python3
"""Test script for the new email template engine."""

import sys
sys.path.insert(0, '.')

from api.email_templates import (
    render_complete_email,
    generate_strategy_subject_line,
    extract_and_number_citations,
    STRATEGY_TEMPLATES
)
from datetime import datetime, timezone

def test_strategy_templates():
    """Test that all strategies have proper configurations."""
    print("Testing strategy template configurations...")

    # FAZ-style templates don't use icons - just clean text prefixes
    required_keys = ['title_template', 'subtitle_template', 'subject_prefix']

    for slug, config in STRATEGY_TEMPLATES.items():
        for key in required_keys:
            assert key in config, f"Missing {key} in {slug}"
        print(f"  ✅ {slug}")

    print(f"\n✅ All {len(STRATEGY_TEMPLATES)} strategy templates validated\n")


def test_citation_extraction():
    """Test citation extraction and numbering."""
    print("Testing citation extraction...")

    sections = [
        "Here is some text with a [link](https://example.com/1) and another [reference](https://example.com/2).",
        "More content with the [same link](https://example.com/1) again."
    ]

    evidence = [
        {
            "url": "https://example.com/3",
            "title": "New Source",
            "snippet": "This is a snippet from the new source."
        }
    ]

    modified_sections, citations = extract_and_number_citations(sections, evidence)

    assert len(citations) == 3, f"Expected 3 citations, got {len(citations)}"
    assert "<sup>[1]</sup>" in modified_sections[0], "Citation 1 not replaced"
    assert "<sup>[2]</sup>" in modified_sections[0], "Citation 2 not replaced"
    assert "<sup>[1]</sup>" in modified_sections[1], "Duplicate citation not using same number"

    print(f"  ✅ Extracted {len(citations)} unique citations")
    print(f"  ✅ Markdown links replaced with superscripts")
    print()


def test_subject_line_generation():
    """Test strategy-aware subject line generation (FAZ-style, no emojis)."""
    print("Testing subject line generation...")

    # FAZ-style: Clean, professional subject lines without emojis
    test_cases = [
        ("news/real_time_briefing", "Breaking News", "Breaking News:"),
        ("company/dossier", "Apple Inc", "Company Report:"),
        ("financial_research", "Stock Analysis", "Financial Analysis:"),
        ("daily_news_briefing", "Tech News", "Daily Briefing:"),
        ("unknown_strategy", "Topic", "Research Update:"),
    ]

    for strategy, topic, expected_prefix in test_cases:
        subject = generate_strategy_subject_line(topic, strategy)
        assert subject.startswith(expected_prefix), f"Expected {expected_prefix}, got {subject}"
        print(f"  ✅ {strategy}: {subject}")

    print()


def test_complete_email_rendering():
    """Test complete email rendering for each strategy."""
    print("Testing complete email rendering...")

    # Sample data
    sections = [
        "# Main Findings\n\nThis is the main content with **bold** and *italic* text.",
        "## Key Points\n\n- Point one\n- Point two\n- Point three",
    ]

    citations = [
        {"number": 1, "url": "https://example.com/1", "text": "Source 1", "date": "2025-11-15"},
        {"number": 2, "url": "https://example.com/2", "text": "Source 2", "date": "2025-11-10"},
    ]

    executed_at = datetime.utcnow().isoformat()
    current_date = "November 17, 2025"

    # Test a few key strategies
    strategies_to_test = [
        "daily_news_briefing",
        "news/real_time_briefing",
        "company/dossier",
        "financial_research",
    ]

    for strategy_slug in strategies_to_test:
        html = render_complete_email(
            research_topic="Test Research Topic",
            sections=sections,
            citations=citations,
            strategy_slug=strategy_slug,
            evidence_count=5,
            executed_at=executed_at,
            current_date=current_date
        )

        # Validate HTML structure (FAZ-style)
        assert "<!DOCTYPE html>" in html, "Missing DOCTYPE"
        assert "<html" in html, "Missing html tag"
        assert "Web Research Agent" in html, "Missing footer branding"
        assert "Quellen" in html, "Missing citations section"
        assert "Test Research Topic" in html, "Missing research topic"
        # FAZ design uses black rules, not gradients
        assert "#1a1a1a" in html, "Missing FAZ primary color (Cod Gray)"

        print(f"  ✅ {strategy_slug}: {len(html)} chars")

    # Save one sample for inspection
    sample_html = render_complete_email(
        research_topic="Breaking News: Major Tech Announcement",
        sections=sections,
        citations=citations,
        strategy_slug="news/real_time_briefing",
        evidence_count=5,
        executed_at=executed_at,
        current_date=current_date
    )

    with open("/tmp/sample_email.html", "w") as f:
        f.write(sample_html)

    print(f"\n  📧 Sample email saved to /tmp/sample_email.html")
    print(f"     Size: {len(sample_html):,} characters")
    print()


def test_markdown_conversion():
    """Test markdown to HTML conversion with FAZ styling."""
    print("Testing markdown to HTML conversion...")

    from api.email_templates import markdown_to_html

    markdown = """
# Heading 1

This is a paragraph with **bold** and *italic* text.

## Heading 2

- Item 1
- Item 2
- Item 3

### Heading 3

A [link](https://example.com) here.
"""

    html = markdown_to_html(markdown)

    # Check for FAZ-styled elements (using #1a1a1a Cod Gray)
    assert 'color: #1a1a1a' in html, "H1 not styled with FAZ primary color"
    assert 'Source Serif' in html or 'Georgia' in html, "Missing serif font for headlines"
    assert '<strong style="color: #1a1a1a' in html, "Strong not styled with FAZ primary"
    assert 'text-decoration: underline' in html, "Links not styled"
    assert '<ul style="margin: 0 0 24px 0;' in html, "Lists not styled"

    print("  ✅ All markdown elements converted with FAZ inline styles")
    print()


def test_email_wrapper_boundaries():
    """Ensure email wrapper has no stray leading/ending paragraph tags."""
    print("Testing email wrapper boundaries...")

    from api.email_templates import render_complete_email

    html = render_complete_email(
        research_topic="Boundary Test",
        sections=["Test body"],
        citations=[],
        strategy_slug="daily_news_briefing",
        evidence_count=0,
        executed_at=datetime.now(timezone.utc).isoformat(),
        current_date="November 17, 2025"
    )

    stripped = html.lstrip()
    assert stripped.startswith("<!DOCTYPE html>"), "Email HTML should start with DOCTYPE, found leading characters"
    assert not stripped.startswith("</p>"), "Email HTML should not start with stray closing paragraph tag"
    assert not html.rstrip().endswith("<p>"), "Email HTML should not end with stray opening paragraph tag"

    print("  ✅ Wrapper starts at DOCTYPE and ends cleanly")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Email Template Engine Test Suite")
    print("=" * 60)
    print()

    test_strategy_templates()
    test_citation_extraction()
    test_subject_line_generation()
    test_markdown_conversion()
    test_email_wrapper_boundaries()
    test_complete_email_rendering()

    print("=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
