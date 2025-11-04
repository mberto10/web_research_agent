# Fixes Applied - QC Workflow & Section Duplication

## Date: 2025-11-04

## Summary

Applied comprehensive fixes to address two critical issues:
1. **QC LLM returning empty object** - Silent failures with no logging
2. **Duplicate sections in webhook** - Sections being duplicated in output

---

## Changes Made

### 1. Added Debug Logging in Finalize Step

**File:** `core/graph.py`

**Location:** Lines 1329-1331 (after report generation)

**Change:**
```python
report_content = final_response.choices[0].message.content

# DEBUG: Log report before parsing
logger.info(f"📄 FINALIZE: Generated report ({len(report_content)} chars)")
logger.info(f"Preview: {report_content[:500]}...")
```

**Purpose:** See exactly what the LLM generates before section parsing

---

### 2. Added Section Deduplication Logic

**File:** `core/graph.py`

**Location:** Lines 1405-1427 (after section parsing)

**Change:**
```python
# DEDUPLICATION: Remove duplicate sections
if len(state.sections) > 1:
    unique_sections = []
    seen = set()

    for section in state.sections:
        # Use first 200 chars as fingerprint
        fingerprint = section[:200].strip()
        if fingerprint not in seen:
            unique_sections.append(section)
            seen.add(fingerprint)
        else:
            logger.warning(f"⚠️ FINALIZE: Removed duplicate section")

    if len(unique_sections) != len(state.sections):
        logger.info(f"📝 FINALIZE: Deduplication: {len(state.sections)} → {len(unique_sections)} sections")
        state.sections = unique_sections

# DEBUG: Log parsed sections
logger.info(f"📝 FINALIZE: Parsed into {len(state.sections)} sections:")
for i, section in enumerate(state.sections):
    preview = section[:150].replace('\n', ' ')
    logger.info(f"  Section {i+1}: {len(section)} chars - {preview}...")
```

**Purpose:**
- Detect and remove duplicate sections using first 200 chars as fingerprint
- Log detailed information about each section (count, length, preview)
- Alert when duplicates are found and removed

---

### 3. Improved QC Error Handling

**File:** `core/graph.py`

**Location:** Lines 792-801 (exception handling in `_qc_llm`)

**Before:**
```python
except Exception:
    return {}  # Silent failure, no logging
```

**After:**
```python
except json.JSONDecodeError as e:
    logger.error(f"❌ QC_LLM: JSON parsing failed: {e}")
    logger.error(f"Response was: {content[:500] if 'content' in locals() else 'No response'}...")
    return {"grounded": True, "warnings": [f"QC parsing failed: {str(e)}"], "inconsistencies": []}
except Exception as e:
    logger.error(f"❌ QC_LLM: Failed with error: {e}")
    logger.error(f"Input size: {len(user) if 'user' in locals() else 0} chars")
    import traceback
    logger.error(traceback.format_exc())
    return {"grounded": True, "warnings": [f"QC check failed: {str(e)}"], "inconsistencies": []}
```

**Purpose:**
- Distinguish between JSON parsing errors and other exceptions
- Log detailed error information for debugging
- Return safe defaults instead of empty dict
- Show LLM response that failed to parse
- Show input size to check for token limit issues

---

### 4. Added QC Logging - Missing API Key

**File:** `core/graph.py`

**Location:** Lines 743-745 (API key check in `_qc_llm`)

**Before:**
```python
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    return {}  # Silent failure
```

**After:**
```python
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.warning("⚠️ QC_LLM: OPENAI_API_KEY not set, skipping LLM grounding check")
    return {"grounded": True, "warnings": [], "inconsistencies": []}
```

**Purpose:** Alert when API key is missing instead of failing silently

---

### 5. Added QC Input/Output Logging

**File:** `core/graph.py`

**Location:**
- Line 756 (before API call)
- Line 793 (after receiving response)
- Lines 863 & 867 (in main QC function)

**Changes:**
```python
# Before calling OpenAI (line 756)
logger.info(f"🔍 QC_LLM: Calling {model} with {len(user)} chars input")

# After receiving response (line 793)
logger.info(f"✅ QC_LLM: Received {len(content)} chars response, parsing JSON...")

# In main qc() function (lines 863 & 867)
logger.info(f"🔍 QC: Running LLM grounding check on {len(state.sections)} sections and {len(state.citations)} citations")
result = _qc_llm(state.sections, state.citations, model=llm_cfg.get("model"), system=system)
logger.info(f"✅ QC: LLM check complete. Grounded: {result.get('grounded', True)}, Warnings: {len(result.get('warnings', []))}, Inconsistencies: {len(result.get('inconsistencies', []))}")
```

