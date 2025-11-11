# Email Format Transformation Test

## BEFORE (Current Bad Format)

```
1. EXECUTIVE SUMMARY
The U.S. Department of Defense announced sweeping acquisition reforms and senior leadership pressure on industry to speed delivery, prompting legal-analysis commentary (DoD reforms) (2025-11-11) [https://www.wilmerhale.com/en/insights/client-alerts/20251111-defense-acquisition-system-reforms-legal-implications-for-industry]; major industry M&A: private equity Arcline agreed to buy Novaria Group for $2.2 billion in an all-cash deal (2025-11-11) [https://www.govconwire.com/articles/arcline-2b-acquisition-novaria-aerospace].

2. KEY DEVELOPMENTS
• DoD announces sweeping acquisition reforms and industry urged to accelerate delivery: Department of Defense reforms intended to speed capability delivery were publicized and legal-implication analysis published on Nov 11; Secretary Pete Hegseth has publicly pressed defense executives to be "faster, more agile and less risk averse" in remarks tied to these changes. Source: WilmerHale (2025-11-11) [https://www.wilmerhale.com/en/insights/client-alerts/20251111-defense-acquisition-system-reforms-legal-implications-for-industry]
```

**Problems:**
- ❌ Raw URLs break reading flow
- ❌ Dense wall of text
- ❌ No visual hierarchy
- ❌ Impossible to scan quickly

---

## AFTER (New Clean Format)

```
## Executive Summary

The U.S. Department of Defense announced sweeping acquisition reforms pressuring industry to accelerate delivery timelines [1]. Private equity firm Arcline agreed to acquire Novaria Group for $2.2B, continuing mid-tier aerospace consolidation [2].

---

## Key Developments

**DoD Acquisition Reforms Announced**
Secretary Hegseth publicly pressed defense executives to be "faster, more agile and less risk averse" alongside new acquisition reforms aimed at accelerating capability delivery. Legal analysis published November 11 highlights implications for contractors. [1][3]

**Arcline to Acquire Novaria for $2.2B**
Private equity firm Arcline reached an all-cash agreement to buy aerospace supplier Novaria Group, following its 2024 Kaman acquisition and consolidating mid-tier aerospace supply capacity. [2]

---

## Sources

[1] WilmerHale (2025-11-11): https://www.wilmerhale.com/en/insights/client-alerts/20251111-defense-acquisition-system-reforms-legal-implications-for-industry
[2] GovConWire (2025-11-11): https://www.govconwire.com/articles/arcline-2b-acquisition-novaria-aerospace
[3] Breaking Defense (2025-11-07): https://breakingdefense.com/2025/11/hegseth-presses-defense-execs-to-move-faster
```

**Benefits:**
- ✅ Clean, scannable text
- ✅ Numbered citations don't interrupt reading
- ✅ Clear visual hierarchy with bold headlines
- ✅ All URLs collected at the end
- ✅ Clickable superscript citations link to sources

---

## How It Works in HTML Email

The email renderer will now convert:

### Inline Citations
```markdown
Secretary Hegseth pressed executives [1][3]
```
→ Becomes:
```html
Secretary Hegseth pressed executives <sup><a href="#cite-1">[1]</a></sup><sup><a href="#cite-3">[3]</a></sup>
```

### Sources Section
```markdown
[1] WilmerHale (2025-11-11): https://www.wilmerhale.com/...
```
→ Becomes:
```html
<span id="cite-1">
  <strong>[1]</strong> WilmerHale (2025-11-11):
  <a href="https://www.wilmerhale.com/...">https://www.wilmerhale.com/...</a>
</span>
```

### Result
- Citations are **clickable** and jump to the source
- Sources have **anchor IDs** so links work
- Everything is **hyperlinked** for easy access
- Text is **readable** without URL clutter

---

## Changes Made

### 1. `/home/runner/workspace/strategies/daily_news_briefing.yaml`
- ✅ Updated prompt to use numbered citations `[1][2]` instead of inline URLs
- ✅ Added clear section separators with `---`
- ✅ Emphasized formatting rules: NO raw URLs in body text
- ✅ All URLs must go in Sources section

### 2. `/home/runner/workspace/docs/langdock_actions/10_email_renderer_complete.js`
- ✅ Added citation converter: `[1]` → `<sup><a href="#cite-1">[1]</a></sup>`
- ✅ Added source formatter with anchor IDs for jumpable links
- ✅ Added horizontal rule support for `---` separators
- ✅ Citations now styled as superscript with proper linking

---

## Next Steps

To test the new format:

1. **Run a daily briefing:**
   ```bash
   python run_daily_briefing.py
   ```

2. **Check the webhook output** - should now have numbered citations instead of inline URLs

3. **Verify email formatting** - citations should be clickable superscripts linking to sources at bottom

The email will now be **clean, professional, and actually readable**!
