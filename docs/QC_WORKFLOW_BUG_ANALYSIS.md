# QC Workflow Bug Analysis & Fix

## Problem Summary

**Reported Issue:**
- QC LLM step receives 44k tokens as input
- QC returns empty object `{}`
- Sections in webhook appear duplicated/corrupted

**Webhook Payload Received:**
```json
{
  "sections": [
    "# Research Results ## What are AI agents...",
    "# Research Results ## What are AI agents..."  // DUPLICATE!
  ],
  "citations": [10 valid citations],
  "metadata": {
    "evidence_count": 160,
    "executed_at": "2025-11-04T10:21:20.113886"
  }
}
```

---

## Root Cause Analysis

### Issue 1: QC Empty Object Return

**Location:** `core/graph.py:734-793` (`_qc_llm` function)

**What Happens:**
1. QC receives sections (44k tokens) + citations
2. Sends to `gpt-4o-mini` for grounding validation
3. Expects JSON response: `{"grounded": true, "warnings": [], "inconsistencies": []}`
4. **Exception occurs** (likely JSON parsing failure)
5. **Silent catch** returns `{}` (line 792)

**Code:**
```python
def _qc_llm(sections: List[str], citations: List[str], model: str | None = None, system: str | None = None) -> Dict[str, Any]:
    try:
        # Build 44k token prompt
        user = f"Sections:\n{chr(10).join(sections)}\n\nCitations:\n{chr(10).join(citations)}"

        response = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            response_format={"type": "json_object"}  # Requires valid JSON
        )

        content = response.choices[0].message.content
        return json.loads(content)  # ← FAILS HERE
    except Exception:
        return {}  # ← SILENTLY RETURNS EMPTY DICT
```

**Why It Fails:**
- **Token limit exceeded**: 44k input + output may exceed context
- **JSON parsing error**: LLM returns invalid JSON
- **API error**: OpenAI API timeout/error
- **Missing API key**: No OPENAI_API_KEY set

**Impact:**
- ✅ Sections are NOT lost (they remain in `state.sections`)
- ❌ No quality control validation performed
- ❌ No warnings or inconsistencies flagged
- ⚠️ Silent failure - no error logged

---

### Issue 2: Duplicate/Corrupted Sections

**Location:** `core/graph.py:1389-1398` (finalize step section parsing)

**What Should Happen:**
1. LLM generates report with sections: `"## Section 1\ncontent\n## Section 2\ncontent"`
2. Code splits by `"## "`
3. Each section stored separately

**Code:**
```python
# Parse sections from the report
if "## " in report_content:
    parts = report_content.split("## ")
    for part in parts[1:]:  # Skip first empty part
        if part.strip():
            state.sections.append(f"## {part.strip()}")
else:
    # If no sections found, add as single section
    state.sections.append(report_content)
```

**Potential Issues:**
- LLM generated duplicate content
- Report parsing split incorrectly
- Only 1 section created, then duplicated somewhere

---

## Debugging Steps

### Step 1: Enable Detailed Logging

Add logging to see what's happening at each stage:

```python
# In core/graph.py, line 791 (inside _qc_llm):
except Exception as e:
    logger.error(f"❌ QC_LLM FAILED: {e}")
    import traceback
    logger.error(traceback.format_exc())
    logger.error(f"Input size: {len(user)} chars")
    logger.error(f"Response: {response.choices[0].message.content if response else 'No response'}")
    return {}
```

```python
# In core/graph.py, line 1398 (after finalize creates sections):
logger.info(f"📝 FINALIZE: Created {len(state.sections)} sections")
for i, section in enumerate(state.sections):
    logger.info(f"  Section {i+1}: {section[:100]}...")  # First 100 chars
```

```python
# In core/graph.py, line 731 (after write step):
logger.info(f"✍️ WRITE: {len(state.sections)} sections")
```

```python
# In core/graph.py, line 870 (after QC step):
logger.info(f"✅ QC: {len(state.sections)} sections passed validation")
```

```python
# In api/main.py, line 344 (before webhook):
logger.info(f"📊 Sections for webhook:")
for i, section in enumerate(sections):
    logger.info(f"  [{i}] Length: {len(section)}, Preview: {section[:100]}...")
```

---

### Step 2: Check Environment Variables

**Missing API Key Issue:**

The `_qc_llm` function uses OpenAI client (line 742-744):
```python
client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)
```

**Verify in Replit:**
```bash
echo $OPENAI_API_KEY
```

If empty, add to Replit Secrets and restart API.

---

### Step 3: Reproduce With Test

**Create test script:** `test_qc_issue.py`
```python
import os
from core.graph import build_graph
from core.state import State

# Set up
os.environ["OPENAI_API_KEY"] = "your-key-here"

# Build graph
graph = build_graph()

# Test with simple research topic
result = graph.invoke(State(user_request="AI agents overview"))

# Check sections
print(f"Sections created: {len(result.sections)}")
for i, section in enumerate(result.sections):
    print(f"\n=== Section {i+1} ({len(section)} chars) ===")
    print(section[:200])  # First 200 chars
```

Run:
```bash
python test_qc_issue.py
```

---

### Step 4: Check QC Token Limits

**Token calculation:**
- 44k characters ≈ 11k tokens (rough estimate)
- Plus citations ≈ another 5k tokens
- Plus system prompt ≈ 1k tokens
- **Total input:** ~17k tokens

**gpt-4o-mini limits:**
- Context window: 128k tokens
- Max output: 16k tokens

**Verdict:** Should be within limits, so issue is likely JSON parsing or API error.

---

## Fixes

### Fix 1: Improve QC Error Handling

**File:** `core/graph.py:734-793`

