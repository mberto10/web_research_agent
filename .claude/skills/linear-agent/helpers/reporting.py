#!/usr/bin/env python3
"""
Reporting Helper
Generate reports on team activity, sprint progress, and issue metrics.
"""

import argparse
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
from linear_client import LinearClient, LinearAPIError


def parse_date(date_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))


def generate_team_summary(
    client: LinearClient,
    team_name: str,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Generate summary report for a team.

    Args:
        client: Linear client
        team_name: Team name
        verbose: Print verbose output

    Returns:
        Summary dictionary with metrics
    """
    if verbose:
        print(f"📊 Generating team summary for '{team_name}'...")

    # Get team
    team = client.get_team_by_name(team_name)
    if not team:
        raise LinearAPIError(f"Team not found: {team_name}")

    # Query all issues for team
    query = """
    query TeamIssues($teamId: String!) {
        team(id: $teamId) {
            issues {
                nodes {
                    id
                    identifier
                    title
                    priority
                    estimate
                    state {
                        name
                        type
                    }
                    assignee {
                        name
                    }
                    labels {
                        nodes {
                            name
                        }
                    }
                    createdAt
                    updatedAt
                    completedAt
                }
            }
        }
    }
    """

    result = client._execute_query(query, {"teamId": team["id"]})
    issues = result.get("team", {}).get("issues", {}).get("nodes", [])

    if verbose:
        print(f"✓ Found {len(issues)} total issues")

    # Analyze issues
    summary = {
        "team": team["name"],
        "total_issues": len(issues),
        "by_state": defaultdict(int),
        "by_priority": defaultdict(int),
        "by_assignee": defaultdict(int),
        "by_label": defaultdict(int),
        "total_estimate": 0,
        "completed_estimate": 0,
        "recent_activity": []
    }

    priority_names = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}

    for issue in issues:
        # By state
        state_name = issue.get("state", {}).get("name", "Unknown")
        state_type = issue.get("state", {}).get("type", "unknown")
        summary["by_state"][state_name] += 1

        # By priority
        priority = issue.get("priority", 0)
        priority_label = priority_names.get(priority, str(priority))
        summary["by_priority"][priority_label] += 1

        # By assignee
        assignee = issue.get("assignee", {}).get("name", "Unassigned")
        summary["by_assignee"][assignee] += 1

        # By labels
        for label in issue.get("labels", {}).get("nodes", []):
            summary["by_label"][label["name"]] += 1

        # Estimates
        estimate = issue.get("estimate", 0) or 0
        summary["total_estimate"] += estimate

        if state_type == "completed":
            summary["completed_estimate"] += estimate

    # Convert defaultdicts to regular dicts
    summary["by_state"] = dict(summary["by_state"])
    summary["by_priority"] = dict(summary["by_priority"])
    summary["by_assignee"] = dict(summary["by_assignee"])
    summary["by_label"] = dict(summary["by_label"])

    return summary


def format_summary_markdown(summary: Dict[str, Any]) -> str:
    """Format summary as markdown report."""
    lines = []

    lines.append(f"# Team Summary: {summary['team']}\n")
    lines.append(f"**Total Issues:** {summary['total_issues']}\n")

    # By state
    lines.append("## Issues by State\n")
    for state, count in sorted(summary["by_state"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{state}**: {count}")
    lines.append("")

    # By priority
    lines.append("## Issues by Priority\n")
    priority_order = ["Urgent", "High", "Normal", "Low", "None"]
    for priority in priority_order:
        count = summary["by_priority"].get(priority, 0)
        if count > 0:
            lines.append(f"- **{priority}**: {count}")
    lines.append("")

    # By assignee
    lines.append("## Workload Distribution\n")
    for assignee, count in sorted(summary["by_assignee"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{assignee}**: {count} issues")
    lines.append("")

    # Estimates
    lines.append("## Effort Tracking\n")
    lines.append(f"- **Total Estimate**: {summary['total_estimate']} points")
    lines.append(f"- **Completed Estimate**: {summary['completed_estimate']} points")
    if summary['total_estimate'] > 0:
        completion_rate = (summary['completed_estimate'] / summary['total_estimate']) * 100
        lines.append(f"- **Completion Rate**: {completion_rate:.1f}%")
    lines.append("")

    # Top labels
    if summary["by_label"]:
        lines.append("## Top Labels\n")
        for label, count in sorted(summary["by_label"].items(), key=lambda x: -x[1])[:10]:
            lines.append(f"- **{label}**: {count}")
        lines.append("")

    return "\n".join(lines)


def generate_sprint_report(
    client: LinearClient,
    team_name: str,
    days: int = 7,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Generate sprint/period report for a team.

    Args:
        client: Linear client
        team_name: Team name
        days: Number of days to look back
        verbose: Print verbose output

    Returns:
        Sprint report dictionary
    """
    if verbose:
        print(f"📅 Generating {days}-day report for '{team_name}'...")

    cutoff_date = datetime.now() - timedelta(days=days)

    # Get team summary
    summary = generate_team_summary(client, team_name, verbose=False)

    # Query recent activity
    team = client.get_team_by_name(team_name)
    query = """
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
                    completedAt
                    createdAt
                    updatedAt
                }
            }
        }
    }
    """

    result = client._execute_query(query, {"teamId": team["id"]})
    issues = result.get("team", {}).get("issues", {}).get("nodes", [])

    # Filter by date
    created_in_period = []
    completed_in_period = []
    updated_in_period = []

    for issue in issues:
        created_at = parse_date(issue["createdAt"])
        if created_at >= cutoff_date:
            created_in_period.append(issue)

        if issue.get("completedAt"):
            completed_at = parse_date(issue["completedAt"])
            if completed_at >= cutoff_date:
                completed_in_period.append(issue)

        updated_at = parse_date(issue["updatedAt"])
        if updated_at >= cutoff_date and updated_at != created_at:
            updated_in_period.append(issue)

    report = {
        "period_days": days,
        "team": team_name,
        "created": len(created_in_period),
        "completed": len(completed_in_period),
        "updated": len(updated_in_period),
        "velocity": len(completed_in_period) / (days / 7) if days >= 7 else len(completed_in_period),
        "summary": summary
    }

    if verbose:
        print(f"✓ Period activity:")
        print(f"  - Created: {report['created']}")
        print(f"  - Completed: {report['completed']}")
        print(f"  - Updated: {report['updated']}")

    return report


def format_sprint_report_markdown(report: Dict[str, Any]) -> str:
    """Format sprint report as markdown."""
    lines = []

    lines.append(f"# Sprint Report: {report['team']}\n")
    lines.append(f"**Period:** Last {report['period_days']} days\n")

    lines.append("## Activity Summary\n")
    lines.append(f"- **Issues Created**: {report['created']}")
    lines.append(f"- **Issues Completed**: {report['completed']}")
    lines.append(f"- **Issues Updated**: {report['updated']}")
    lines.append(f"- **Velocity**: {report['velocity']:.1f} issues/week\n")

    # Include team summary
    lines.append("---\n")
    lines.append(format_summary_markdown(report["summary"]))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate reports on Linear team activity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Team summary
  python reporting.py --team "Backend Team" --report summary

  # Sprint report (last 7 days)
  python reporting.py --team "Backend Team" --report sprint --period 7

  # Export to file
  python reporting.py --team "Backend" --report sprint --output report.md

  # JSON output
  python reporting.py --team "Backend" --report summary --format json
        """
    )

    parser.add_argument("--team", required=True, help="Team name")
    parser.add_argument("--report", required=True, choices=["summary", "sprint"],
                        help="Report type")
    parser.add_argument("--period", type=int, default=7,
                        help="Period in days (for sprint report)")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown",
                        help="Output format")
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        client = LinearClient()

        if args.report == "summary":
            data = generate_team_summary(client, args.team, args.verbose)
            if args.format == "markdown":
                output = format_summary_markdown(data)
            else:
                output = json.dumps(data, indent=2)

        elif args.report == "sprint":
            data = generate_sprint_report(client, args.team, args.period, args.verbose)
            if args.format == "markdown":
                output = format_sprint_report_markdown(data)
            else:
                output = json.dumps(data, indent=2)

        # Output
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"\n✅ Report saved to {args.output}")
        else:
            print(output)

    except LinearAPIError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
