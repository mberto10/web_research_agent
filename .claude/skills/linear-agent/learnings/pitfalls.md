# Common Pitfalls and How to Avoid Them

## Overview

This document captures common mistakes when working with the Linear API and how to avoid them in the Linear Agent Skill.

---

## 1. ID vs Name Resolution

### Pitfall
Providing team/state/label names directly to the API instead of resolving to IDs first.

**Problem:**
```python
# ❌ This fails - API expects IDs
client.create_issue(team="Backend Team", title="Test")
```

**Solution:**
```python
# ✅ Resolve name to ID first
team = client.get_team_by_name("Backend Team")
client.create_issue(team_id=team["id"], title="Test")
```

**In the Skill:**
- Always resolve names to IDs before API calls
- Cache team/label mappings to reduce API calls
- Provide clear error messages when names don't match

---

## 2. Case Sensitivity

### Pitfall
Assuming team/label names are case-insensitive.

**Problem:**
```python
# ❌ May not match if actual name is "Backend Team"
team = client.get_team_by_name("backend team")
```

**Solution:**
```python
# ✅ Use case-insensitive matching
teams = client.list_teams()
team = next((t for t in teams if t["name"].lower() == "backend team".lower()), None)
```

**In the Skill:**
- All name lookups use `.lower()` comparison
- Show matched team name to confirm: "Found team: Backend Team"

---

## 3. Rate Limiting

### Pitfall
Making too many API calls in rapid succession.

**Problem:**
```python
# ❌ This will hit rate limits quickly
for i in range(2000):
    client.create_issue(...)
```

**Solution:**
```python
# ✅ Use bulk operations and throttling
client._check_rate_limit()  # Built into linear_client.py
# OR use bulk_operations.py for batches
```

**In the Skill:**
- LinearClient automatically throttles at 1400 req/hour
- Use batch operations for multiple issues
- Show progress updates during long operations

---

## 4. Missing Required Fields

### Pitfall
Not providing required fields when creating issues.

**Problem:**
```python
# ❌ Missing teamId
client.create_issue(title="Test")
```

**Solution:**
```python
# ✅ Validate required fields first
if not team_id or not title:
    raise ValueError("teamId and title are required")
client.create_issue(team_id=team_id, title=title)
```

**In the Skill:**
- create_issue.py validates required fields
- Prompt user for missing information
- Use templates with smart defaults

---

## 5. State Transition Validation

### Pitfall
Attempting invalid state transitions (e.g., Backlog → Done without In Progress).

**Problem:**
```python
# ❌ May violate team workflow rules
client.update_issue(issue_id, state_id="completed_state_id")
```

**Solution:**
```python
# ✅ Check current state and validate transition
current = client.get_issue(issue_id)
current_state = current["state"]["name"]
# Validate transition logic here
```

**In the Skill:**
- Show current state before updating
- Warn about potentially invalid transitions
- Add comment explaining state change

---

## 6. Label ID vs Label Name

### Pitfall
Providing label names instead of IDs in create/update operations.

**Problem:**
```python
# ❌ API expects IDs, not names
client.create_issue(team_id=team_id, title="Test", labelIds=["bug", "p1"])
```

**Solution:**
```python
# ✅ Resolve label names to IDs
all_labels = client.list_labels(team_id=team_id)
label_map = {l["name"].lower(): l["id"] for l in all_labels}
label_ids = [label_map["bug"], label_map["p1"]]
client.create_issue(team_id=team_id, title="Test", labelIds=label_ids)
```

**In the Skill:**
- create_issue.py has `get_label_ids()` helper
- Warns when labels don't exist
- Shows available labels for selection

---

## 7. Markdown Formatting

### Pitfall
Not escaping special characters in descriptions or breaking markdown syntax.

**Problem:**
```python
# ❌ Broken markdown
description = "Price is $100 (not $50)"  # Parens break if not escaped
```

**Solution:**
```python
# ✅ Use proper markdown formatting
description = "Price is \\$100 (not \\$50)"
# OR use code blocks for literal text
description = "`Price is $100 (not $50)`"
```

**In the Skill:**
- Templates use markdown formatting guides
- Escape special characters in user input
- Validate markdown before creating issues

---

## 8. Pagination Limits

### Pitfall
Assuming all results are returned in a single query.

**Problem:**
```python
# ❌ Only gets first 50 issues (default limit)
issues = client.query_issues(team_id=team_id)
```

**Solution:**
```python
# ✅ Handle pagination
all_issues = []
cursor = None
while True:
    result = client.query_issues(team_id=team_id, after=cursor)
    all_issues.extend(result["nodes"])
    if not result["pageInfo"]["hasNextPage"]:
        break
    cursor = result["pageInfo"]["endCursor"]
```

**In the Skill:**
- query_issues.py uses `limit` parameter (default 50)
- Warn when result set is truncated
- Offer to export full results if > 50 issues

---

## 9. Stale Data

### Pitfall
Caching issue/team/label data too long and using stale information.

**Problem:**
```python
# ❌ Cache never refreshed
teams = client.list_teams()  # Cache this
# ... 1 hour later ...
# teams may be stale if new teams were added
```

