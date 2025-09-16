# Sonar API Parameters Guide

This document describes all available parameters for configuring Sonar (Perplexity) API calls in strategy YAML files.

## Overview

The Sonar adapter now supports all official Perplexity API parameters, allowing fine-grained control over search behavior, response generation, and result filtering directly from strategy configurations.

## Available Parameters

### Core Parameters

#### `system_prompt` (string)
- **Description**: Sets the system message to guide the AI's behavior
- **Default**: None
- **Example**: 
```yaml
system_prompt: "Be concise and focus on factual information with dates."
```

#### `search_mode` (string)
- **Description**: Controls the type of search performed
- **Options**: `"web"` (default), `"academic"`
- **Example**:
```yaml
search_mode: "academic"  # For research papers and scholarly articles
```

### Search Filtering

#### `search_domain_filter` (array)
- **Description**: Limits search results to specific domains
- **Maximum**: 20 domains
- **Default**: None (searches all domains)
- **Example**:
```yaml
search_domain_filter:
  - "reuters.com"
  - "bloomberg.com"
  - "wsj.com"
```

#### `search_recency_filter` (string)
- **Description**: Filters results by time period
- **Options**: `"day"`, `"week"`, `"month"`, `"year"`
- **Default**: None (no time filter)
- **Example**:
```yaml
search_recency_filter: "week"  # Only results from last 7 days
```

### Response Configuration

#### `max_tokens` (integer)
- **Description**: Maximum tokens in the response
- **Default**: Model dependent
- **Example**:
```yaml
max_tokens: 2000
```

#### `temperature` (number)
- **Description**: Controls response randomness/creativity
- **Range**: 0.0 to 2.0
- **Default**: 0.2
- **Example**:
```yaml
temperature: 0.1  # Very factual, low creativity
```

#### `top_p` (number)
- **Description**: Nucleus sampling parameter
- **Range**: 0.0 to 1.0
- **Default**: 0.9
- **Example**:
```yaml
top_p: 0.95
```

### Additional Options

#### `return_images` (boolean)
- **Description**: Include images in search results
- **Default**: false
- **Example**:
```yaml
return_images: true
```

#### `return_related_questions` (boolean)
- **Description**: Return related questions with the response
- **Default**: false
- **Example**:
```yaml
return_related_questions: true
```

#### `stream` (boolean)
- **Description**: Enable streaming response mode
- **Default**: false
- **Example**:
```yaml
stream: false  # Batch mode (wait for complete response)
```

### Advanced Parameters

#### `reasoning_effort` (string)
- **Description**: Controls computational effort (only for `sonar-deep-research` model)
- **Options**: `"low"`, `"medium"`, `"high"`
- **Default**: Model dependent
- **Example**:
```yaml
reasoning_effort: "high"  # Maximum analysis depth
```

#### `disable_search` (boolean)
- **Description**: Disable web search entirely (use only model knowledge)
- **Default**: false
- **Example**:
```yaml
disable_search: true  # No web search, only model knowledge
```

## Complete Example

Here's a comprehensive example showing multiple Sonar configurations in a single strategy:

```yaml
meta:
  slug: multi_sonar_example
  version: 1
  category: research
  time_window: custom
  depth: deep

tool_chain:
  # Financial news with domain restrictions
  - name: sonar_financial
    params:
      system_prompt: "Focus on financial data, percentages, and market movements."
      search_mode: "web"
      search_domain_filter:
        - "bloomberg.com"
        - "reuters.com"
        - "ft.com"
      search_recency_filter: "day"
      temperature: 0.1
      max_tokens: 1500
      return_related_questions: true
  
  # Academic research
  - name: sonar_research
    params:
      system_prompt: "Find peer-reviewed research and cite sources."
      search_mode: "academic"
      search_recency_filter: "year"
      temperature: 0.2
      max_tokens: 2000
  
  # Quick facts lookup
  - name: sonar_facts
    params:
      system_prompt: "Provide quick, factual answers."
      temperature: 0.0  # Deterministic
      max_tokens: 500
      disable_search: false
```

## Strategy Integration Tips

1. **Use system prompts** to guide the AI toward domain-specific responses
2. **Domain filtering** is powerful for ensuring source quality
3. **Recency filters** help focus on current events vs historical context
4. **Temperature** should be low (0.0-0.3) for factual research, higher for creative tasks
5. **Academic mode** is best for scholarly research and citations
6. **Related questions** can help discover adjacent research topics

## Migration Guide

If you have existing strategies using Sonar, they will continue to work. The adapter maintains backward compatibility while adding these new capabilities. To enhance existing strategies:

1. Add a `system_prompt` to improve response quality
2. Add `search_recency_filter` to focus on recent information
3. Add `search_domain_filter` for trusted sources
4. Lower `temperature` for more consistent factual responses

## Model Support

Different Sonar models support different parameters:
- **sonar**: All parameters except `reasoning_effort`
- **sonar-pro**: All parameters except `reasoning_effort`
- **sonar-deep-research**: All parameters including `reasoning_effort`
- **sonar-reasoning**: Focus on reasoning capabilities
- **sonar-reasoning-pro**: Enhanced reasoning model