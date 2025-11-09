# Strategy Builder & Optimizer Skill

Intelligent assistant for building, optimizing, and analyzing research strategies in the web research agent.

## Overview

This skill helps you:
1. **Analyze research queries** to determine if new strategies are needed
2. **Optimize existing strategies** using Langfuse trace data
3. **Generate strategy templates** with valid YAML structure
4. **Validate strategies** against schema

## Quick Start

### Use Case 1: Analyze a Research Query

**Question**: "Do I need a new strategy for this research query?"

```bash
cd /home/user/web_research_agent/.claude/skills/strategy-builder/helpers

# Analyze query
python3 analyze_research_query.py \
  --query "Suche mir alle Informationen über gerichtsurteile an deutschen Gerichten" \
  --output /tmp/analysis.json

# View results
cat /tmp/analysis.json
```

**Output tells you**:
- Whether existing strategy matches
- What category/time_window/depth it classified
- If new strategy needed, provides suggested slug and tools

### Use Case 2: Optimize Existing Strategy

**Question**: "How is my daily_news_briefing strategy performing?"

```bash
cd /home/user/web_research_agent/.claude/skills/strategy-builder/helpers

# Step 1: Get traces for strategy
python3 retrieve_strategy_traces.py \
  --strategy "daily_news_briefing" \
  --days 7 \
  --limit 50 \
  --filter-essential \
  --output /tmp/traces.json

# Step 2: Analyze performance
python3 analyze_strategy_performance.py \
  --traces /tmp/traces.json \
  --strategy "daily_news_briefing" \
  --output /tmp/performance.json

# View results
cat /tmp/performance.json
```

**Output includes**:
- Success rate
- Latency breakdown by phase
- Tool effectiveness
- Error patterns
- Optimization recommendations

### Use Case 3: Create New Strategy

**Question**: "I need a strategy for legal research in German"

```bash
cd /home/user/web_research_agent/.claude/skills/strategy-builder/helpers

# Step 1: Generate strategy template
python3 generate_strategy.py \
  --slug "legal/court_cases_de" \
  --category "legal" \
  --time-window "month" \
  --depth "comprehensive" \
  --required-vars "topic,jurisdiction" \
  --tools "sonar_search,exa_search_semantic,llm_analyzer" \
  --language "de" \
  --output /tmp/new_strategy.yaml

# Step 2: Validate
python3 validate_strategy.py \
  --strategy /tmp/new_strategy.yaml

# Step 3: Review and customize
cat /tmp/new_strategy.yaml
```

## Helper Scripts

### 1. analyze_research_query.py

Classifies research query and recommends strategy action.

**Key Features**:
- Multi-language support (en, de, es, fr)
- LLM-powered classification
- Matches against existing strategies
- Suggests new strategy if needed

**Usage**:
```bash
python3 analyze_research_query.py \
  --query "Your research query" \
  [--frequency daily|weekly|monthly] \
  [--depth brief|overview|deep|comprehensive] \
  --output /tmp/analysis.json
```

### 2. retrieve_strategy_traces.py

Fetches Langfuse traces for specific strategy.

**Key Features**:
- Filters by strategy slug
- Size optimization (95-96% reduction)
- Error-only filtering
- Date range support

**Usage**:
```bash
python3 retrieve_strategy_traces.py \
  --strategy "strategy_slug" \
  --days 7 \
  --limit 50 \
  --filter-essential \
  --output /tmp/traces.json
```

### 3. analyze_strategy_performance.py

Analyzes strategy performance from traces.

**Key Features**:
- Latency analysis (trace, phase, tool-level)
- Error pattern detection
- Tool effectiveness metrics
- Optimization recommendations

**Usage**:
```bash
python3 analyze_strategy_performance.py \
  --traces /tmp/traces.json \
  --strategy "strategy_slug" \
  [--focus latency|errors|tools|all] \
  --output /tmp/performance.json
```

### 4. generate_strategy.py

Generates valid strategy YAML template.

**Key Features**:
- Category-specific defaults
- Domain suggestions
- Multi-language support
- Automatic tool chain generation

**Usage**:
```bash
# From analysis
python3 generate_strategy.py \
  --from-analysis /tmp/analysis.json \
  --output /tmp/strategy.yaml

# Manual
python3 generate_strategy.py \
  --slug "category/name" \
  --category "category" \
  --time-window "day" \
  --depth "deep" \
  --required-vars "topic" \
  --tools "sonar_search,exa_search_semantic" \
  --output /tmp/strategy.yaml
```

### 5. validate_strategy.py

Validates strategy YAML against schema.

**Key Features**:
- JSON schema validation
- Required field checking
- Variable interpolation validation
- Domain filter warnings
- Strict mode for CI/CD

