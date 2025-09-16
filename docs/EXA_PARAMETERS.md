# Exa API Parameters Guide

This document provides comprehensive documentation for all available Exa API parameters that can be used in strategy YAML files.

## Overview

The Exa adapter now supports all official Exa API parameters across four main endpoints:
- **Search**: Find webpages using neural or keyword search
- **Contents**: Retrieve and process webpage content
- **Find Similar**: Discover similar pages based on a URL
- **Answer**: Get direct answers to questions

## Search Endpoint Parameters

### Search Type Configuration

#### `type` (string)
- **Description**: Determines the search algorithm used
- **Options**: 
  - `"auto"` (default): Intelligently combines neural and keyword search
  - `"neural"`: Embeddings-based semantic search
  - `"keyword"`: Traditional keyword matching
  - `"fast"`: Optimized for speed
- **Example**:
```yaml
type: "neural"  # For semantic understanding
```

#### `use_autoprompt` (boolean)
- **Description**: Auto-optimize query for neural search
- **Default**: false
- **Note**: Only works with neural search type
- **Example**:
```yaml
use_autoprompt: true
```

### Content Filtering

#### `category` (string)
- **Description**: Filter results by content type
- **Options**: 
  - `"company"`
  - `"research paper"`
  - `"news"`
  - `"pdf"`
  - `"github"`
  - `"tweet"`
  - `"personal site"`
  - `"linkedin profile"`
  - `"financial report"`
- **Example**:
```yaml
category: "research paper"
```

#### `num_results` (integer)
- **Description**: Number of results to return
- **Range**: 1-100
- **Default**: 10
- **Example**:
```yaml
num_results: 25
```

### Date Filtering

All date parameters use ISO 8601 format: `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`

#### `start_crawl_date` (string)
- **Description**: Include only links crawled after this date
- **Example**:
```yaml
start_crawl_date: "2024-01-01"
```

#### `end_crawl_date` (string)
- **Description**: Include only links crawled before this date
- **Example**:
```yaml
end_crawl_date: "2024-12-31"
```

#### `start_published_date` (string)
- **Description**: Include only content published after this date
- **Example**:
```yaml
start_published_date: "{{start_date}}"  # Can use template variables
```

#### `end_published_date` (string)
- **Description**: Include only content published before this date
- **Example**:
```yaml
end_published_date: "{{end_date}}"
```

### Domain Filtering

#### `include_domains` (array)
- **Description**: Limit results to specific domains
- **Note**: Can include subdomains
- **Example**:
```yaml
include_domains:
  - "arxiv.org"
  - "nature.com"
  - "blog.openai.com"
```

#### `exclude_domains` (array)
- **Description**: Exclude specific domains from results
- **Example**:
```yaml
exclude_domains:
  - "spam-site.com"
  - "unreliable-news.net"
```

### Text Content Filtering

#### `include_text` (string)
- **Description**: Results must contain this text
- **Limitation**: Single string, maximum 5 words
- **Example**:
```yaml
include_text: "machine learning breakthrough"
```

#### `exclude_text` (string)
- **Description**: Results must NOT contain this text in first 1000 words
- **Limitation**: Single string, maximum 5 words
- **Example**:
```yaml
exclude_text: "sponsored content"
```

### Additional Search Options

#### `user_location` (string)
- **Description**: Two-letter ISO country code to bias results
- **Example**:
```yaml
user_location: "US"  # Bias toward US sources
```

#### `moderation` (boolean)
- **Description**: Filter potentially unsafe content
- **Default**: false
- **Example**:
```yaml
moderation: true
```

#### `context` (boolean/object)
- **Description**: Format results for LLM consumption
- **Default**: false
- **Example**:
```yaml
context: true  # Optimize for AI processing
```

## Contents Endpoint Parameters

### Text Retrieval

#### `text` (boolean/object)
- **Description**: Configure text extraction
- **Options**:
  - `true`: Return full text with defaults
  - `false`: Don't return text
  - Object with options:
    - `include_html_tags`: Include HTML markup
    - `max_characters`: Limit text length
- **Example**:
```yaml
text:
  include_html_tags: false
  max_characters: 5000
```

### Highlight Extraction

#### `highlights` (object)
- **Description**: Extract most relevant snippets
- **Options**:
  - `query`: Search terms for relevance
  - `num_sentences`: Sentences per highlight
  - `highlights_per_url`: Number of highlights
- **Example**:
```yaml
highlights:
  query: "key findings conclusions"
  num_sentences: 3
  highlights_per_url: 5
```

### Summary Generation

#### `summary` (object)
- **Description**: Generate webpage summary
- **Options**:
  - `length`: `"short"`, `"medium"`, `"long"`
- **Example**:
```yaml
summary:
  length: "medium"
```

