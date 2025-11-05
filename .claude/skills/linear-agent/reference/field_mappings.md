# Linear Field Mappings

## Overview

This document maps natural language concepts to Linear API fields for the Linear Agent Skill.

---

## Issue Fields

### Core Fields

| User Input | Linear Field | Type | Notes |
|------------|--------------|------|-------|
| Title | `title` | string | Required |
| Description | `description` | string | Supports markdown |
| Team | `teamId` | string | Required, must resolve team name → ID |
| Status, State | `stateId` | string | Must resolve state name → ID |
| Priority | `priority` | integer | 0-4 (0=None, 1=Urgent, 2=High, 3=Normal, 4=Low) |
| Assignee | `assigneeId` | string | Must resolve email/name → user ID |
| Labels, Tags | `labelIds` | string[] | Array of label IDs |
| Estimate, Points | `estimate` | integer | Story points |
| Due date | `dueDate` | string | ISO 8601 format |
| Parent | `parentId` | string | For sub-issues |
| Project | `projectId` | string | Must resolve project name → ID |

### Read-only Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Internal Linear ID |
| `identifier` | string | Human-readable ID (e.g., ISS-123) |
| `url` | string | Web URL to issue |
| `createdAt` | timestamp | Creation timestamp |
| `updatedAt` | timestamp | Last update timestamp |
| `completedAt` | timestamp | Completion timestamp |
| `number` | integer | Issue number in team |

---

## Priority Mappings

### Natural Language → Priority Value

| User Input | Priority Value | Linear Display |
|------------|---------------|----------------|
| urgent, p0, critical, blocker | 1 | Urgent |
| high, p1, important | 2 | High |
| normal, p2, medium, default | 3 | Normal |
| low, p3, minor | 4 | Low |
| none, no priority, unset | 0 | No priority |

---

## State Mappings

### Common State Names

States are team-specific, but common patterns include:

| Common Names | State Type | Description |
|--------------|------------|-------------|
| Backlog, To Do, Planned | `backlog` | Not started |
| Todo, Ready | `unstarted` | Ready to start |
| In Progress, Started, Working On | `started` | Active work |
| In Review, Review | `started` | Under review |
| Done, Completed, Finished | `completed` | Completed |
| Canceled, Cancelled, Won't Do | `canceled` | Canceled |

**Note:** State names are team-configurable. Always query available states for a team before updating.

---

## Label Mappings

### Label Resolution

Labels are identified by name (case-insensitive), but the API requires label IDs.

**Resolution Process:**
1. Query all labels for team
2. Build name → ID mapping
3. Convert user-provided names to IDs
4. Warn if labels don't exist

**Common Label Patterns:**

| Type | Examples |
|------|----------|
| Type | bug, feature, task, improvement, documentation |
| Priority | p0, p1, p2, p3, critical, urgent |
| Area | backend, frontend, api, database, infrastructure |
| Status | blocked, needs-review, ready-to-test |
| Platform | ios, android, web, mobile |

---

## Team Mappings

### Team Resolution

Teams are identified by name (case-insensitive) or ID.

**Resolution Process:**
1. If input starts with `team_`: Use as ID directly
2. Otherwise: Query teams and match by name (case-insensitive)
3. Return first match or error

**Common Team Patterns:**
- Engineering teams: Backend, Frontend, Mobile, Infrastructure
- Functional teams: Design, Product, Marketing
- Project teams: Named after product/feature

---

## Date/Time Formats

### Input Formats

| User Input | Parsed As | Linear Format |
|------------|-----------|---------------|
| "2025-01-15" | Specific date | "2025-01-15T00:00:00.000Z" |
| "tomorrow" | Next day | ISO 8601 |
| "next week" | 7 days ahead | ISO 8601 |
| "in 3 days" | Relative | ISO 8601 |

---

## Estimate Mappings

### Story Points

Linear supports integer estimates (typically 1-13 for Fibonacci):

| User Input | Estimate Value |
|------------|---------------|
| XS, tiny | 1 |
| S, small | 2 |
| M, medium | 3 |
| L, large | 5 |
| XL, extra large | 8 |
| XXL, huge | 13 |
| (numeric) | Use as-is |

---

## Special Field Handling

### Description Formatting

Linear supports markdown in descriptions:

```markdown
## Heading
**Bold text**
*Italic text*
- Bullet list
1. Numbered list
[Link](url)
`code`
```

### Multi-value Fields

**Labels**: Array of label IDs
```json
{
  "labelIds": ["label_abc", "label_xyz"]
}
```

**Relationships**: Single ID reference
```json
{
  "parentId": "issue_parent",
  "projectId": "project_xyz"
}
```

---

## Filter Operators

When querying issues:

| Operator | Usage | Example |
|----------|-------|---------|
| `eq` | Equals | `{ state: { name: { eq: "Done" } } }` |
| `neq` | Not equals | `{ priority: { neq: 0 } }` |
| `in` | In array | `{ state: { name: { in: ["Done", "Canceled"] } } }` |
| `contains` | Substring | `{ title: { contains: "auth" } }` |
| `gt`, `gte` | Greater than | `{ priority: { gte: 2 } }` |
| `lt`, `lte` | Less than | `{ estimate: { lte: 5 } }` |

---

## Template Variable Mappings

### Bug Template → Linear Fields

| Template Variable | Linear Field | Transform |
|-------------------|--------------|-----------|
| `short_description` | Title (partial) | Prepend "[BUG] " |
| `detailed_description` | Description (partial) | ## Description section |
| `steps` | Description (partial) | ## Steps section |
| `expected` | Description (partial) | ## Expected section |
| `actual` | Description (partial) | ## Actual section |
| `os`, `version` | Description (partial) | ## Environment section |
| (template labels) | `labelIds` | Resolve "bug" label |
| (template priority) | `priority` | Default to 2 (High) |

### Feature Template → Linear Fields

| Template Variable | Linear Field | Transform |
|-------------------|--------------|-----------|
| `short_description` | Title (partial) | Prepend "[FEATURE] " |
| `problem` | Description (partial) | ## Problem section |
| `solution` | Description (partial) | ## Solution section |
| `alternatives` | Description (partial) | ## Alternatives section |
| `success_criteria` | Description (partial) | ## Success section |
| (template labels) | `labelIds` | Resolve "feature" label |
| (template priority) | `priority` | Default to 3 (Normal) |

---

## Error Message Mappings

### API Errors → User-Friendly Messages

| API Error | User Message | Action |
|-----------|-------------|---------|
| "Team not found" | "Team '{name}' doesn't exist. Available teams: ..." | List teams |
| "Invalid priority" | "Priority must be 0-4 (0=None, 1=Urgent, 2=High, 3=Normal, 4=Low)" | Show options |
| "Label not found" | "Label '{name}' not found for team. Available: ..." | List labels |
| "Rate limit exceeded" | "Too many requests. Pausing for {time}s..." | Auto-retry |
| "Unauthorized" | "API key invalid or expired. Check LINEAR_API_KEY." | Check env var |
