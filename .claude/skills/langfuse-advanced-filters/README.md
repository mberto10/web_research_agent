## Langfuse Advanced Filters Skill

Quick reference for the Langfuse Advanced Filters skill.

### Helper Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `query_with_filters.py` | Query traces/observations with precise filters | `python3 query_with_filters.py --view traces --filters '[...]' --limit 50` |
| `query_metrics.py` | Query aggregated metrics with filters | `python3 query_metrics.py --view traces --metrics '[...]' --dimensions '[...]'` |
| `build_filters.py` | Build and validate filter JSON | `python3 build_filters.py --interactive` |
| `analyze_filtered_results.py` | Analyze query results | `python3 analyze_filtered_results.py --input results.json --analysis-type latency-breakdown` |

### Quick Examples

**Find slow traces for a case**:
```bash
python3 helpers/query_with_filters.py \
  --view traces \
  --filters '[{"column": "metadata", "operator": "=", "key": "case_id", "value": "0001", "type": "stringObject"}, {"column": "latency", "operator": ">", "value": 5000, "type": "number"}]' \
  --from-date "2025-11-01" \
  --limit 50
```

**Find ERROR observations**:
```bash
python3 helpers/query_with_filters.py \
  --view observations \
  --filters '[{"column": "level", "operator": "=", "value": "ERROR", "type": "string"}]' \
  --from-date "2025-11-03" \
  --limit 100
```

**Get average latency by case**:
```bash
python3 helpers/query_metrics.py \
  --view traces \
  --metrics '[{"measure": "latency", "aggregation": "avg"}]' \
  --dimensions '[{"field": "metadata.case_id"}]' \
  --from-date "2025-11-01T00:00:00Z" \
  --to-date "2025-11-04T23:59:59Z"
```

### Filter Syntax

```json
{
  "column": "string",      // Field to filter on
  "operator": "string",    // =, >, <, >=, <=, contains, etc.
  "value": "any",          // Value to compare
  "type": "string",        // string, number, datetime, stringObject
  "key": "string"          // Required for metadata filters
}
```

### Common Use Cases

1. **Debug slow workflows**: Filter by case + latency threshold
2. **Find failing checks**: Filter by case + ERROR level + node name
3. **Analyze tool selection**: Filter by research node + metadata
4. **Performance regression**: Compare metrics before/after deployment
5. **Error spike investigation**: Filter by ERROR level + time range

See `SKILL.md` for detailed documentation.
