# Email Formatting Solution

## Root Cause
The problem is in `/home/runner/workspace/strategies/daily_news_briefing.yaml` lines 46-108.

The LLM prompt is instructing the model to format output with **inline raw URLs** like:
- `Source: (Date) [URL]`
- `• Concrete fact or development (Date) [Source URL]`

This creates the unreadable wall of URLs you're seeing.

## The Fix

### Current Bad Format (lines 62-64):
```yaml
2. KEY DEVELOPMENTS
List 3-5 major news items, each formatted as:
• Headline: specific development (2-3 sentences with key facts, numbers, dates, people involved)
  Source: (Date) [URL]
```

### Should Be:
```yaml
2. KEY DEVELOPMENTS
List 3-5 major news items, each formatted as:
**Headline**: Specific development with key facts, numbers, dates, people [1][2]

Use numbered citations [1], [2], etc. to reference sources inline.
```

---

## Complete Replacement Strategy

Replace lines 46-108 with this improved prompt:

```yaml
    inputs:
      prompt: |
        Create a CONCISE daily news briefing from the following research results.

        Topic: {{topic}}
        Current Date: {{current_date}}
        Timeframe: {{start_date_natural}} to {{end_date_natural}}

        Research Evidence ({{evidence_count}} items total):
        {{evidence_text}}

        FORMAT INSTRUCTIONS:

        ## 1. Executive Summary

        Write 2-3 concise sentences highlighting the most important developments. Use numbered citations [1][2] for sources.

        ## 2. Key Developments

        List 3-5 major news items. Each formatted as:

        **Headline Title**
        Brief description with specific facts, numbers, dates, and people involved. [1][2]

        ## 3. Analysis by Theme

        Create 2-3 thematic sections based on actual news patterns (e.g., "Acquisition Activity", "Regulatory Changes", "Market Growth").

        For each theme:
        - **Theme: Specific Theme Name**
        - Overview: One sentence summary
        - Bullet points with concrete, newsworthy information:
          - Specific fact or development [1]
          - Another development with data [2][3]

        ## 4. Additional Coverage

        Brief bullets (max 5) for other relevant updates:
        - Specific news item [1]
        - Another item [2]

        ## 5. Sources

        List all cited sources:
        [1] Publication Name (YYYY-MM-DD): https://full-url.com
        [2] Another Source (YYYY-MM-DD): https://url.com

        ---

        CRITICAL RULES:

        ✓ DO:
        - Use numbered citations [1][2] inline - NEVER raw URLs
        - Put ALL URLs in Sources section at the end
        - Keep Executive Summary to 2-3 sentences max
        - Focus on NEWS: events, announcements, changes, data
        - Include specific numbers, dates, names, facts
        - Make themes specific to {{topic}}, not generic
        - Ensure each news item appears only ONCE
        - Add blank lines between sections for readability

        ✗ DON'T:
        - Include raw URLs like (Date) [https://...]
        - Write generic website descriptions
        - Add conversational text like "If you'd like..."
        - Duplicate information across sections
        - Exceed 2000 words total
        - Continue past the Sources section
```

---

## Why This Works

### Old Format Creates:
```
• Germany to buy 20 Airbus H145M helicopters for ~€1bn to complete rotary wing modernisation (2025-11-10) [https://www.aerotime.aero/articles/germany-additional-20-h145m-helicopters]
```
❌ **Unreadable**: URLs interrupt flow, dense text, hard to scan

### New Format Creates:
```
**Germany Orders Military Helicopters**
Berlin approved ~€1 billion procurement of 20 Airbus H145M helicopters for rotary wing modernization. [1]

[1] AeroTime (2025-11-10): https://www.aerotime.aero/articles/germany-additional-20-h145m-helicopters
```
✓ **Clean**: Numbered citations, URLs at end, scannable structure

---

## Implementation Steps

1. **Edit** `/home/runner/workspace/strategies/daily_news_briefing.yaml`
2. **Replace** lines 46-108 with the new prompt above
3. **Test** by running a daily briefing
4. **The email renderer** (`10_email_renderer_complete.js`) needs NO changes - it will automatically handle the improved markdown format

---

## Additional Recommendation

Consider adding this CSS to the email renderer for even better citation formatting:

```css
.citation-ref {
  color: #667eea;
  font-weight: 600;
  text-decoration: none;
  font-size: 0.9em;
  vertical-align: super;
}
```

Then modify the markdown converter to turn `[1]` into:
```html
<sup><a href="#cite-1" class="citation-ref">[1]</a></sup>
```