**Solution:**
```python
# ✅ Refresh data when needed
if not cached_teams or cache_expired():
    cached_teams = client.list_teams()
```

**In the Skill:**
- Don't cache across user requests
- Fetch fresh data for each operation
- Use verbose mode to show data freshness

---

## 10. Error Message Clarity

### Pitfall
Showing raw API errors to users without context.

**Problem:**
```python
# ❌ Cryptic error
"GraphQL error: Variable $input of type IssueCreateInput! was provided invalid value"
```

**Solution:**
```python
# ✅ Translate to user-friendly message
try:
    client.create_issue(...)
except LinearAPIError as e:
    if "invalid value" in str(e):
        print("Issue creation failed: Check that all required fields are provided")
        print(f"Details: {e}")
```

**In the Skill:**
- All helper scripts catch LinearAPIError
- Translate to actionable user messages
- Include troubleshooting hints

---

## 11. Bulk Operation Failures

### Pitfall
Stopping entire batch when one issue fails.

**Problem:**
```python
# ❌ First failure stops everything
for issue_data in batch:
    client.create_issue(**issue_data)  # Fails on first error
```

**Solution:**
```python
# ✅ Continue on errors, report at end
results = []
errors = []
for issue_data in batch:
    try:
        issue = client.create_issue(**issue_data)
        results.append(issue)
    except Exception as e:
        errors.append((issue_data["title"], str(e)))

print(f"Created {len(results)}/{len(batch)} issues")
if errors:
    print("Failures:")
    for title, error in errors:
        print(f"  - {title}: {error}")
```

**In the Skill:**
- bulk_operations.py uses try-except per issue
- Shows progress during execution
- Reports summary with successes and failures

---

## 12. Priority Value Confusion

### Pitfall
Confusing priority values (0-4) with P0-P4 labels.

**Problem:**
```python
# ❌ Wrong mapping
priority = 0  # User means "P0 urgent" but 0 = "No priority"
```

**Solution:**
```python
# ✅ Correct mapping
priority_map = {
    "p0": 1,    # Urgent
    "p1": 2,    # High
    "p2": 3,    # Normal
    "p3": 4,    # Low
    "urgent": 1,
    "high": 2,
    "normal": 3,
    "low": 4,
    "none": 0
}
```

**In the Skill:**
- Use field_mappings.md for consistent mapping
- Show priority names, not just numbers
- Validate priority input: 0-4 only

---

## 13. Template Variable Missing

### Pitfall
Not providing all template variables, leaving placeholders in final issue.

**Problem:**
```python
# ❌ Missing 'expected' variable
template_vars = {"short_description": "Bug", "actual": "Crash"}
# Result: "Expected: {expected}" appears in issue
```

**Solution:**
```python
# ✅ Validate all required variables
required = extract_template_vars(template)
missing = [v for v in required if v not in template_vars]
if missing:
    raise ValueError(f"Missing template variables: {missing}")
```

**In the Skill:**
- create_issue.py prompts for missing variables
- Templates document required variables
- Show preview before creating issue

---

## 14. Assignee Resolution

### Pitfall
Assuming email addresses can be used directly as assignee IDs.

**Problem:**
```python
# ❌ API needs user ID, not email
client.create_issue(team_id=team_id, title="Test", assigneeId="user@example.com")
```

**Solution:**
```python
# ✅ Resolve email to user ID first
# Note: Requires additional query to get user by email
# Currently not implemented - recommend using user ID directly
```

**In the Skill:**
- Currently requires user ID (not email)
- TODO: Add user lookup by email feature
- Document this limitation in SKILL.md

---

## 15. Retry Logic on Transient Errors

### Pitfall
Not retrying on network failures or transient API errors.

**Problem:**
```python
# ❌ Single attempt, fails on network blip
response = requests.post(url, ...)
```

**Solution:**
```python
# ✅ Exponential backoff retry
for attempt in range(MAX_RETRIES):
    try:
        response = requests.post(url, ...)
        return response
    except RequestException as e:
        if attempt == MAX_RETRIES - 1:
            raise
        wait_time = 2 ** attempt
        time.sleep(wait_time)
```

**In the Skill:**
- LinearClient._execute_query() has built-in retry
- Max 3 retries with exponential backoff
- Shows retry messages in verbose mode

---

## Best Practices Summary

1. **Always resolve names to IDs** before API calls
2. **Use case-insensitive matching** for names
3. **Respect rate limits** with throttling and batching
4. **Validate required fields** before API calls
5. **Check current state** before updates
6. **Resolve label names to IDs** before creating issues
7. **Use proper markdown** formatting in descriptions
8. **Handle pagination** for large result sets
9. **Refresh data** instead of long-term caching
10. **Provide clear error messages** to users
11. **Continue on errors** in bulk operations
12. **Map priority correctly** (0=None, 1=Urgent, not P0)
13. **Validate template variables** before rendering
14. **Use user IDs** for assignees (not emails yet)
15. **Implement retry logic** for transient failures
