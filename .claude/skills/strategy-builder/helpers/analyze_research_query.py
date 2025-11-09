#!/usr/bin/env python3
"""
Analyze Research Query

Classifies a research query and determines if existing strategies match,
or if a new strategy should be created.

USAGE:
======
# Basic analysis
python3 analyze_research_query.py \
  --query "Suche mir alle Informationen über gerichtsurteile an deutschen Gerichten"

# With context
python3 analyze_research_query.py \
  --query "Monitor Tesla product launches" \
  --frequency "weekly" \
  --depth "comprehensive"

# Save output
python3 analyze_research_query.py \
  --query "Daily AI regulation news" \
  --output /tmp/analysis.json
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from strategies import load_strategy_index, StrategyIndexEntry
    from openai import OpenAI
except ImportError as e:
    print(f"Error: Missing dependencies: {e}", file=sys.stderr)
    print("Run from project root: /home/user/web_research_agent", file=sys.stderr)
    sys.exit(1)


def detect_language(query: str) -> str:
    """Detect query language (basic heuristic)."""
    # German indicators
    german_words = {'über', 'alle', 'informationen', 'der', 'die', 'das', 'ein', 'eine', 'gerichtsurteile', 'deutschen'}
    query_lower = query.lower()
    german_matches = sum(1 for word in german_words if word in query_lower)

    # Spanish indicators
    spanish_words = {'sobre', 'todos', 'información', 'el', 'la', 'los', 'las', 'un', 'una'}
    spanish_matches = sum(1 for word in spanish_words if word in query_lower)

    # French indicators
    french_words = {'sur', 'tous', 'toutes', 'information', 'le', 'la', 'les', 'un', 'une', 'des'}
    french_matches = sum(1 for word in french_words if word in query_lower)

    if german_matches >= 2:
        return "de"
    elif spanish_matches >= 2:
        return "es"
    elif french_matches >= 2:
        return "fr"
    else:
        return "en"


def classify_query(query: str, frequency: Optional[str] = None, depth: Optional[str] = None) -> Dict[str, Any]:
    """Use LLM to classify research query."""

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Build prompt
    prompt = f"""You are a research strategy classifier. Analyze this research query and extract structured information.

Query: "{query}"

Context:
- Frequency hint: {frequency or "not specified"}
- Depth hint: {depth or "not specified"}

Classify the query into:

1. **category** (pick ONE that best fits):
   - news: breaking news, daily updates, current events
   - general: broad topics, overview research
   - company: corporate research, company profiles
   - financial: market analysis, stock research, financial data
   - finance: financial planning, economic analysis
   - academic: research papers, scientific literature
   - legal: court cases, legal research, legislation
   - technical: technical documentation, how-to guides
   - regulatory: regulations, compliance, policy changes
   - competitive: competitor analysis, market intelligence

2. **time_window** (how far back to search):
   - day: last 24 hours, real-time
   - week: last 7 days, recent
   - month: last 30 days, current period
   - year: last 12 months, historical

3. **depth** (research thoroughness):
   - brief: quick summary, headlines
   - overview: broad scan, multiple topics
   - deep: thorough analysis, detailed
   - comprehensive: exhaustive research, all aspects

4. **required_variables**: List of variables needed (e.g., topic, company, jurisdiction)

5. **suggested_tools**: Which research tools would work best:
   - sonar_search: real-time web search with citations
   - exa_search_semantic: semantic/neural search
   - exa_search_keyword: keyword-based search
   - exa_contents: fetch full content
   - exa_answer: direct answer synthesis
   - llm_analyzer: LLM-based analysis

6. **domain_hints**: Specific domains/sources to prioritize (if applicable)

