#!/usr/bin/env python3
"""
Create Issue Helper
Intelligent issue creation with template support and validation.
"""

import argparse
import os
import sys
import yaml
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path to import linear_client
sys.path.insert(0, str(Path(__file__).parent))
from linear_client import LinearClient, LinearAPIError


TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_template(template_name: str) -> Dict[str, Any]:
    """
    Load issue template from templates directory.

    Args:
        template_name: Template name (e.g., 'bug_report', 'feature_request', 'task')

    Returns:
        Template dictionary

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"

    if not template_path.exists():
        available = [f.stem for f in TEMPLATES_DIR.glob("*.yaml")]
        raise FileNotFoundError(
            f"Template '{template_name}' not found. Available: {', '.join(available)}"
        )

    with open(template_path, 'r') as f:
        return yaml.safe_load(f)


def render_template(
    template: Dict[str, Any],
    variables: Dict[str, str]
) -> Dict[str, Any]:
    """
    Render template with variable substitution.

    Args:
        template: Template dictionary
        variables: Variables to substitute (e.g., {'short_description': 'Login timeout'})

    Returns:
        Rendered template with variables replaced
    """
    rendered = {}

    for key, value in template.items():
        if isinstance(value, str):
            # Replace all {variable} placeholders
            for var_name, var_value in variables.items():
                placeholder = "{" + var_name + "}"
                value = value.replace(placeholder, var_value)
            rendered[key] = value
        elif isinstance(value, list):
            rendered[key] = value
        elif isinstance(value, dict):
            rendered[key] = render_template(value, variables)
        else:
            rendered[key] = value

    return rendered


def parse_labels(labels_str: Optional[str]) -> List[str]:
    """
    Parse comma-separated labels string.

    Args:
        labels_str: Comma-separated labels (e.g., "bug,p1,backend")

    Returns:
        List of label names
    """
    if not labels_str:
        return []
    return [label.strip() for label in labels_str.split(",") if label.strip()]


def get_label_ids(
    client: LinearClient,
    label_names: List[str],
    team_id: Optional[str] = None
) -> List[str]:
    """
    Convert label names to IDs.

    Args:
        client: Linear client
        label_names: List of label names
        team_id: Optional team ID to filter labels

    Returns:
        List of label IDs
    """
    if not label_names:
        return []

    all_labels = client.list_labels(team_id=team_id)
    label_map = {label["name"].lower(): label["id"] for label in all_labels}

    label_ids = []
    missing_labels = []

    for name in label_names:
        label_id = label_map.get(name.lower())
        if label_id:
            label_ids.append(label_id)
        else:
            missing_labels.append(name)

    if missing_labels:
        print(f"⚠ Warning: Labels not found: {', '.join(missing_labels)}")
        print("  Available labels:")
        for label_name in sorted(label_map.keys()):
            print(f"    - {label_name}")

    return label_ids


def create_issue_with_template(
    client: LinearClient,
    team_name_or_id: str,
    title: str,
    description: Optional[str] = None,
    template_name: Optional[str] = None,
    template_vars: Optional[Dict[str, str]] = None,
    priority: Optional[int] = None,
    labels: Optional[List[str]] = None,
    assignee_email: Optional[str] = None,
    estimate: Optional[int] = None,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Create issue with optional template support.

    Args:
        client: Linear client
        team_name_or_id: Team name or ID
        title: Issue title (or will be taken from template)
        description: Issue description (or will be taken from template)
        template_name: Optional template to use
        template_vars: Variables for template rendering
        priority: Priority (0-4)
        labels: List of label names
        assignee_email: Assignee email address
        estimate: Story point estimate
        verbose: Print verbose output

    Returns:
        Created issue dictionary
    """
    # Get team
    if verbose:
        print(f"🔍 Looking up team: {team_name_or_id}")

    team = None
    if team_name_or_id.startswith("team_"):
        # It's a team ID
        teams = client.list_teams()
        team = next((t for t in teams if t["id"] == team_name_or_id), None)
    else:
        # It's a team name
        team = client.get_team_by_name(team_name_or_id)

    if not team:
        raise LinearAPIError(f"Team not found: {team_name_or_id}")

    if verbose:
        print(f"✓ Found team: {team['name']} ({team['key']})")

    team_id = team["id"]

    # Load and render template if specified
    if template_name:
        if verbose:
            print(f"📋 Loading template: {template_name}")

        template = load_template(template_name)
        rendered = render_template(template, template_vars or {})

        # Merge template with explicit parameters (explicit params take precedence)
        if not title and "title" in rendered:
            title = rendered["title"]
        if not description and "description" in rendered:
            description = rendered["description"]
        if priority is None and "priority" in rendered:
            priority = rendered["priority"]
        if not labels and "labels" in rendered:
            labels = rendered["labels"]

    # Validate required fields
    if not title:
        raise ValueError("Title is required")

    # Convert labels to IDs
    label_ids = []
    if labels:
        if verbose:
            print(f"🏷  Resolving labels: {', '.join(labels)}")
        label_ids = get_label_ids(client, labels, team_id)
        if label_ids and verbose:
            print(f"✓ Resolved {len(label_ids)} labels")

    # Get assignee ID if email provided
    assignee_id = None
    if assignee_email:
        if verbose:
            print(f"👤 Looking up assignee: {assignee_email}")
        # Note: This would require a user lookup query
        # For now, we'll skip this and require the user to provide ID
        print("⚠ Warning: Assignee lookup by email not yet implemented")
        print("  Please provide assignee ID instead")

    # Create issue
    if verbose:
        print(f"\n📝 Creating issue:")
        print(f"  Title: {title}")
        print(f"  Team: {team['name']}")
        if description:
            print(f"  Description: {description[:100]}...")
        if priority is not None:
            priority_names = {0: "No priority", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
            print(f"  Priority: {priority_names.get(priority, priority)}")
        if label_ids:
            print(f"  Labels: {len(label_ids)} labels")
        if estimate:
            print(f"  Estimate: {estimate} points")

    issue = client.create_issue(
        team_id=team_id,
        title=title,
        description=description,
        priority=priority,
        assignee_id=assignee_id,
        label_ids=label_ids,
        estimate=estimate
    )

    return issue


def main():
    parser = argparse.ArgumentParser(
        description="Create Linear issue with template support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create simple issue
  python create_issue.py --team "Backend Team" --title "Fix login timeout"

  # Create from bug template
  python create_issue.py --team "Backend Team" --template bug_report \\
    --var short_description="Login timeout" \\
    --var detailed_description="Users report 30s timeout" \\
    --var expected="Login within 3s" \\
    --var actual="30s timeout then error"

  # Create with labels and priority
  python create_issue.py --team "Backend" --title "Add rate limiting" \\
    --labels "feature,p1" --priority 2 --estimate 5

  # Output as JSON
  python create_issue.py --team "Backend" --title "Fix bug" --output json
        """
    )

    parser.add_argument("--team", required=True, help="Team name or ID")
    parser.add_argument("--title", help="Issue title (or from template)")
    parser.add_argument("--description", help="Issue description (supports markdown)")
    parser.add_argument("--template", help="Template name (bug_report, feature_request, task)")
    parser.add_argument("--var", action="append", help="Template variable (format: key=value)")
    parser.add_argument("--priority", type=int, choices=[0, 1, 2, 3, 4],
                        help="Priority: 0=None, 1=Urgent, 2=High, 3=Normal, 4=Low")
    parser.add_argument("--labels", help="Comma-separated label names")
    parser.add_argument("--assignee", help="Assignee email address")
    parser.add_argument("--estimate", type=int, help="Story point estimate")
    parser.add_argument("--output", choices=["text", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Parse template variables
    template_vars = {}
    if args.var:
        for var_str in args.var:
            if "=" not in var_str:
                print(f"Error: Invalid variable format: {var_str}")
                print("Expected format: key=value")
                sys.exit(1)
            key, value = var_str.split("=", 1)
            template_vars[key.strip()] = value.strip()

    # Parse labels
    label_list = parse_labels(args.labels)

    try:
        client = LinearClient()

        issue = create_issue_with_template(
            client=client,
            team_name_or_id=args.team,
            title=args.title,
            description=args.description,
            template_name=args.template,
            template_vars=template_vars,
            priority=args.priority,
            labels=label_list,
            assignee_email=args.assignee,
            estimate=args.estimate,
            verbose=args.verbose
        )

        if args.output == "json":
            print(json.dumps(issue, indent=2))
        else:
            print("\n✅ Issue created successfully!")
            print(f"  ID: {issue['identifier']}")
            print(f"  Title: {issue['title']}")
            print(f"  URL: {issue['url']}")
            if "state" in issue:
                print(f"  State: {issue['state']['name']}")

    except (LinearAPIError, ValueError, FileNotFoundError) as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
