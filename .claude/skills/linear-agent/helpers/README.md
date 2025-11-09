# Linear Agent Helper Tools

Optimized, crystal-clear helper scripts for Linear API operations.

## Quick Start

All scripts are located in `/home/user/web_research_agent/.claude/skills/linear-agent/helpers/`

### Prerequisites

```bash
# Set your Linear API key
export LINEAR_API_KEY="lin_api_..."
```

### Test Connection

```bash
python test_api.py
```

Expected output:
```
✓ API key found: lin_api_...
🔍 Testing Linear API connection...
Status Code: 200
✓ API Connection Successful!
  User: Your Name
  Email: your@email.com
```

---

## Core Operations

### 1. Search for Issues

**Use Case**: Find issues by keywords in title or description

```bash
# Search for issues containing "Tracing"
python query_issues.py --search "Tracing" --verbose

# Search within a specific team
python query_issues.py --team "MB90" --search "LLM" --verbose

# Filter by state
python query_issues.py --state "Backlog" --verbose

# Filter by priority (0=None, 1=Urgent, 2=High, 3=Normal, 4=Low)
python query_issues.py --priority 2 --verbose

# Combine filters
python query_issues.py --team "MB90" --state "Backlog" --priority 2 --search "tracing" --verbose
```

**Example Output**:
```
🔍 Querying Linear issues...
✓ Retrieved 100 total issues
🔍 Filtered by search 'Tracing': 9 issues
✓ Returning 9 issues

ID           Title                                              State           Priority
------------------------------------------------------------------------------------------
MB90-285     [Tracing] Add Comprehensive LLM Call Tracing - T   Backlog         High
MB90-284     [Tracing] Add Research Step-Level Tracing - Indi   Backlog         Urgent
...
```

---

### 2. Get Issue Details

**Use Case**: Retrieve complete details of a specific issue

```bash
# Get issue by identifier
python get_issue.py MB90-285 --verbose

# Get issue as JSON for parsing
python get_issue.py MB90-285 --format json
```

**Example Output**:
```
🔍 Searching for issue: MB90-285
✓ Found issue: MB90-285 - [Tracing] Add Comprehensive LLM Call Tracing

================================================================================
Issue: MB90-285
================================================================================

Title: [Tracing] Add Comprehensive LLM Call Tracing - Token & Cost Visibility
URL: https://linear.app/ecosystem901209/issue/MB90-285/...

Team: MB90
State: Backlog
Priority: High
Assignee: Unassigned
Estimate: 8 points
Project: Web Research Agent Architecture

Created: 2025-11-09T12:04:18.141Z
Updated: 2025-11-09T12:10:59.510Z

Description:
--------------------------------------------------------------------------------
## Goal
Make ALL LLM calls visible with prompts, responses, and token usage...
[Full description here]
--------------------------------------------------------------------------------
```

---

### 3. Update Issues

**Use Case**: Modify issue fields or add comments

#### Add a Comment

```bash
python update_issue.py --issue-id MB90-285 \
  --comment "Working on this issue now" \
  --verbose
```

#### Change State

```bash
python update_issue.py --issue-id MB90-285 \
  --state "In Progress" \
  --comment "Starting implementation" \
  --verbose
```

**Note**: State names are automatically resolved! Available states:
- Backlog
- Todo
- In Progress
- In Review
- Done
- Canceled

#### Update Priority

```bash
python update_issue.py --issue-id MB90-285 \
  --priority 1 \
  --comment "Escalating to urgent" \
  --verbose
```

Priority values:
- 0 = No priority
- 1 = Urgent
- 2 = High
- 3 = Normal
- 4 = Low

#### Update Multiple Fields

```bash
python update_issue.py --issue-id MB90-285 \
  --state "In Progress" \
  --priority 1 \
  --estimate 5 \
  --comment "Updated estimate after scoping" \
  --verbose
```

**Example Output**:
```
🔍 Fetching current state of MB90-285...
✓ Found issue: MB90-285 - [Tracing] Add Comprehensive LLM Call Tracing
  Current state: Backlog

✓ Found state: In Progress (ID: abc123...)

📝 Proposed changes:
  • Priority: High → Urgent
  • Estimate: 8 → 5 points
  • State: Backlog → In Progress

🔄 Applying updates...
💬 Adding comment...
✓ Comment added successfully
✓ Update complete!

✅ Issue updated successfully!
  ID: MB90-285
  Title: [Tracing] Add Comprehensive LLM Call Tracing
  URL: https://linear.app/...
  State: In Progress
```