Return ONLY valid JSON with this structure:
{{
  "category": "...",
  "time_window": "...",
  "depth": "...",
  "required_variables": [
    {{"name": "variable_name", "description": "what it represents"}}
  ],
  "suggested_tools": ["tool1", "tool2"],
  "domain_hints": ["domain1.com", "domain2.com"],
  "reasoning": "brief explanation of classification"
}}"""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a research strategy expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        classification = json.loads(response.choices[0].message.content)
        return classification

    except Exception as e:
        print(f"Error calling OpenAI API: {e}", file=sys.stderr)
        # Fallback to simple classification
        return {
            "category": "general",
            "time_window": "week",
            "depth": depth or "deep",
            "required_variables": [{"name": "topic", "description": "Research topic"}],
            "suggested_tools": ["sonar_search", "exa_search_semantic", "llm_analyzer"],
            "domain_hints": [],
            "reasoning": "Fallback classification due to API error"
        }


def find_matching_strategy(
    category: str,
    time_window: str,
    depth: str,
    strategies: List[StrategyIndexEntry]
) -> Optional[StrategyIndexEntry]:
    """Find existing strategy that matches classification."""

    # Exact match
    for strategy in strategies:
        if (strategy.category == category and
            strategy.time_window == time_window and
            strategy.depth == depth and
            strategy.active):
            return strategy

    # Partial match (category + time_window, flexible on depth)
    for strategy in strategies:
        if (strategy.category == category and
            strategy.time_window == time_window and
            strategy.active):
            return strategy

    # Partial match (category only, closest depth/time)
    category_matches = [s for s in strategies if s.category == category and s.active]
    if category_matches:
        # Return highest priority match
        return sorted(category_matches, key=lambda s: s.priority)[0]

    return None


def calculate_match_quality(
    classification: Dict[str, Any],
    strategy: StrategyIndexEntry
) -> float:
    """Calculate how well a strategy matches the classification (0-100)."""

    score = 0.0

    # Category match (40 points)
    if strategy.category == classification["category"]:
        score += 40

    # Time window match (30 points)
    if strategy.time_window == classification["time_window"]:
        score += 30
    elif strategy.time_window == "week" and classification["time_window"] == "day":
        score += 15  # Week can cover day
    elif strategy.time_window == "month" and classification["time_window"] in ["day", "week"]:
        score += 10  # Month can cover shorter periods

    # Depth match (30 points)
    depth_map = {"brief": 1, "overview": 2, "deep": 3, "comprehensive": 4}
    strat_depth = depth_map.get(strategy.depth, 2)
    class_depth = depth_map.get(classification["depth"], 2)
    depth_diff = abs(strat_depth - class_depth)
    score += max(0, 30 - (depth_diff * 10))

    return min(100, score)


def suggest_new_slug(classification: Dict[str, Any]) -> str:
    """Suggest slug for new strategy."""

    category = classification["category"]

    # Extract key topic words from reasoning
    reasoning = classification.get("reasoning", "").lower()

    # Domain-specific slug suggestions
    if category == "legal":
        if "court" in reasoning or "case" in reasoning:
            return f"legal/court_cases"
        elif "regulation" in reasoning or "compliance" in reasoning:
            return f"legal/regulatory"
        else:
            return f"legal/general_research"

    elif category == "technical":
        if "documentation" in reasoning:
            return f"technical/documentation"
        elif "how" in reasoning or "guide" in reasoning:
            return f"technical/guides"
        else:
            return f"technical/research"

    elif category in ["news", "general", "financial", "finance", "academic", "company"]:
        # Use existing pattern
        time_window = classification["time_window"]
        depth = classification["depth"]
        return f"{category}/{time_window}_{depth}"

    else:
        # Generic pattern
        return f"{category}/research"


def analyze_query(
    query: str,
    frequency: Optional[str] = None,
    depth: Optional[str] = None,
    language: Optional[str] = None
) -> Dict[str, Any]:
    """Main analysis function."""

    # Detect language
    if not language:
        language = detect_language(query)

    # Load existing strategies
    try:
        strategies = load_strategy_index()
        print(f"✓ Loaded {len(strategies)} existing strategies", file=sys.stderr)
    except Exception as e:
        print(f"⚠️  Could not load strategies: {e}", file=sys.stderr)
        strategies = []

    # Classify query
    print("Classifying query...", file=sys.stderr)
    classification = classify_query(query, frequency, depth)
    classification["language"] = language

    # Find matching strategy
    matching_strategy = find_matching_strategy(
        classification["category"],
        classification["time_window"],
        classification["depth"],
        strategies
    )

    # Build result
    result = {
        "query": query,
        "classification": classification,
        "existing_strategies_count": len(strategies),
        "existing_categories": list(set(s.category for s in strategies)),
    }

    if matching_strategy:
        match_quality = calculate_match_quality(classification, matching_strategy)
        result["existing_match"] = {
            "slug": matching_strategy.slug,
            "title": matching_strategy.title,
            "description": matching_strategy.description,
            "match_quality": round(match_quality, 1),
            "priority": matching_strategy.priority,
            "fan_out": matching_strategy.normalized_fan_out(),
            "required_variables": [
                {"name": v.name, "description": v.description}
                for v in matching_strategy.required_variables
            ]
        }

        if match_quality >= 80:
            result["recommendation"] = "use_existing"
            result["recommendation_reasoning"] = f"Excellent match ({match_quality}%). Use existing strategy."
        elif match_quality >= 60:
            result["recommendation"] = "use_existing_with_caution"
            result["recommendation_reasoning"] = f"Good match ({match_quality}%). May need minor adjustments."
        else:
            result["recommendation"] = "modify_existing"
            result["recommendation_reasoning"] = f"Partial match ({match_quality}%). Consider creating variant."
    else:
        result["existing_match"] = None
        result["recommendation"] = "create_new_strategy"
        result["recommendation_reasoning"] = (
            f"No existing strategy covers {classification['category']} research. "
            f"Existing categories: {', '.join(result['existing_categories'])}"
        )
        result["suggested_slug"] = suggest_new_slug(classification)

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Analyze research query and recommend strategy',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  %(prog)s --query "Daily AI news"

  # With context
  %(prog)s --query "German court cases" --frequency weekly --depth comprehensive

  # Save output
  %(prog)s --query "Tesla launches" --output /tmp/analysis.json
        """
    )

    parser.add_argument('--query', required=True, help='Research query to analyze')
    parser.add_argument('--frequency', choices=['daily', 'weekly', 'monthly', 'yearly'],
                       help='How often to run the research')
    parser.add_argument('--depth', choices=['brief', 'overview', 'deep', 'comprehensive'],
                       help='Desired research depth')
    parser.add_argument('--language', choices=['en', 'de', 'es', 'fr'],
                       help='Query language (auto-detected if not specified)')
    parser.add_argument('--output', default='/tmp/strategy_analysis/query_analysis.json',
                       help='Output file path')

    args = parser.parse_args()

    # Map frequency to time_window
    frequency_map = {
        'daily': 'day',
        'weekly': 'week',
        'monthly': 'month',
        'yearly': 'year'
    }
    depth_arg = args.depth
    if args.frequency:
        # Use frequency as hint for classification
        pass

    try:
        result = analyze_query(
            query=args.query,
            frequency=args.frequency,
            depth=depth_arg,
            language=args.language
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        # Print summary
        print("\n" + "="*60)
        print("QUERY ANALYSIS SUMMARY")
        print("="*60)
        print(f"\nQuery: {result['query']}")
        print(f"\nClassification:")
        print(f"  Category: {result['classification']['category']}")
        print(f"  Time Window: {result['classification']['time_window']}")
        print(f"  Depth: {result['classification']['depth']}")
        print(f"  Language: {result['classification']['language']}")

        print(f"\nRecommendation: {result['recommendation']}")
        print(f"Reasoning: {result['recommendation_reasoning']}")

        if result['existing_match']:
            match = result['existing_match']
            print(f"\nMatched Strategy:")
            print(f"  Slug: {match['slug']}")
            print(f"  Title: {match['title']}")
            print(f"  Match Quality: {match['match_quality']}%")
        else:
            print(f"\nSuggested New Slug: {result.get('suggested_slug', 'N/A')}")

        print(f"\n✓ Full analysis saved to: {output_path}")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