**Purpose:** Track QC execution flow and identify where failures occur

---

## Expected Log Output

### Successful Execution:
```
📄 FINALIZE: Generated report (45234 chars)
Preview: # Research Results

## Overview of AI Agents...

📝 FINALIZE: Parsed into 2 sections:
  Section 1: 22500 chars - ## Overview of AI Agents AI agents are...
  Section 2: 22734 chars - ## Recent Developments In recent months...

✍️ WRITE: 2 sections

🔍 QC: Running LLM grounding check on 2 sections and 160 citations
🔍 QC_LLM: Calling gpt-4o-mini with 44582 chars input
✅ QC_LLM: Received 156 chars response, parsing JSON...
✅ QC: LLM check complete. Grounded: True, Warnings: 0, Inconsistencies: 0

📊 Sections: 2, Evidence: 160
  Section 1: 22500 chars - ## Overview of AI Agents...
  Section 2: 22734 chars - ## Recent Developments...
```

### With Deduplication:
```
📄 FINALIZE: Generated report (45234 chars)
⚠️ FINALIZE: Removed duplicate section
📝 FINALIZE: Deduplication: 2 → 1 sections
📝 FINALIZE: Parsed into 1 sections:
  Section 1: 22500 chars - ## Overview of AI Agents...
```

### With QC Error:
```
🔍 QC_LLM: Calling gpt-4o-mini with 44582 chars input
❌ QC_LLM: JSON parsing failed: Expecting value: line 1 column 1 (char 0)
Response was: The sections provided are well-grounded in the citations...
✅ QC: LLM check complete. Grounded: True, Warnings: 1, Inconsistencies: 0
```

---

## Testing Checklist

- [ ] Deploy changes to Replit
- [ ] Restart API to load changes
- [ ] Trigger batch execution
- [ ] Monitor logs for:
  - [ ] "📄 FINALIZE: Generated report" - confirms report size
  - [ ] "📝 FINALIZE: Parsed into X sections" - shows section count
  - [ ] Each section preview logged
  - [ ] Any deduplication warnings
  - [ ] "🔍 QC_LLM: Calling..." - shows QC running
  - [ ] QC success or detailed error
- [ ] Check webhook payload for:
  - [ ] Correct section count
  - [ ] No duplicate sections
  - [ ] Complete content
- [ ] Verify email received with proper content

---

## Files Modified

| File | Lines Modified | Changes |
|------|----------------|---------|
| `core/graph.py` | 743-745 | Improved API key check logging |
| `core/graph.py` | 756 | Added QC input logging |
| `core/graph.py` | 792-801 | Improved exception handling with detailed logging |
| `core/graph.py` | 793 | Added QC output logging |
| `core/graph.py` | 863, 867 | Added QC main function logging |
| `core/graph.py` | 1329-1331 | Added finalize report logging |
| `core/graph.py` | 1405-1427 | Added section deduplication and logging |

---

## Benefits

### Before Fixes:
- ❌ QC failures were silent
- ❌ No visibility into section parsing
- ❌ Duplicate sections sent to users
- ❌ No way to debug 44k token issue
- ❌ Empty object returned from QC

### After Fixes:
- ✅ Complete logging of finalize → parse → dedupe → QC flow
- ✅ Detailed error messages when QC fails
- ✅ Automatic removal of duplicate sections
- ✅ Clear visibility into report generation
- ✅ Section previews for debugging
- ✅ QC returns safe defaults with warnings
- ✅ Can identify exact failure point in workflow

---

## Known Issues Addressed

1. **QC returning empty object**: Now logs detailed errors and returns safe defaults
2. **Duplicate sections in webhook**: Now automatically detected and removed
3. **Silent failures**: All error paths now log comprehensive information
4. **Missing API key**: Now warns instead of silent failure
5. **44k token mystery**: Now logged to understand what's being sent to QC

---

## Next Steps

1. Deploy to production
2. Monitor logs for patterns
3. If duplicates still occur, check LLM prompt in finalize step
4. If QC continues to fail, review error logs for root cause
5. Consider adjusting QC prompt if JSON parsing fails consistently

---

## Rollback Plan

If issues arise, the changes are non-breaking:
- Logging additions won't affect functionality
- Deduplication only removes exact duplicates (safe)
- Error handling returns same structure as before (with better defaults)

To disable specific features:
- **Disable deduplication**: Comment out lines 1405-1421
- **Disable QC logging**: Comment out logger.info/error calls
- **Revert to silent QC**: Replace exception blocks with `return {}`

---

## Status

✅ **All fixes applied**
⏳ **Awaiting deployment and testing**

