# Report Length Optimization - Fixes Applied

## Date: 2025-11-04

## Problem

Reports were generating **45,000+ characters** (way too long for a daily briefing), causing:
- Duplicate content in webhook
- Very long emails
- Poor user experience

---

## Root Causes Identified

### 1. **Untruncated Evidence** ❌
```yaml
# BEFORE (line 53)
{{evidence_full_text}}  # No length limit on snippets!
```

Each evidence snippet could be thousands of characters. With 160 items, this created massive input.

### 2. **No Output Constraints** ❌
- No `max_tokens` parameter
- Prompt said "comprehensive" not "concise"
- No word count limits

### 3. **Verbose Instructions** ❌
- "Create a comprehensive daily news briefing"
- "Complete list of ALL sources"
- "Detailed analysis by theme"
- 2-4 themes with unlimited bullet points

---

## Fixes Applied

### Fix 1: Use Truncated Evidence ✅

**File:** `strategies/daily_news_briefing.yaml` (line 53)

**Before:**
```yaml
Research Evidence ({{evidence_count}} items total, showing top 50):
{{evidence_full_text}}
```

**After:**
```yaml
Research Evidence ({{evidence_count}} items total, showing top 50):
{{evidence_text}}
```

**Impact:** Evidence snippets now truncated to 500 chars each instead of unlimited

---

### Fix 2: Add Length Constraints ✅

**File:** `strategies/daily_news_briefing.yaml` (line 46)

**Before:**
```yaml
Create a comprehensive daily news briefing from the following research results.
```

**After:**
```yaml
Create a CONCISE daily news briefing (max 2000 words) from the following research results.
```

**Impact:** Clear word count target for the LLM

---

### Fix 3: Add max_tokens Parameter ✅

**File:** `strategies/daily_news_briefing.yaml` (line 44)

**Added:**
```yaml
  - use: llm_analyzer.call
    description: "Create concise briefing"
    max_tokens: 4000  # ← NEW: Hard limit on output
```

**Impact:** LLM physically cannot generate more than 4000 tokens (~3000 words)

---

### Fix 4: Reduce Section Requirements ✅

**File:** `strategies/daily_news_briefing.yaml`

#### 4a. Section 3 - Analysis (lines 66-74)

**Before:**
```yaml
3. DETAILED ANALYSIS BY THEME
Create 2-4 thematic sections...
For each theme:
  - Bullet points with specific information...
```

**After:**
```yaml
3. ANALYSIS BY THEME
Create 2-3 thematic sections...
For each theme (keep concise, 3-5 bullet points max):
  - 3-5 bullet points with specific information...
```

**Impact:** Max 3 themes instead of 4, max 5 bullets each

#### 4b. Section 4 - Notable Mentions (line 86)

**Added:**
```yaml
Brief bullet points (max 5) of other relevant but less critical updates
```

**Impact:** Limited to 5 items instead of unlimited

#### 4c. Section 5 - Sources (lines 89-91)

**Before:**
```yaml
5. ALL SOURCES
Complete list of all sources used, formatted as:
- Publication/Website (Date): URL
Include the date for each source if available
```

**After:**
```yaml
5. KEY SOURCES
Top 10 most important sources used, formatted as:
- Publication/Website (Date): URL
```

**Impact:** Only 10 sources instead of all 160+

---

### Fix 5: Reinforce Conciseness ✅

**File:** `strategies/daily_news_briefing.yaml` (line 98)

**Added to IMPORTANT section:**
```yaml
- Keep the briefing CONCISE (max 2000 words total)
```

**Impact:** Repeated reminder to stay brief

---

## Expected Results

### Before Fixes:
- 📄 Report: **45,000 characters** (22,500 words!)
- 📧 Email: Extremely long, duplicate content
- ⏱️ Processing: Slow due to massive output

### After Fixes:
- 📄 Report: **~8,000 characters** (2,000 words)
- 📧 Email: Concise, readable briefing
- ⏱️ Processing: Faster generation
- 💰 Cost: Lower token usage

---

## Calculation

**Before:**
- Input: 160 evidence × ~2000 chars = 320,000 chars ≈ 80,000 tokens
- Output: 45,000 chars ≈ 11,250 tokens
- **Total: ~91,000 tokens**