### Crawling Configuration

#### `livecrawl` (string)
- **Description**: Control real-time crawling behavior
- **Options**:
  - `"never"`: Only use cache
  - `"fallback"`: Use cache, crawl if empty (default for keyword)
  - `"always"`: Always crawl fresh content
  - `"preferred"`: Try crawl first, use cache if fails
- **Example**:
```yaml
livecrawl: "preferred"
```

#### `livecrawl_timeout` (integer)
- **Description**: Timeout for live crawling in milliseconds
- **Default**: 10000 (10 seconds)
- **Example**:
```yaml
livecrawl_timeout: 15000  # 15 seconds
```

### Subpage Crawling

#### `subpages` (integer)
- **Description**: Number of subpages to crawl
- **Default**: 0
- **Example**:
```yaml
subpages: 3
```

#### `subpage_target` (string/array)
- **Description**: Keywords to find specific subpages
- **Example**:
```yaml
subpage_target: "documentation"
# Or multiple targets:
subpage_target:
  - "api"
  - "reference"
```

## Find Similar Endpoint Parameters

Most parameters are similar to the search endpoint:

### Unique Parameters

#### `exclude_source_domain` (boolean)
- **Description**: Exclude the source URL's domain from results
- **Default**: false
- **Example**:
```yaml
exclude_source_domain: true  # Get different sources
```

### Shared Parameters
- `num_results`: Number of similar pages (1-100)
- `include_domains`: Domains to include
- `exclude_domains`: Domains to exclude
- `start_crawl_date`: Crawl date filter
- `end_crawl_date`: Crawl date filter
- `start_published_date`: Publication date filter
- `end_published_date`: Publication date filter
- `include_text`: Required text
- `exclude_text`: Excluded text
- `category`: Content type filter
- `moderation`: Safety filter
- `context`: LLM formatting

## Answer Endpoint Parameters

#### `stream` (boolean)
- **Description**: Return response as server-sent events stream
- **Default**: false
- **Example**:
```yaml
stream: false  # Get complete answer at once
```

#### `text` (boolean)
- **Description**: Include full text content in response
- **Default**: false
- **Example**:
```yaml
text: true  # Include source texts
```

## Complete Strategy Example

```yaml
meta:
  slug: comprehensive_research
  version: 1
  category: research
  time_window: week
  depth: deep

tool_chain:
  # Advanced neural search with all filters
  - name: exa_deep_search
    params:
      type: "neural"
      use_autoprompt: true
      category: "research paper"
      num_results: 20
      start_published_date: "{{start_date}}"
      end_published_date: "{{end_date}}"
      include_domains:
        - "arxiv.org"
        - "nature.com"
      exclude_domains:
        - "predatory-journal.com"
      include_text: "peer reviewed"
      exclude_text: "preprint"
      user_location: "US"
      moderation: false
      context: true
  
  # Get detailed contents with highlights
  - name: exa_extract_contents
    params:
      text:
        include_html_tags: false
        max_characters: 10000
      highlights:
        query: "methodology results conclusions"
        num_sentences: 5
      summary:
        length: "long"
      livecrawl: "preferred"
      livecrawl_timeout: 20000
  
  # Find similar research
  - name: exa_similar_research
    params:
      num_results: 10
      exclude_source_domain: true
      category: "research paper"
      start_published_date: "{{start_date}}"
```

## Migration Tips

1. **Replace deprecated parameters**:
   - `max_results` → `num_results`
   - `start_date` → `start_published_date`
   - `end_date` → `end_published_date`

2. **Optimize search type**:
   - Use `"neural"` for semantic/conceptual searches
   - Use `"keyword"` for exact matches
   - Use `"fast"` when speed is critical
   - Use `"auto"` when unsure

3. **Leverage categories**:
   - Filter by content type for more relevant results
   - Combine with domain filters for precision

4. **Date filtering best practices**:
   - Use `published_date` for content recency
   - Use `crawl_date` for index freshness
   - Combine both for comprehensive filtering

5. **Content extraction**:
   - Use `highlights` for quick summaries
   - Use `text` with `max_characters` for controlled extraction
   - Use `livecrawl: "preferred"` for real-time content

## Performance Considerations

- **Neural search** is slower but more accurate for semantic queries
- **Keyword search** is faster for exact matches
- **Autoprompt** adds latency but improves neural search quality
- **Livecrawl** adds 5-20 seconds depending on site complexity
- **Large `num_results`** (>50) may increase response time
- **Domain filters** can speed up searches by limiting scope

## Error Handling

The adapter handles various response formats and provides graceful fallbacks:
- Missing fields default to `None`
- Both dictionary and object responses are supported
- Network errors trigger automatic retries
- Invalid parameters are passed through (may cause API errors)