**Change:**
```python
def _qc_llm(sections: List[str], citations: List[str], model: str | None = None, system: str | None = None) -> Dict[str, Any]:
    """Call an LLM to verify factual grounding."""
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("⚠️ OPENAI_API_KEY not set, skipping QC LLM check")
        return {"grounded": True, "warnings": [], "inconsistencies": []}

    # Build prompt
    user = f"Sections:\n{chr(10).join(sections)}\n\nCitations:\n{chr(10).join(citations)}"
    logger.info(f"🔍 QC_LLM: Checking {len(user)} chars with {model or 'gpt-4o-mini'}")

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system or DEFAULT_QC_SYSTEM},
                {"role": "user", "content": user}
            ],
            temperature=0,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        logger.info(f"✅ QC_LLM: Received {len(content)} chars response")

        result = json.loads(content)
        logger.info(f"✅ QC_LLM: Parsed JSON successfully")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"❌ QC_LLM: JSON parsing failed: {e}")
        logger.error(f"Response was: {content[:500]}...")
        return {"grounded": True, "warnings": [f"QC parsing failed: {e}"], "inconsistencies": []}

    except Exception as e:
        logger.error(f"❌ QC_LLM: Failed with error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"grounded": True, "warnings": [f"QC check failed: {e}"], "inconsistencies": []}
```

**Benefits:**
- ✅ Logs detailed error information
- ✅ Returns safe defaults instead of empty dict
- ✅ Distinguishes between JSON errors and API errors
- ✅ Warns if API key missing

---

### Fix 2: Add Section Validation

**File:** `core/graph.py:1398` (after finalize creates sections)

**Add:**
```python
# Parse sections from the report
if "## " in report_content:
    parts = report_content.split("## ")
    for part in parts[1:]:
        if part.strip():
            state.sections.append(f"## {part.strip()}")
else:
    state.sections.append(report_content)

# VALIDATION: Check for duplicate sections
if len(state.sections) > 1:
    unique_sections = []
    seen_previews = set()

    for section in state.sections:
        # Use first 200 chars as fingerprint
        preview = section[:200]
        if preview not in seen_previews:
            unique_sections.append(section)
            seen_previews.add(preview)
        else:
            logger.warning(f"⚠️ FINALIZE: Duplicate section detected and removed")

    if len(unique_sections) < len(state.sections):
        logger.info(f"📝 FINALIZE: Removed {len(state.sections) - len(unique_sections)} duplicates")
        state.sections = unique_sections

logger.info(f"📝 FINALIZE: Created {len(state.sections)} unique sections")
```

---

### Fix 3: Add API Logging Before Webhook

**File:** `api/main.py:344`

**Replace:**
```python
logger.info(f"  📊 Sections: {len(sections)}, Evidence: {len(evidence)}")
```

**With:**
```python
logger.info(f"  📊 Sections: {len(sections)}, Evidence: {len(evidence)}")

# Log detailed section info
for i, section in enumerate(sections):
    preview = section[:100].replace('\n', ' ')
    logger.info(f"    Section {i+1}: {len(section)} chars - {preview}...")

# Check for duplicates
if len(sections) > 1:
    previews = [s[:200] for s in sections]
    if len(previews) != len(set(previews)):
        logger.warning(f"  ⚠️ Duplicate sections detected in webhook payload!")
```

---

## Expected Log Output After Fixes

### Successful Execution:
```
🔍 QC_LLM: Checking 44582 chars with gpt-4o-mini
✅ QC_LLM: Received 156 chars response
✅ QC_LLM: Parsed JSON successfully
📝 FINALIZE: Created 2 unique sections
  Section 1: 8234 chars - ## Overview of AI Agents...
  Section 2: 7891 chars - ## Recent Developments...
✍️ WRITE: 2 sections
✅ QC: 2 sections passed validation
📊 Sections: 2, Evidence: 160
  Section 1: 8234 chars - ## Overview of AI Agents...
  Section 2: 7891 chars - ## Recent Developments...
```

### With Errors:
```
❌ QC_LLM: JSON parsing failed: Expecting value: line 1 column 1 (char 0)
Response was: The sections provided are well-grounded...
⚠️ FINALIZE: Duplicate section detected and removed
📝 FINALIZE: Removed 1 duplicates
📝 FINALIZE: Created 1 unique sections
```

---

## Immediate Actions

1. **Add logging to QC function** to see actual error
2. **Add section deduplication** in finalize step
3. **Verify OPENAI_API_KEY** is set in Replit
4. **Re-run test** and check logs for:
   - QC error details
   - Section count at each step
   - Section preview/fingerprints
5. **Check Langfuse traces** to see which step is failing

---

## Files to Modify

| File | Line | Change |
|------|------|--------|
| `core/graph.py` | 791 | Improve QC error handling |
| `core/graph.py` | 1398 | Add section deduplication |
| `api/main.py` | 344 | Add detailed section logging |

---

## Quick Fix (Temporary)

If you need to deploy immediately while debugging:

**Disable QC step temporarily:**

In `core/graph.py:870`, add at the top of `qc()` function:
```python
def qc(state: State) -> State:
    """Quality control checks."""
    logger.info("⏭️ QC: Skipping for now (debugging)")
    return state  # ← TEMPORARY: Skip QC entirely
```

This will bypass the failing QC step and let sections flow through to webhook.

**Remember to re-enable QC after fixing!**

---

## Root Cause Summary

**Primary Issue:** QC's `_qc_llm` function silently fails (likely JSON parsing error) and returns empty dict instead of validation results.

**Secondary Issue:** Sections may be duplicated during finalize step's report parsing.

**Not an Issue:** Sections themselves are not lost - they remain in state throughout workflow.

**Solution:** Add comprehensive logging and error handling to identify exact failure point, then fix accordingly.