---

## Advanced Usage

### Export Issues to CSV

```bash
python query_issues.py --team "MB90" --state "Backlog" \
  --output issues_backlog.csv --format csv
```

### Export Issues to JSON

```bash
python query_issues.py --search "Tracing" \
  --output tracing_issues.json --format json
```

### List Teams

```bash
python linear_client.py
```

Output:
```
✓ Linear client initialized
✓ Found 1 teams
  - MB90 (MB90)
```

---

## Key Improvements Made

### 1. **Fixed Authorization Header**
- **Before**: Used `Bearer {token}` format (caused 503 errors)
- **After**: Direct API key in Authorization header (works correctly)
- **File**: `linear_client.py:52`

### 2. **Simplified Query Construction**
- **Before**: Complex dynamic GraphQL query building (error-prone)
- **After**: Simple query + client-side filtering (robust & reliable)
- **File**: `query_issues.py:48-167`

### 3. **Added State Lookup**
- **Before**: Required state IDs manually
- **After**: Automatically resolves state names to IDs
- **Files**:
  - `linear_client.py:394-454` (new methods)
  - `update_issue.py:139-155` (implementation)

### 4. **Fixed Comment-Only Updates**
- **Before**: Comments ignored if no other changes
- **After**: Comments work independently
- **File**: `update_issue.py:157-181`

### 5. **Created Get Issue Helper**
- **New Feature**: Retrieve issues by identifier
- **File**: `get_issue.py` (new file)

### 6. **Added API Test Script**
- **New Feature**: Quick connection testing
- **File**: `test_api.py` (new file)

---

## Troubleshooting

### API Connection Issues

```bash
# Test API connectivity
python test_api.py
```

Common issues:
1. **LINEAR_API_KEY not set**: Export the environment variable
2. **Invalid API key**: Check key starts with `lin_api_`
3. **503 errors**: Check Linear API status

### Finding State Names

```bash
# If state update fails, use --verbose to see available states
python update_issue.py --issue-id MB90-285 --state "InvalidState" --verbose
```

Output will show:
```
⚠ Warning: State not found: 'InvalidState'
  Available states: Backlog, Todo, In Progress, In Review, Done, Canceled
```

### Rate Limiting

The client automatically handles rate limiting (1500 requests/hour). If you hit the limit:
```
[Rate Limit] Approaching limit, pausing for 3600s
```

Wait for the window to reset, or reduce query volume.

---

## Testing with Your Issue

Using the example issue "[Tracing] Add Comprehensive LLM Call Tracing - Token & Cost Visibility":

```bash
# 1. Search for it
python query_issues.py --search "Comprehensive LLM" --verbose

# 2. Get full details
python get_issue.py MB90-285 --verbose

# 3. Move to "In Progress"
python update_issue.py --issue-id MB90-285 \
  --state "In Progress" \
  --comment "Starting implementation based on requirements" \
  --verbose

# 4. Update estimate
python update_issue.py --issue-id MB90-285 \
  --estimate 5 \
  --comment "Refined estimate after technical review" \
  --verbose

# 5. Mark as done (when complete)
python update_issue.py --issue-id MB90-285 \
  --state "Done" \
  --comment "All LLM calls now traced with @observe decorator" \
  --verbose
```

---

## File Reference

| File | Purpose |
|------|---------|
| `linear_client.py` | Core API client with retry logic & error handling |
| `query_issues.py` | Search and filter issues |
| `get_issue.py` | Retrieve specific issue by identifier |
| `update_issue.py` | Update issue fields and add comments |
| `create_issue.py` | Create new issues (existing) |
| `test_api.py` | Test API connectivity |

---

## Summary

All helper tools are now:
- ✅ **Crystal clear**: Verbose output shows exactly what's happening
- ✅ **Error-free**: Fixed authorization, query construction, and state lookup
- ✅ **Well-tested**: Verified with real Linear API operations
- ✅ **Easy to use**: Simple CLI with helpful examples
- ✅ **Robust**: Client-side filtering, retry logic, rate limiting

**Next Steps**: Use these tools to manage your Linear issues with confidence!