**Usage**:
```bash
python3 validate_strategy.py \
  --strategy /tmp/strategy.yaml \
  [--strict] \
  --output /tmp/validation.json
```

## Common Workflows

### Workflow A: Query → Decision → Action

```bash
# 1. Analyze query
python3 analyze_research_query.py \
  --query "Daily AI regulation news" \
  --output /tmp/analysis.json

# 2. Check recommendation
RECOMMENDATION=$(jq -r '.recommendation' /tmp/analysis.json)

# 3. If use_existing
if [ "$RECOMMENDATION" = "use_existing" ]; then
  SLUG=$(jq -r '.existing_match.slug' /tmp/analysis.json)
  echo "Use existing strategy: $SLUG"
  python run_daily_briefing.py --strategy "$SLUG" --topic "AI regulation"
fi

# 4. If create_new_strategy
if [ "$RECOMMENDATION" = "create_new_strategy" ]; then
  python3 generate_strategy.py \
    --from-analysis /tmp/analysis.json \
    --output /tmp/new_strategy.yaml
  python3 validate_strategy.py --strategy /tmp/new_strategy.yaml
fi
```

### Workflow B: Optimize Existing Strategy

```bash
# 1. Retrieve traces
python3 retrieve_strategy_traces.py \
  --strategy "daily_news_briefing" \
  --days 7 \
  --limit 50 \
  --filter-essential \
  --output /tmp/traces.json

# 2. Analyze performance
python3 analyze_strategy_performance.py \
  --traces /tmp/traces.json \
  --strategy "daily_news_briefing" \
  --output /tmp/performance.json

# 3. Review recommendations
jq '.recommendations' /tmp/performance.json

# 4. Apply fixes to strategy YAML
# (manual step - edit strategies/daily_news_briefing.yaml)

# 5. Validate changes
python3 validate_strategy.py \
  --strategy strategies/daily_news_briefing.yaml

# 6. Re-test and compare
# (run strategy again, re-analyze after 20-30 executions)
```

### Workflow C: Create Strategy from Scratch

```bash
# 1. Generate template
python3 generate_strategy.py \
  --slug "legal/court_cases_de" \
  --category "legal" \
  --time-window "month" \
  --depth "comprehensive" \
  --required-vars "topic,jurisdiction" \
  --tools "sonar_search,exa_search_semantic,llm_analyzer" \
  --language "de" \
  --output /tmp/new_strategy.yaml

# 2. Validate
python3 validate_strategy.py --strategy /tmp/new_strategy.yaml

# 3. Customize (manual)
# Edit /tmp/new_strategy.yaml - adjust prompts, add domains, etc.

# 4. Save to project
cp /tmp/new_strategy.yaml strategies/legal_court_cases_de.yaml

# 5. Add to index
# Edit strategies/index.yaml

# 6. Migrate to database
python scripts/migrate_strategies.py --strategy legal_court_cases_de

# 7. Test
python run_daily_briefing.py \
  --strategy "legal/court_cases_de" \
  --topic "Datenschutz DSGVO"
```

## Environment Variables

Required for Langfuse integration:
```bash
export LANGFUSE_PUBLIC_KEY="your_public_key"
export LANGFUSE_SECRET_KEY="your_secret_key"
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

Required for query analysis:
```bash
export OPENAI_API_KEY="your_openai_key"
export OPENAI_MODEL="gpt-4o-mini"  # optional, default: gpt-4o-mini
```

## Tips

1. **Always start with query analysis** - don't guess if you need a new strategy
2. **Use trace data for decisions** - base optimizations on real performance data
3. **Validate before deploying** - catches 90% of issues
4. **Monitor post-deployment** - wait for 20-30 executions before optimizing
5. **Keep tool chains simple** - start with 2-3 tools, add more only if needed
6. **Language-specific strategies** - customize prompts and domains for each language

## Troubleshooting

**"No strategies found"**:
- Run: `python scripts/migrate_main_strategies.py`

**"OPENAI_API_KEY not set"**:
- Set environment variable or add to `.env`

**"No traces found for strategy"**:
- Verify strategy has been executed
- Check strategy slug is exact match
- Ensure traces have `metadata.strategy_slug` field

**"Validation failed"**:
- Check YAML syntax (indentation, quotes)
- Verify required fields: meta, tool_chain
- Check variable interpolation: `{{var}}` not `{var}`

## Examples

See `SKILL.md` for detailed examples of:
- German legal research strategy
- Multi-language query analysis
- Performance optimization recommendations
- Error pattern analysis

## Related Skills

- **langfuse-optimization**: Broader config optimization (style.yaml, template.yaml)
- **langfuse-advanced-filters**: Surgical trace queries with complex filters
- **batch-execution-validator**: Daily batch job validation