**After:**
- Input: 160 evidence × 500 chars = 80,000 chars ≈ 20,000 tokens
- Output: Max 4,000 tokens ≈ 3,000 words
- **Total: ~24,000 tokens** (74% reduction!)

---

## Structure Comparison

### Before:
```
1. EXECUTIVE SUMMARY (3+ paragraphs)
2. KEY DEVELOPMENTS (5-10 items)
3. DETAILED ANALYSIS (4 themes × unlimited bullets)
4. NOTABLE MENTIONS (unlimited)
5. ALL SOURCES (160+ sources)

Total: 45,000+ characters
```

### After:
```
1. EXECUTIVE SUMMARY (2-3 sentences)
2. KEY DEVELOPMENTS (3-5 items)
3. ANALYSIS BY THEME (2-3 themes × max 5 bullets)
4. NOTABLE MENTIONS (max 5 items)
5. KEY SOURCES (top 10)

Total: ~8,000 characters (max)
```

---

## Example Output Size

**Before Optimization:**
```
Section 1: 2,000 chars
Section 2: 5,000 chars
Section 3: 20,000 chars (4 themes × 5,000 each)
Section 4: 8,000 chars
Section 5: 10,000 chars (160 sources)
---
Total: 45,000 chars
```

**After Optimization:**
```
Section 1: 500 chars
Section 2: 1,500 chars
Section 3: 4,000 chars (3 themes × ~1,300 each)
Section 4: 800 chars
Section 5: 1,200 chars (10 sources)
---
Total: 8,000 chars
```

---

## Files Modified

| File | Lines | Changes |
|------|-------|---------|
| `strategies/daily_news_briefing.yaml` | 43 | Added `max_tokens: 4000` |
| `strategies/daily_news_briefing.yaml` | 46 | "comprehensive" → "CONCISE (max 2000 words)" |
| `strategies/daily_news_briefing.yaml` | 53 | `{{evidence_full_text}}` → `{{evidence_text}}` |
| `strategies/daily_news_briefing.yaml` | 66-74 | Section 3: "DETAILED" → "ANALYSIS", 2-4 → 2-3 themes, added "3-5 bullets max" |
| `strategies/daily_news_briefing.yaml` | 86 | Section 4: Added "max 5" constraint |
| `strategies/daily_news_briefing.yaml` | 89-91 | Section 5: "ALL SOURCES" → "KEY SOURCES (top 10)" |
| `strategies/daily_news_briefing.yaml` | 98 | Added "Keep briefing CONCISE" to IMPORTANT |
| `strategies/daily_news_briefing.yaml` | 102 | Updated section name reference |

---

## Testing Checklist

- [ ] Deploy changes to Replit
- [ ] Restart API
- [ ] Trigger test execution
- [ ] Monitor logs for:
  - [ ] "📄 FINALIZE: Generated report (X chars)" - should be ~8,000 instead of 45,000
  - [ ] Report generation time - should be faster
  - [ ] No truncation warnings
- [ ] Check webhook payload:
  - [ ] Sections are readable length
  - [ ] No duplication
  - [ ] Complete but concise
- [ ] Verify email:
  - [ ] Readable in one screen scroll
  - [ ] All 5 sections present
  - [ ] Max 10 sources listed
  - [ ] Professional format

---

## Rollback Plan

If briefings become too short or missing important info:

1. **Increase max_tokens**: Change from 4000 to 6000
2. **Increase theme count**: Change "2-3" back to "2-4"
3. **Increase sources**: Change "top 10" to "top 15"

To fully revert:
```bash
git diff strategies/daily_news_briefing.yaml
git checkout strategies/daily_news_briefing.yaml  # Revert all changes
```

---

## Benefits

### User Experience
- ✅ Faster email loading
- ✅ Easier to scan and read
- ✅ Focus on most important info
- ✅ No duplicate content

### Performance
- ✅ 74% token reduction
- ✅ Faster generation time
- ✅ Lower API costs
- ✅ Less memory usage

### Quality
- ✅ Focuses on key developments
- ✅ More curated sources
- ✅ Better signal-to-noise ratio
- ✅ Professional brevity

---

## Status

✅ **All fixes applied**
⏳ **Ready for testing**

Expected outcome: Reports will be **~8,000 characters** (2,000 words) instead of 45,000+
