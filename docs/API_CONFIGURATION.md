# Configuration Management API

Complete API reference for managing research strategies and global settings via HTTP endpoints.

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Strategy Endpoints](#strategy-endpoints)
- [Global Settings Endpoints](#global-settings-endpoints)
- [Examples](#examples)
- [Strategy YAML Structure](#strategy-yaml-structure)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Configuration Management API allows you to create, update, and delete research strategies and global LLM settings **without redeploying your application**. Changes take effect immediately by invalidating in-memory caches.

**Base URL**: `https://your-api-domain.com`

**Key Features**:
- ✅ Runtime configuration updates (no redeploy needed)
- ✅ Automatic cache invalidation
- ✅ Database-backed with YAML fallback
- ✅ API key authentication
- ✅ Full CRUD operations

---

## Authentication

All endpoints require an API key via the `X-API-Key` header.

```bash
X-API-Key: your-secret-api-key
```

The API key is configured via the `API_SECRET_KEY` environment variable.

**Example**:
```bash
curl -H "X-API-Key: your-secret-api-key" \
  https://your-api.com/api/strategies
```

---

## Strategy Endpoints

### List All Strategies

**GET** `/api/strategies`

List all active strategies from the database.

**Query Parameters**:
- `active_only` (boolean, optional, default: `true`) - Filter by active status

**Response**: `200 OK`
```json
[
  {
    "id": "uuid",
    "slug": "daily_news_briefing",
    "yaml_content": { ... },
    "is_active": true,
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  }
]
```

**Example**:
```bash
curl -H "X-API-Key: your-key" \
  "https://your-api.com/api/strategies?active_only=true"
```

---

### Get Single Strategy

**GET** `/api/strategies/{slug}`

Retrieve a specific strategy by its slug.

**Path Parameters**:
- `slug` (string, required) - Strategy identifier (e.g., `daily_news_briefing`)

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "slug": "daily_news_briefing",
  "yaml_content": {
    "meta": {
      "slug": "daily_news_briefing",
      "version": 3,
      "category": "news",
      "time_window": "day",
      "depth": "deep"
    },
    "queries": {
      "sonar": "{{topic}} latest news updates"
    },
    "tool_chain": [ ... ],
    "llm": {
      "fill": {
        "temperature": 0.4
      }
    }
  },
  "is_active": true,
  "created_at": "2025-11-05T10:00:00Z",
  "updated_at": "2025-11-05T10:00:00Z"
}
```

**Errors**:
- `404 Not Found` - Strategy not found

**Example**:
```bash
curl -H "X-API-Key: your-key" \
  https://your-api.com/api/strategies/daily_news_briefing
```

---

### Create New Strategy

**POST** `/api/strategies`

Create a new research strategy.

**Request Body**:
```json
{
  "slug": "my_custom_strategy",
  "yaml_content": {
    "meta": {
      "slug": "my_custom_strategy",
      "version": 1,
      "category": "news",
      "time_window": "week",
      "depth": "brief"
    },
    "queries": {
      "exa_search": "{{topic}} recent developments"
    },
    "tool_chain": [
      {
        "use": "exa.search",
        "inputs": {
          "query": "{{topic}}",
          "num_results": 10
        }
      }
    ],
    "limits": {
      "max_results": 20
    }
  }
}
```

**Response**: `201 Created`
```json
{
  "id": "uuid",
  "slug": "my_custom_strategy",
  "yaml_content": { ... },
  "is_active": true,
  "created_at": "2025-11-05T15:30:00Z",
  "updated_at": "2025-11-05T15:30:00Z"
}
```

**Errors**:
- `400 Bad Request` - Strategy with slug already exists
- `422 Unprocessable Entity` - Invalid YAML structure

**Example**:
```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "my_custom_strategy",
    "yaml_content": { ... }
  }' \
  https://your-api.com/api/strategies
```

**Effect**: Strategy cache is cleared and new strategy becomes immediately available.

---

### Update Existing Strategy

**PUT** `/api/strategies/{slug}`

Update an existing strategy's configuration.

**Path Parameters**:
- `slug` (string, required) - Strategy identifier

**Request Body**:
```json
{
  "yaml_content": {
    "meta": {
      "slug": "daily_news_briefing",
      "version": 4,
      "category": "news",
      "time_window": "day",
      "depth": "deep"
    },
    "queries": {
      "sonar": "{{topic}} breaking news"
    },
    "llm": {
      "fill": {
        "temperature": 0.5,
        "model": "gpt-5-mini"
      }
    }
  }
}
```

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "slug": "daily_news_briefing",
  "yaml_content": { ... },
  "is_active": true,
  "created_at": "2025-11-05T10:00:00Z",
  "updated_at": "2025-11-05T15:45:00Z"
}
```

**Errors**:
- `404 Not Found` - Strategy not found

**Example**:
```bash
curl -X PUT \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": { ... }
  }' \
  https://your-api.com/api/strategies/daily_news_briefing
```

**Effect**: Strategy cache is cleared and updated strategy loads on next request.

---

### Delete Strategy

**DELETE** `/api/strategies/{slug}`

Delete a strategy from the database.

**Path Parameters**:
- `slug` (string, required) - Strategy identifier

**Response**: `200 OK`
```json
{
  "success": true,
  "message": "Strategy 'my_custom_strategy' deleted"
}
```

**Errors**:
- `404 Not Found` - Strategy not found

**Example**:
```bash
curl -X DELETE \
  -H "X-API-Key: your-key" \
  https://your-api.com/api/strategies/my_custom_strategy
```

**Effect**: Strategy cache is cleared and deleted strategy is no longer available.

---

## Global Settings Endpoints

### List All Settings

**GET** `/api/settings`

List all global configuration settings (LLM defaults, prompts).

**Response**: `200 OK`
```json
[
  {
    "id": "uuid",
    "key": "llm_defaults",
    "value": {
      "fill": {
        "model": "gpt-5-mini",
        "temperature": 0.3
      },
      "summarize": {
        "model": "gpt-5-mini",
        "temperature": 0.2
      }
    },
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  },
  {
    "id": "uuid",
    "key": "prompts",
    "value": {
      "fill": {
        "instructions": "Analyze the task context..."
      }
    },
    "created_at": "2025-11-05T10:00:00Z",
    "updated_at": "2025-11-05T10:00:00Z"
  }
]
```

**Example**:
```bash
curl -H "X-API-Key: your-key" \
  https://your-api.com/api/settings
```

---

### Get Single Setting

**GET** `/api/settings/{key}`

Retrieve a specific setting by key.

**Path Parameters**:
- `key` (string, required) - Setting key (`llm_defaults` or `prompts`)

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "key": "llm_defaults",
  "value": {
    "fill": {
      "model": "gpt-5-mini",
      "temperature": 0.3
    },
    "nodes": {
      "scope_classifier": {
        "model": "gpt-5-mini",
        "temperature": 0
      }
    }
  },
  "created_at": "2025-11-05T10:00:00Z",
  "updated_at": "2025-11-05T10:00:00Z"
}
```

**Errors**:
- `404 Not Found` - Setting not found

**Example**:
```bash
curl -H "X-API-Key: your-key" \
  https://your-api.com/api/settings/llm_defaults
```

---

### Update Setting

**PUT** `/api/settings/{key}`

Update or create a global setting.

**Path Parameters**:
- `key` (string, required) - Setting key

**Request Body**:
```json
{
  "value": {
    "fill": {
      "model": "gpt-5-mini",
      "temperature": 0.4
    },
    "summarize": {
      "model": "gpt-5-mini",
      "temperature": 0.3
    },
    "nodes": {
      "scope_classifier": {
        "model": "gpt-5-mini",
        "temperature": 0.1
      }
    }
  }
}
```

**Response**: `200 OK`
```json
{
  "id": "uuid",
  "key": "llm_defaults",
  "value": { ... },
  "created_at": "2025-11-05T10:00:00Z",
  "updated_at": "2025-11-05T16:00:00Z"
}
```

**Example**:
```bash
curl -X PUT \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "value": {
      "fill": {
        "model": "gpt-5-mini",
        "temperature": 0.4
      }
    }
  }' \
  https://your-api.com/api/settings/llm_defaults
