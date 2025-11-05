# Linear API GraphQL Schema Reference

## Overview

The Linear API is a GraphQL API accessible at `https://api.linear.app/graphql`. This document provides quick reference for common operations.

**Authentication:**
```
Authorization: Bearer <LINEAR_API_KEY>
```

**Rate Limits:**
- 1,500 requests per hour per user

---

## Common Queries

### Get Teams
```graphql
query Teams {
  teams {
    nodes {
      id
      name
      key
      description
    }
  }
}
```

### Get Issue by ID
```graphql
query GetIssue($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    priority
    estimate
    state {
      id
      name
      type
    }
    assignee {
      id
      name
      email
    }
    team {
      id
      name
    }
    labels {
      nodes {
        id
        name
        color
      }
    }
    createdAt
    updatedAt
    url
  }
}
```

### List Issues for Team
```graphql
query TeamIssues($teamId: String!) {
  team(id: $teamId) {
    issues {
      nodes {
        id
        identifier
        title
        state {
          name
          type
        }
        priority
        assignee {
          name
        }
      }
    }
  }
}
```

### Get Projects
```graphql
query Projects {
  projects {
    nodes {
      id
      name
      description
      state
      startDate
      targetDate
    }
  }
}
```

---

## Common Mutations

### Create Issue
```graphql
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue {
      id
      identifier
      title
      url
      state {
        name
      }
    }
  }
}
```

**Input Variables:**
```json
{
  "input": {
    "teamId": "team_abc123",
    "title": "Issue title",
    "description": "Issue description (markdown supported)",
    "priority": 2,
    "assigneeId": "user_xyz789",
    "labelIds": ["label_1", "label_2"],
    "estimate": 5
  }
}
```

### Update Issue
```graphql
mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
  issueUpdate(id: $id, input: $input) {
    success
    issue {
      id
      identifier
      title
      url
      state {
        name
      }
    }
  }
}
```

**Input Variables:**
```json
{
  "id": "issue_abc123",
  "input": {
    "title": "Updated title",
    "priority": 1,
    "stateId": "state_xyz789"
  }
}
```

### Create Comment
```graphql
mutation CommentCreate($input: CommentCreateInput!) {
  commentCreate(input: $input) {
    success
    comment {
      id
      body
      createdAt
    }
  }
}
```

**Input Variables:**
```json
{
  "input": {
    "issueId": "issue_abc123",
    "body": "Comment text (markdown supported)"
  }
}
```

### Create Label
```graphql
mutation LabelCreate($input: IssueLabelCreateInput!) {
  issueLabelCreate(input: $input) {
    success
    issueLabel {
      id
      name
      color
    }
  }
}
```

---

## Field Types

### Priority
Integer values:
- `0`: No priority
- `1`: Urgent
- `2`: High
- `3`: Normal (default)
- `4`: Low

### State Types
- `backlog`: Backlog state
- `unstarted`: Unstarted state
- `started`: In progress state
- `completed`: Completed state
- `canceled`: Canceled state

### Issue Fields

**Required:**
- `teamId`: Team ID (string)
- `title`: Issue title (string)

**Optional:**
- `description`: Markdown description (string)
- `priority`: Priority level (0-4, integer)
- `assigneeId`: Assignee user ID (string)
- `stateId`: State ID (string)
- `projectId`: Project ID (string)
- `labelIds`: Array of label IDs (string[])
- `estimate`: Story points (integer)
- `parentId`: Parent issue ID for sub-issues (string)
- `dueDate`: Due date (ISO 8601 string)

---

## Pagination

Linear uses cursor-based pagination:

```graphql
query PaginatedIssues($after: String) {
  issues(first: 50, after: $after) {
    nodes {
      id
      title
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
```

---

## Filtering

Most queries support filter parameters:

```graphql
query FilteredIssues {
  issues(
    filter: {
      team: { name: { eq: "Backend Team" } }
      state: { name: { eq: "In Progress" } }
      priority: { eq: 2 }
    }
  ) {
    nodes {
      id
      title
    }
  }
}
```

**Filter Operators:**
- `eq`: Equals
- `neq`: Not equals
- `in`: In array
- `contains`: Contains substring
- `gt`, `gte`, `lt`, `lte`: Comparisons

---

## Error Handling

GraphQL errors are returned in the `errors` array:

```json
{
  "errors": [
    {
      "message": "Team not found",
      "path": ["issueCreate"],
      "extensions": {
        "code": "NOT_FOUND"
      }
    }
  ]
}
```

Common error codes:
- `NOT_FOUND`: Resource doesn't exist
- `INVALID_INPUT`: Validation failed
- `UNAUTHORIZED`: Authentication failed
- `FORBIDDEN`: Permission denied
- `RATE_LIMITED`: Too many requests

---

## Resources

- **Official Docs**: https://developers.linear.app
- **GraphQL Explorer**: https://studio.apollographql.com/public/Linear-API
- **SDK**: https://github.com/linear/linear (TypeScript/JavaScript)
