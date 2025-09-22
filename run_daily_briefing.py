#!/usr/bin/env python3
"""Run a daily news briefing for a given topic."""

import argparse
import sys
import os
import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.graph import build_graph
from core.state import State
from tools import register_default_adapters
from core.langfuse_tracing import workflow_span, flush_traces


def setup_environment():
    """Load environment variables from .env if it exists."""
    try:
        from dotenv import load_dotenv
        if Path('.env').exists():
            load_dotenv()
            print("[INFO] Loaded environment from .env file")
    except ImportError:
        pass

def run_briefing(topic: str, industry: str = None, timeframe: str = "last 24 hours", verbose: bool = False):
    """Run the daily news briefing workflow."""
    
    print("=" * 60)
    print("DAILY NEWS BRIEFING")
    print("=" * 60)
    print(f"Topic: {topic}")
    if industry:
        print(f"Industry: {industry}")
    print(f"Timeframe: {timeframe}")
    print("-" * 60)
    print()
    
    workflow_input = {
        "topic": topic,
        "industry": industry,
        "timeframe": timeframe,
    }

    with workflow_span(
        name="daily-news-briefing",
        trace_input=workflow_input,
        tags=["workflow:daily-briefing"],
        metadata={"version": "1.0"},
    ) as tracing:
        # Register tools
        print("[1/5] Registering tools...")
        try:
            register_default_adapters(silent=False)
            print("  [OK] Tools registered")
        except Exception as e:
            print(f"  [ERROR] Failed to register tools: {e}")
            tracing.update_trace(metadata={"status": "failed", "error": str(e)})
            tracing.flush()
            return False

        # Build graph
        print("[2/5] Building workflow graph...")
        try:
            graph = build_graph()
            print("  [OK] Graph built")
        except Exception as e:
            print(f"  [ERROR] Failed to build graph: {e}")
            tracing.update_trace(metadata={"status": "failed", "error": str(e)})
            tracing.flush()
            return False

        # Prepare state
        print("[3/5] Preparing research state...")
        state = State(
            user_request=f"Daily briefing on {topic}" + (f" in {industry}" if industry else ""),
            strategy_slug="daily_news_briefing",
            time_window=timeframe,  # The fill phase will calculate dates from this
            vars={
                "topic": topic,
                "industry": industry or "",
                "timeframe": timeframe,
                # Dates will be calculated and added by the fill phase
            }
        )
        print("  [OK] State prepared")

        # Run workflow
        print("[4/5] Running research workflow...")
        print("  This may take 1-2 minutes...")
        try:
            if verbose:
                print("\n  Progress:")

            callbacks = []
            if tracing.handler:
                callbacks.append(tracing.handler)

            invoke_config: Dict[str, Any] = {
                "configurable": {"thread_id": f"briefing_{datetime.now().strftime('%Y%m%d_%H%M%S')}"}
            }
            if callbacks:
                invoke_config["callbacks"] = callbacks

            result = graph.invoke(state, invoke_config)
            print(f"  [OK] Research complete")

            if hasattr(result, 'evidence'):
                evidence = result.evidence
                sections = result.sections
                citations = result.citations
                vars_dict = result.vars
            else:
                evidence = result.get('evidence', [])
                sections = result.get('sections', [])
                citations = result.get('citations', [])
                vars_dict = result.get('vars', {})

            tracing.set_output(
                output={
                    "sections": sections,
                    "citations": citations,
                    "briefing_content": vars_dict.get("briefing_content"),
                },
                metadata={
                    "status": "success",
                    "evidence_items": len(evidence),
                    "sections_count": len(sections),
                    "citations_count": len(citations),
                },
            )

            print(f"  - Evidence collected: {len(evidence)} items")
            print(f"  - Sections generated: {len(sections)}")
            print(f"  - Citations: {len(citations)}")
        except Exception as e:
            print(f"  [ERROR] Workflow failed: {e}")
            tracing.update_trace(metadata={"status": "failed", "error": str(e)})
            if verbose:
                import traceback
                traceback.print_exc()
            tracing.flush()
            return False
    
    # Output results
    print("[5/5] Generating output...")
    print()
    print("=" * 60)
    print("BRIEFING RESULTS")
    print("=" * 60)
    
    # Check if we have the synthesized briefing content
    if "briefing_content" in vars_dict:
        briefing = vars_dict["briefing_content"]
        if isinstance(briefing, list) and len(briefing) > 0:
            # Extract the synthesized content from Evidence object
            content = briefing[0].snippet if hasattr(briefing[0], 'snippet') else str(briefing[0])
            print("\nSYNTHESIZED BRIEFING")
            print("-" * 40)
            # Handle encoding issues for Windows console
            try:
                print(content)
            except UnicodeEncodeError:
                # Replace problematic characters
                safe_content = content.encode('ascii', 'replace').decode('ascii')
                print(safe_content)
            print()
    elif "daily_briefing" in vars_dict:
        # Fallback to old format if it exists
        briefing = vars_dict["daily_briefing"]
        if isinstance(briefing, dict):
            # Output structured briefing
            if "executive_summary" in briefing:
                print("\nEXECUTIVE SUMMARY")
                print("-" * 40)
                summary = briefing["executive_summary"]
                if isinstance(summary, dict):
                    print(f"Headline: {summary.get('headline', 'N/A')}")
                    print(f"Context: {summary.get('key_context', 'N/A')}")
            
            if "key_takeaways" in briefing:
                print("\nKEY TAKEAWAYS")
                print("-" * 40)
                for i, takeaway in enumerate(briefing["key_takeaways"][:5], 1):
                    if isinstance(takeaway, dict):
                        print(f"{i}. {takeaway.get('takeaway', 'N/A')}")
                        print(f"   Impact: {takeaway.get('impact', 'N/A')}")
                        print(f"   Confidence: {takeaway.get('confidence', 'N/A')}")
                        print()
    
    # Output sections only if no synthesized briefing
    if not vars_dict.get("briefing_content"):
        if sections:
            print("\nDETAILED SECTIONS")
            print("-" * 40)
            for section in sections:
                try:
                    print(section)
                except UnicodeEncodeError:
                    # Handle Windows console encoding issues
                    safe_section = section.encode('utf-8', 'replace').decode('utf-8')
                    print(safe_section)
                print()
        
        # Output citations only if no synthesized briefing
        if citations:
            print("\nSOURCES")
            print("-" * 40)
            for i, citation in enumerate(citations[:10], 1):
                if isinstance(citation, dict):
                    date = citation.get('date', 'n.d.')
                    print(f"{i}. {citation.get('title', 'Unknown')} ({date}) {citation.get('url', 'N/A')}")
                else:
                    print(f"{i}. {citation}")
                print()
    
    # Save to file if requested
    if sections or vars_dict.get("briefing_content") or vars_dict.get("daily_briefing"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"briefing_{topic.replace(' ', '_')}_{timestamp}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Daily News Briefing: {topic}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Write synthesized briefing if available
            if "briefing_content" in vars_dict:
                briefing = vars_dict["briefing_content"]
                if isinstance(briefing, list) and len(briefing) > 0:
                    content = briefing[0].snippet if hasattr(briefing[0], 'snippet') else str(briefing[0])
                    f.write(content)
                    f.write("\n\n")
            
            # Write sections if no synthesized briefing
            elif sections:
                for section in sections:
                    f.write(f"{section}\n\n")
                
                # Only add citations if no briefing_content (since briefing already has ALL SOURCES)
                if citations:
                    f.write("\n## Sources\n")
                    for citation in citations:
                        if isinstance(citation, dict):
                            date = citation.get('date', 'n.d.')
                            f.write(f"- {citation.get('title', 'Unknown')} ({date}) [{citation.get('url', '#')}]\n")
                        else:
                            f.write(f"- {citation}\n")
        
        print(f"\n[INFO] Briefing saved to: {filename}")
    
    tracing.flush()
    flush_traces()
    return True

def main():
    parser = argparse.ArgumentParser(description='Generate a daily news briefing on a topic')
    parser.add_argument('--topic', '-t', required=True, help='Topic to research')
    parser.add_argument('--industry', '-i', help='Industry context (optional)')
    parser.add_argument('--timeframe', '-f', default='last 24 hours', 
                       help='Timeframe (default: "last 24 hours")')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Setup environment
    setup_environment()
    
    # Check for API keys
    has_keys = True
    if not os.getenv('OPENAI_API_KEY'):
        print("[ERROR] OPENAI_API_KEY not set")
        has_keys = False
    if not os.getenv('EXA_API_KEY'):
        print("[ERROR] EXA_API_KEY not set")
        has_keys = False
    if not (os.getenv('SONAR_API_KEY') or os.getenv('OPENAI_API_KEY')):
        print("[ERROR] Neither SONAR_API_KEY nor OPENAI_API_KEY set (need at least one)")
        has_keys = False
    
    if not has_keys:
        print("\nPlease set the required API keys. See SETUP_GUIDE.md for instructions.")
        sys.exit(1)
    
    # Run briefing
    success = run_briefing(
        topic=args.topic,
        industry=args.industry,
        timeframe=args.timeframe,
        verbose=args.verbose
    )
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