```

**Effect**: Config cache is cleared and new settings load on next LLM call.

---

## Examples

### Example 1: Update LLM Temperature for All Strategies

```bash
curl -X PUT \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "value": {
      "fill": { "model": "gpt-5-mini", "temperature": 0.5 },
      "summarize": { "model": "gpt-5-mini", "temperature": 0.4 },
      "qc": { "model": "gpt-5-mini", "temperature": 0 }
    }
  }' \
  https://your-api.com/api/settings/llm_defaults
```

### Example 2: Create Custom Weekly Tech News Strategy

```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "weekly_tech_news",
    "yaml_content": {
      "meta": {
        "slug": "weekly_tech_news",
        "version": 1,
        "category": "news",
        "time_window": "week",
        "depth": "overview"
      },
      "queries": {
        "exa_search": "{{topic}} technology news"
      },
      "tool_chain": [
        {
          "use": "exa.search",
          "inputs": {
            "query": "{{topic}} tech developments",
            "num_results": 15
          }
        }
      ],
      "limits": {
        "max_results": 30
      }
    }
  }' \
  https://your-api.com/api/strategies
```

### Example 3: Update Strategy to Use Different Model

```bash
curl -X PUT \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "yaml_content": {
      "meta": { ... },
      "queries": { ... },
      "tool_chain": [ ... ],
      "llm": {
        "analyzer": {
          "model": "gpt-5",
          "temperature": 0.2
        }
      }
    }
  }' \
  https://your-api.com/api/strategies/daily_news_briefing
