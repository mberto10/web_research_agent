#!/usr/bin/env python3
"""
Debug Log Viewer - Interactive analysis tool for research workflow logs

Usage:
    python debug_viewer.py                    # View latest log
    python debug_viewer.py debug_20250122_143025.jsonl  # View specific log
    python debug_viewer.py --summary          # Show summary of latest session
    python debug_viewer.py --prompts          # Extract all prompts
    python debug_viewer.py --errors           # Show only errors
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
from collections import defaultdict


class DebugLogViewer:
    """Interactive viewer for debug logs."""
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.events = []
        self.load_events()
    
    def load_events(self) -> None:
        """Load all events from JSONL file."""
        if not self.log_file.exists():
            print(f"Error: Log file not found: {self.log_file}")
            sys.exit(1)
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        self.events.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"Warning: Skipping invalid JSON line: {e}")
    
    def show_summary(self) -> None:
        """Display session summary."""
        if not self.events:
            print("No events found in log file.")
            return
        
        print(f"\n{'='*80}")
        print(f"DEBUG LOG SUMMARY: {self.log_file.name}")
        print(f"{'='*80}")
        
        # Time range
        start_time = self.events[0].get('timestamp', '')
        end_time = self.events[-1].get('timestamp', '')
        print(f"\nSession Time: {start_time} to {end_time}")
        print(f"Total Events: {len(self.events)}")
        
        # Event type breakdown
        event_types = defaultdict(int)
        for event in self.events:
            event_types[event.get('type', 'unknown')] += 1
        
        print(f"\n{'Event Types':20} {'Count':>10}")
        print("-" * 30)
        for event_type, count in sorted(event_types.items()):
            print(f"{event_type:20} {count:>10}")
        
        # Node performance
        print(f"\n{'='*80}")
        print("NODE PERFORMANCE")
        print(f"{'='*80}")
        
        node_times = defaultdict(list)
        for event in self.events:
            if event.get('type') == 'node_end':
                node = event.get('node', 'unknown')
                elapsed = event.get('elapsed_seconds', 0)
                node_times[node].append(elapsed)
        
        print(f"\n{'Node':15} {'Runs':>6} {'Total(s)':>10} {'Avg(s)':>10} {'Max(s)':>10}")
        print("-" * 55)
        for node, times in sorted(node_times.items()):
            total = sum(times)
            avg = total / len(times) if times else 0
            max_time = max(times) if times else 0
            print(f"{node:15} {len(times):>6} {total:>10.3f} {avg:>10.3f} {max_time:>10.3f}")
        
        # Tool usage
        print(f"\n{'='*80}")
        print("TOOL USAGE")
        print(f"{'='*80}")
        
        tool_calls = defaultdict(lambda: defaultdict(int))
        tool_times = defaultdict(list)
        
        for event in self.events:
            if event.get('type') == 'tool_call':
                provider = event.get('provider', 'unknown')
                method = event.get('method', 'unknown')
                tool_calls[provider][method] += 1
                if event.get('duration_seconds'):
                    tool_times[f"{provider}.{method}"].append(event['duration_seconds'])
        
        print(f"\n{'Provider.Method':30} {'Calls':>8} {'Avg Time(s)':>12}")
        print("-" * 52)
        for provider, methods in sorted(tool_calls.items()):
            for method, count in sorted(methods.items()):
                key = f"{provider}.{method}"
                times = tool_times.get(key, [])
                avg_time = sum(times) / len(times) if times else 0
                print(f"{key:30} {count:>8} {avg_time:>12.3f}")
        
        # LLM usage
        print(f"\n{'='*80}")
        print("LLM USAGE")
        print(f"{'='*80}")
        
        llm_stats = defaultdict(lambda: {'calls': 0, 'prompt_chars': 0, 'response_chars': 0, 'time': 0})
        
        for event in self.events:
            if event.get('type') == 'llm_call':
                model = event.get('model', 'unknown')
                stats = llm_stats[model]
                stats['calls'] += 1
                stats['prompt_chars'] += event.get('prompt_length', 0)
                stats['response_chars'] += event.get('response_length', 0)
                stats['time'] += event.get('duration_seconds', 0)
        
        print(f"\n{'Model':20} {'Calls':>8} {'Prompt Chars':>15} {'Response Chars':>15} {'Total Time(s)':>12}")
        print("-" * 72)
        for model, stats in sorted(llm_stats.items()):
            print(f"{model:20} {stats['calls']:>8} {stats['prompt_chars']:>15,} "
                  f"{stats['response_chars']:>15,} {stats['time']:>12.3f}")
        
        # Errors
        errors = [e for e in self.events if e.get('error') or (e.get('type') == 'node_end' and not e.get('success', True))]
        if errors:
            print(f"\n{'='*80}")
            print(f"ERRORS ({len(errors)} found)")
            print(f"{'='*80}")
            for error in errors[:5]:  # Show first 5 errors
                print(f"\n[{error.get('timestamp', 'N/A')}] {error.get('node', error.get('component', 'Unknown'))}")
                print(f"  Error: {error.get('error', 'N/A')}")
    
    def show_prompts(self) -> None:
        """Extract and display all prompts."""
        print(f"\n{'='*80}")
        print("LLM PROMPTS")
        print(f"{'='*80}")
        
        prompt_events = [e for e in self.events if e.get('type') == 'llm_call' and e.get('prompt')]
        
        for i, event in enumerate(prompt_events, 1):
            print(f"\n{'='*80}")
            print(f"Prompt #{i} - {event.get('component', 'Unknown')} - {event.get('model', 'Unknown')}")
            print(f"Timestamp: {event.get('timestamp', 'N/A')}")
            print(f"Hash: {event.get('prompt_hash', 'N/A')}")
            print(f"{'='*80}")
            
            prompt = event.get('prompt', '')
            if len(prompt) > 1000:
                print(prompt[:1000])
                print(f"\n... [Truncated {len(prompt) - 1000} chars]")
            else:
                print(prompt)
            
            if event.get('response') and event['response'] != '[disabled]':
                print(f"\n{'RESPONSE':^80}")
                print("-" * 80)
                response = event['response']
                if len(response) > 1000:
                    print(response[:1000])
                    print(f"\n... [Truncated {len(response) - 1000} chars]")
                else:
                    print(response)
    
    def show_errors(self) -> None:
        """Display all errors with context."""
        print(f"\n{'='*80}")
        print("ERRORS AND FAILURES")
        print(f"{'='*80}")
        
        errors = []
        for event in self.events:
            if event.get('error'):
                errors.append(event)
            elif event.get('type') == 'node_end' and not event.get('success', True):
                errors.append(event)
        
        if not errors:
            print("\nNo errors found in this session!")
            return
        
        for i, error in enumerate(errors, 1):
            print(f"\n{'='*80}")
            print(f"Error #{i}")
            print(f"{'='*80}")
            print(f"Timestamp: {error.get('timestamp', 'N/A')}")
            print(f"Type: {error.get('type', 'N/A')}")
            print(f"Component: {error.get('node', error.get('component', error.get('provider', 'Unknown')))}")
            print(f"Error: {error.get('error', 'N/A')}")
            
            if error.get('error_trace'):
                print(f"\nStack Trace:")
                print(error['error_trace'])
    
    def show_timeline(self) -> None:
        """Display execution timeline."""
        print(f"\n{'='*80}")
        print("EXECUTION TIMELINE")
        print(f"{'='*80}")
        
        # Filter for major events
        major_events = []
        for event in self.events:
            if event['type'] in ['node_start', 'node_end', 'strategy_selected', 'evidence_update']:
                major_events.append(event)
        
        print(f"\n{'Time':20} {'Type':15} {'Details':45}")
        print("-" * 80)
        
        for event in major_events:
            timestamp = event.get('timestamp', '')
            if timestamp:
                # Extract just time portion
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%H:%M:%S.%f')[:-3]
                except:
                    time_str = timestamp[:19]
            else:
                time_str = 'N/A'
            
            event_type = event.get('type', 'unknown')
            
            # Build details string
            details = []
            if event_type == 'node_start':
                details.append(f"Node: {event.get('node', 'unknown')}")
            elif event_type == 'node_end':
                details.append(f"Node: {event.get('node', 'unknown')}")
                details.append(f"Time: {event.get('elapsed_seconds', 0):.3f}s")
            elif event_type == 'strategy_selected':
                details.append(f"Strategy: {event.get('strategy', 'unknown')}")
            elif event_type == 'evidence_update':
                details.append(f"Added: {event.get('added_count', 0)}")
                details.append(f"Total: {event.get('total_count', 0)}")
            
            detail_str = ' | '.join(details)[:45]
            print(f"{time_str:20} {event_type:15} {detail_str:45}")
    
    def interactive_mode(self) -> None:
        """Interactive exploration of logs."""
        while True:
            print(f"\n{'='*80}")
            print("DEBUG LOG VIEWER - INTERACTIVE MODE")
            print(f"{'='*80}")
            print("\nOptions:")
            print("  1. Show Summary")
            print("  2. Show Timeline")
            print("  3. Show Prompts")
            print("  4. Show Errors")
            print("  5. Search Events")
            print("  6. Export Prompts to File")
            print("  0. Exit")
            
            try:
                choice = input("\nEnter choice: ").strip()
                
                if choice == '0':
                    break
                elif choice == '1':
                    self.show_summary()
                elif choice == '2':
                    self.show_timeline()
                elif choice == '3':
                    self.show_prompts()
                elif choice == '4':
                    self.show_errors()
                elif choice == '5':
                    search_term = input("Enter search term: ").strip()
                    self.search_events(search_term)
                elif choice == '6':
                    self.export_prompts()
                else:
                    print("Invalid choice. Please try again.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
    
    def search_events(self, search_term: str) -> None:
        """Search for events containing the search term."""
        print(f"\n{'='*80}")
        print(f"SEARCH RESULTS for '{search_term}'")
        print(f"{'='*80}")
        
        matches = []
        for event in self.events:
            event_str = json.dumps(event, ensure_ascii=False).lower()
            if search_term.lower() in event_str:
                matches.append(event)
        
        print(f"\nFound {len(matches)} matching events")
        
        for i, event in enumerate(matches[:20], 1):  # Show first 20
            print(f"\n{i}. [{event.get('timestamp', 'N/A')}] Type: {event.get('type', 'unknown')}")
            # Show first few keys
            for key in list(event.keys())[:5]:
                if key not in ['timestamp', 'type']:
                    value = str(event[key])[:100]
                    print(f"   {key}: {value}")
    
    def export_prompts(self) -> None:
        """Export all prompts to a markdown file."""
        output_file = self.log_file.parent / f"prompts_{self.log_file.stem}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# LLM Prompts Export\n")
            f.write(f"## Session: {self.log_file.name}\n\n")
            
            prompt_events = [e for e in self.events if e.get('type') == 'llm_call' and e.get('prompt')]
            
            for i, event in enumerate(prompt_events, 1):
                f.write(f"### Prompt #{i}\n\n")
                f.write(f"- **Component**: {event.get('component', 'Unknown')}\n")
                f.write(f"- **Model**: {event.get('model', 'Unknown')}\n")
                f.write(f"- **Timestamp**: {event.get('timestamp', 'N/A')}\n")
                f.write(f"- **Duration**: {event.get('duration_seconds', 'N/A')}s\n\n")
                
                f.write("#### Prompt:\n```\n")
                f.write(event.get('prompt', 'N/A'))
                f.write("\n```\n\n")
                
                if event.get('response') and event['response'] != '[disabled]':
                    f.write("#### Response:\n```\n")
                    f.write(event['response'])
                    f.write("\n```\n\n")
                
                f.write("---\n\n")
        
        print(f"Prompts exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Debug Log Viewer for Research Workflow")
    parser.add_argument('log_file', nargs='?', help='Log file to view (default: latest)')
    parser.add_argument('--summary', '-s', action='store_true', help='Show summary only')
    parser.add_argument('--prompts', '-p', action='store_true', help='Show all prompts')
    parser.add_argument('--errors', '-e', action='store_true', help='Show errors only')
    parser.add_argument('--timeline', '-t', action='store_true', help='Show execution timeline')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')
    
    args = parser.parse_args()
    
    # Find log file
    log_dir = Path('./debug_logs')
    if not log_dir.exists():
        print("Error: debug_logs directory not found")
        sys.exit(1)
    
    if args.log_file:
        log_file = log_dir / args.log_file
        if not log_file.exists():
            log_file = Path(args.log_file)
    else:
        # Find latest log file
        log_files = sorted(log_dir.glob('debug_*.jsonl'), key=lambda x: x.stat().st_mtime, reverse=True)
        if not log_files:
            print("No debug logs found in debug_logs directory")
            sys.exit(1)
        log_file = log_files[0]
        print(f"Using latest log: {log_file.name}")
    
    viewer = DebugLogViewer(log_file)
    
    if args.summary:
        viewer.show_summary()
    elif args.prompts:
        viewer.show_prompts()
    elif args.errors:
        viewer.show_errors()
    elif args.timeline:
        viewer.show_timeline()
    elif args.interactive:
        viewer.interactive_mode()
    else:
        # Default: show summary
        viewer.show_summary()


if __name__ == '__main__':
    main()