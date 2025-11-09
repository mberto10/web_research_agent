#!/usr/bin/env python3
"""
Analyze Strategy Performance

Analyzes Langfuse traces to generate performance reports for research strategies.
Identifies bottlenecks, errors, and optimization opportunities.

USAGE:
======
# Comprehensive analysis
python3 analyze_strategy_performance.py \
  --traces /tmp/strategy_analysis/traces.json \
  --strategy "daily_news_briefing"

# Focus on specific aspect
python3 analyze_strategy_performance.py \
  --traces /tmp/traces.json \
  --strategy "financial_research" \
  --focus tool_effectiveness
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from datetime import datetime

def calculate_latencies(traces: List[Dict], observations: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Calculate latency statistics."""

    trace_latencies = []
    phase_latencies = defaultdict(list)
    tool_latencies = defaultdict(list)

    for trace in traces:
        # Trace-level latency
        latency = trace.get('latency')
        if latency:
            trace_latencies.append(latency / 1000)  # Convert to seconds

        # Observation-level latencies
        trace_id = trace['id']
        if trace_id in observations:
            for obs in observations[trace_id]:
                obs_latency = obs.get('latency')
                if obs_latency:
                    latency_sec = obs_latency / 1000
                    obs_name = obs.get('name', 'unknown')

                    # Categorize by phase
                    if 'scope' in obs_name.lower():
                        phase_latencies['scope'].append(latency_sec)
                    elif 'fill' in obs_name.lower():
                        phase_latencies['fill'].append(latency_sec)
                    elif 'research' in obs_name.lower() or 'tool' in obs_name.lower():
                        phase_latencies['research'].append(latency_sec)
                    elif 'finalize' in obs_name.lower() or 'write' in obs_name.lower():
                        phase_latencies['finalize'].append(latency_sec)

                    # Tool-specific latencies
                    tool_latencies[obs_name].append(latency_sec)

    def stats(values):
        if not values:
            return None
        return {
            'avg': round(sum(values) / len(values), 2),
            'min': round(min(values), 2),
            'max': round(max(values), 2),
            'p50': round(sorted(values)[len(values)//2], 2),
            'p95': round(sorted(values)[int(len(values)*0.95)], 2) if len(values) > 1 else round(values[0], 2),
            'count': len(values)
        }

    return {
        'trace_latencies': stats(trace_latencies),
        'phase_latencies': {phase: stats(latencies) for phase, latencies in phase_latencies.items()},
        'tool_latencies': {tool: stats(latencies) for tool, latencies in tool_latencies.items()}
    }


def analyze_errors(traces: List[Dict], observations: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Analyze error patterns."""

    errors = []
    error_traces = set()

    for trace in traces:
        trace_id = trace['id']
        level = trace.get('level', 'DEFAULT')
        status = trace.get('status_message', '')

        if level == 'ERROR':
            error_traces.add(trace_id)
            errors.append({
                'trace_id': trace_id,
                'level': 'trace',
                'message': status,
                'timestamp': trace.get('timestamp')
            })

        # Check observations
        if trace_id in observations:
            for obs in observations[trace_id]:
                obs_level = obs.get('level', 'DEFAULT')
                if obs_level in ['ERROR', 'WARNING']:
                    error_traces.add(trace_id)
                    errors.append({
                        'trace_id': trace_id,
                        'level': obs_level.lower(),
                        'phase': obs.get('name', 'unknown'),
                        'message': obs.get('status_message', ''),
                        'timestamp': obs.get('start_time')
                    })

    # Group errors by type
    error_patterns = defaultdict(list)
    for error in errors:
        msg = error.get('message', '').lower()
        if 'timeout' in msg:
            error_patterns['timeout'].append(error)
        elif 'context length' in msg or 'token' in msg:
            error_patterns['context_length'].append(error)
        elif 'rate limit' in msg:
            error_patterns['rate_limit'].append(error)
        elif 'api' in msg:
            error_patterns['api_error'].append(error)
        else:
            error_patterns['other'].append(error)

    return {
        'total_errors': len(errors),
        'affected_traces': len(error_traces),
        'error_rate': round(len(error_traces) / len(traces) * 100, 1) if traces else 0,
        'error_patterns': {
            pattern: {
                'count': len(errs),
                'trace_ids': list(set(e['trace_id'] for e in errs))[:5]  # Sample
            }
            for pattern, errs in error_patterns.items()
        }
    }


def analyze_tool_effectiveness(observations: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Analyze which tools are performing well."""

    tool_stats = defaultdict(lambda: {'success': 0, 'failure': 0, 'latencies': []})

    for trace_id, obs_list in observations.items():
        for obs in obs_list:
            tool_name = obs.get('name', 'unknown')
            level = obs.get('level', 'DEFAULT')
            latency = obs.get('latency')

            if level == 'ERROR':
                tool_stats[tool_name]['failure'] += 1
            else:
                tool_stats[tool_name]['success'] += 1

            if latency:
                tool_stats[tool_name]['latencies'].append(latency / 1000)

    # Calculate success rates
    tool_report = {}
    for tool, stats in tool_stats.items():
        total = stats['success'] + stats['failure']
        success_rate = (stats['success'] / total * 100) if total > 0 else 0
        avg_latency = sum(stats['latencies']) / len(stats['latencies']) if stats['latencies'] else 0

        tool_report[tool] = {
            'success_count': stats['success'],
            'failure_count': stats['failure'],
            'total_calls': total,
            'success_rate': round(success_rate, 1),
            'avg_latency_sec': round(avg_latency, 2)
        }

    return tool_report


def generate_recommendations(
    latencies: Dict,
    errors: Dict,
    tool_effectiveness: Dict,
    strategy_slug: str
) -> List[Dict[str, str]]:
    """Generate optimization recommendations."""

    recommendations = []

    # Check error rate
    if errors['error_rate'] > 10:
        recommendations.append({
            'priority': 1,
            'category': 'errors',
            'issue': f"High error rate ({errors['error_rate']}%)",
            'impact': 'high',
            'recommendation': 'Investigate and fix error patterns',
            'details': errors['error_patterns']
        })

    # Check for timeout errors
    if 'timeout' in errors['error_patterns'] and errors['error_patterns']['timeout']['count'] > 0:
        recommendations.append({
            'priority': 1,
            'category': 'timeout',
            'issue': f"{errors['error_patterns']['timeout']['count']} timeout errors",
            'impact': 'high',
            'recommendation': 'Increase timeout settings for slow tools',
            'example_fix': 'Add "timeout: 8" parameter to tool configuration'
        })

    # Check for context length errors
    if 'context_length' in errors['error_patterns'] and errors['error_patterns']['context_length']['count'] > 0:
        recommendations.append({
            'priority': 1,
            'category': 'context_length',
            'issue': f"{errors['error_patterns']['context_length']['count']} context length errors",
            'impact': 'high',
            'recommendation': 'Reduce evidence limits or use more aggressive filtering',
            'example_fix': 'Reduce limits.max_results from 20 to 15'
        })

    # Check P95 latency
    if latencies['trace_latencies'] and latencies['trace_latencies']['p95'] > 15:
        recommendations.append({
            'priority': 2,
            'category': 'latency',
            'issue': f"High P95 latency ({latencies['trace_latencies']['p95']}s)",
            'impact': 'medium',
            'recommendation': 'Optimize slow phases or add parallel execution'
        })

    # Check tool failure rates
    for tool, stats in tool_effectiveness.items():
        if stats['success_rate'] < 90 and stats['total_calls'] > 5:
            recommendations.append({
                'priority': 2,
                'category': 'tool_reliability',
                'issue': f"{tool} has {stats['success_rate']}% success rate",
                'impact': 'medium',
                'recommendation': f'Investigate {tool} failures or add fallback'
            })

    return sorted(recommendations, key=lambda r: r['priority'])


def analyze_performance(
    traces_file: str,
    strategy_slug: str,
    focus: str = 'all'
) -> Dict[str, Any]:
    """Main analysis function."""

    # Load traces
    with open(traces_file, 'r') as f:
        data = json.load(f)

    traces = data.get('traces', [])
    observations = data.get('observations', {})

    if not traces:
        return {
            'error': 'No traces found in file',
            'trace_count': 0
        }

    print(f"Analyzing {len(traces)} traces for strategy '{strategy_slug}'...")

    # Calculate metrics
    result = {
        'strategy_slug': strategy_slug,
        'analysis_timestamp': datetime.now().isoformat(),
        'trace_count': len(traces),
        'summary': {
            'total_traces': len(traces),
            'success_traces': len([t for t in traces if t.get('level') != 'ERROR']),
            'error_traces': len([t for t in traces if t.get('level') == 'ERROR']),
        }
    }

    if focus in ['all', 'latency']:
        print("  Calculating latencies...")
        result['latencies'] = calculate_latencies(traces, observations)

    if focus in ['all', 'errors']:
        print("  Analyzing errors...")
        result['errors'] = analyze_errors(traces, observations)

    if focus in ['all', 'tools', 'tool_effectiveness']:
        print("  Analyzing tool effectiveness...")
        result['tool_effectiveness'] = analyze_tool_effectiveness(observations)

    if focus == 'all':
        print("  Generating recommendations...")
        result['recommendations'] = generate_recommendations(
            result.get('latencies', {}),
            result.get('errors', {}),
            result.get('tool_effectiveness', {}),
            strategy_slug
        )

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Analyze strategy performance from Langfuse traces',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full analysis
  %(prog)s --traces /tmp/traces.json --strategy "daily_news_briefing"

  # Focus on latency
  %(prog)s --traces /tmp/traces.json --strategy "financial_research" --focus latency
        """
    )

    parser.add_argument('--traces', required=True, help='Path to traces JSON file')
    parser.add_argument('--strategy', required=True, help='Strategy slug being analyzed')
    parser.add_argument('--focus', choices=['all', 'latency', 'errors', 'tools', 'tool_effectiveness'],
                       default='all', help='Focus area for analysis')
    parser.add_argument('--output', default='/tmp/strategy_analysis/performance_report.json',
                       help='Output file path')

    args = parser.parse_args()

    try:
        result = analyze_performance(
            traces_file=args.traces,
            strategy_slug=args.strategy,
            focus=args.focus
        )

        # Save output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        # Print summary
        print("\n" + "="*60)
        print(f"PERFORMANCE REPORT: {args.strategy}")
        print("="*60)
        print(f"\nTraces Analyzed: {result['trace_count']}")

        if 'summary' in result:
            summary = result['summary']
            success_rate = round(summary['success_traces'] / summary['total_traces'] * 100, 1)
            print(f"Success Rate: {success_rate}% ({summary['success_traces']}/{summary['total_traces']})")

        if 'latencies' in result and result['latencies'].get('trace_latencies'):
            lat = result['latencies']['trace_latencies']
            print(f"\nLatency:")
            print(f"  Average: {lat['avg']}s")
            print(f"  P95: {lat['p95']}s")

        if 'errors' in result:
            errors = result['errors']
            print(f"\nErrors:")
            print(f"  Error Rate: {errors['error_rate']}%")
            print(f"  Total Errors: {errors['total_errors']}")

        if 'recommendations' in result and result['recommendations']:
            print(f"\nTop Recommendations:")
            for i, rec in enumerate(result['recommendations'][:3], 1):
                print(f"  {i}. [{rec['category']}] {rec['issue']}")
                print(f"     → {rec['recommendation']}")

        print(f"\n✓ Full report saved to: {output_path}")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