```

---

## Strategy YAML Structure

Complete structure for strategy `yaml_content`:

```yaml
meta:
  slug: strategy_name
  version: 1
  category: news          # news|finance|company|academic|general
  time_window: day        # day|week|month
  depth: deep             # brief|overview|deep|comprehensive

queries:
  sonar: "{{topic}} latest updates"
  exa_search: "{{topic}} developments"
  exa_answer: "What happened with {{topic}}?"

tool_chain:
  - use: exa.search
    inputs:
      query: "{{topic}}"
      num_results: 10
    llm_fill: ["query"]
    save_as: search_results

  - use: llm_analyzer.call
    description: "Synthesize findings"
    inputs:
      prompt: "Create comprehensive briefing..."
    phase: finalize

limits:
  max_results: 20
  max_llm_queries: 3

finalize:
  reactive: false
  instructions: |
    Create structured report with:
    1. Executive Summary
    2. Key Developments
    3. Analysis

llm:
  fill:
    model: gpt-5-mini
    temperature: 0.3
  analyzer:
    model: gpt-5-mini
    temperature: 0.2
```

---

## Troubleshooting

### Strategy Not Loading After Update

**Problem**: Updated strategy via API but old version still runs.

**Solution**: Cache invalidation happens automatically, but if issues persist:
1. Check that the `updated_at` timestamp changed
2. Restart the application to force cache reload
3. Verify database was actually updated: `GET /api/strategies/{slug}`

### Authentication Failed

**Problem**: `401 Unauthorized` response.

**Solution**:
- Verify `X-API-Key` header is included
- Check that API key matches `API_SECRET_KEY` environment variable
- Ensure header name is exactly `X-API-Key` (case-sensitive)

### Invalid YAML Structure

**Problem**: `422 Unprocessable Entity` when creating/updating strategy.

**Solution**:
- Validate `yaml_content` against schema
- Ensure `meta` section includes all required fields
- Check that `tool_chain` is an array
- Verify JSON structure is valid

### Strategy Slug Collision

**Problem**: `400 Bad Request` when creating strategy.

**Solution**:
- Choose a different slug
- Or delete existing strategy first: `DELETE /api/strategies/{slug}`
- Or update existing strategy instead: `PUT /api/strategies/{slug}`

---

## Migration Notes

If migrating from file-based YAML to database:

1. **Run migration script**:
   ```bash
   python scripts/migrate_main_strategies.py
   ```

2. **Verify migration**:
   ```bash
   curl -H "X-API-Key: your-key" https://your-api.com/api/strategies
   ```

3. **Keep YAML files as backup** (already done in migration)

4. **Test strategy execution** with database-loaded strategies

5. **Optionally delete YAML files** after confirming everything works

---

## Support

For issues or questions:
- Check application logs for detailed error messages
- Verify database connectivity
- Ensure all environment variables are set
- Review strategy YAML structure against examples

**API Version**: 1.0.0
**Last Updated**: 2025-11-05
