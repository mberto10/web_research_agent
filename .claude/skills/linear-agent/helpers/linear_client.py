#!/usr/bin/env python3
"""
Linear API Client
Unified client for interacting with Linear's GraphQL API.
Wraps MCP tools and provides convenience methods with retry logic and error handling.
"""

import os
import time
import requests
from typing import Optional, Dict, Any, List
import json


class LinearAPIError(Exception):
    """Custom exception for Linear API errors."""
    pass


class LinearClient:
    """
    Unified Linear API client with retry logic and error handling.

    This client wraps the Linear GraphQL API and provides convenience methods
    for common operations. It handles authentication, rate limiting, and retries.
    """

    API_ENDPOINT = "https://api.linear.app/graphql"
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds
    RATE_LIMIT_PER_HOUR = 1500

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Linear client.

        Args:
            api_key: Linear API key. If not provided, will look for LINEAR_API_KEY env var.

        Raises:
            LinearAPIError: If no API key is found.
        """
        self.api_key = api_key or os.getenv("LINEAR_API_KEY")
        if not self.api_key:
            raise LinearAPIError(
                "No API key provided. Set LINEAR_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key
        }
        self.request_count = 0
        self.request_window_start = time.time()

    def _check_rate_limit(self):
        """Check if we're approaching rate limits and pause if needed."""
        current_time = time.time()
        elapsed = current_time - self.request_window_start

        # Reset counter every hour
        if elapsed >= 3600:
            self.request_count = 0
            self.request_window_start = current_time

        # If approaching limit, pause
        if self.request_count >= self.RATE_LIMIT_PER_HOUR - 100:
            sleep_time = 3600 - elapsed
            if sleep_time > 0:
                print(f"[Rate Limit] Approaching limit, pausing for {sleep_time:.0f}s")
                time.sleep(sleep_time)
                self.request_count = 0
                self.request_window_start = time.time()

    def _execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query with retry logic.

        Args:
            query: GraphQL query or mutation string
            variables: Optional query variables
            retry_count: Current retry attempt (used internally)

        Returns:
            Response data dictionary

        Raises:
            LinearAPIError: If request fails after all retries
        """
        self._check_rate_limit()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = requests.post(
                self.API_ENDPOINT,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            self.request_count += 1

            response.raise_for_status()
            data = response.json()

            # Check for GraphQL errors
            if "errors" in data:
                error_messages = [e.get("message", str(e)) for e in data["errors"]]
                raise LinearAPIError(f"GraphQL errors: {'; '.join(error_messages)}")

            return data.get("data", {})

        except requests.exceptions.RequestException as e:
            if retry_count < self.MAX_RETRIES:
                delay = self.RETRY_DELAY * (2 ** retry_count)  # Exponential backoff
                print(f"[Retry {retry_count + 1}/{self.MAX_RETRIES}] Request failed, retrying in {delay}s...")
                time.sleep(delay)
                return self._execute_query(query, variables, retry_count + 1)
            else:
                raise LinearAPIError(f"Request failed after {self.MAX_RETRIES} retries: {e}")

    def list_teams(self) -> List[Dict[str, Any]]:
        """
        List all teams in the workspace.

        Returns:
            List of team dictionaries with id, name, and key.
        """
        query = """
        query Teams {
            teams {
                nodes {
                    id
                    name
                    key
                    description
                }
            }
        }
        """
        result = self._execute_query(query)
        return result.get("teams", {}).get("nodes", [])

    def get_team_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get team by name (case-insensitive).

        Args:
            name: Team name to search for

        Returns:
            Team dictionary if found, None otherwise
        """
        teams = self.list_teams()
        for team in teams:
            if team["name"].lower() == name.lower():
                return team
        return None

    def get_issue(self, issue_id: str) -> Dict[str, Any]:
        """
        Get issue by ID.

        Args:
            issue_id: Linear issue ID

        Returns:
            Issue dictionary with all fields
        """
        query = """
        query GetIssue($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                estimate
                state {
                    id
                    name
                    type
                }
                assignee {
                    id
                    name
                    email
                }
                team {
                    id
                    name
                    key
                }
                project {
                    id
                    name
                }
                labels {
                    nodes {
                        id
                        name
                        color
                    }
                }
                createdAt
                updatedAt
                completedAt
                url
            }
        }
        """
        result = self._execute_query(query, {"id": issue_id})
        return result.get("issue", {})

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
        state_id: Optional[str] = None,
        project_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        estimate: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new issue.

        Args:
            team_id: Team ID to create issue in
            title: Issue title
            description: Issue description (markdown supported)
            priority: Priority (0=No priority, 1=Urgent, 2=High, 3=Normal, 4=Low)
            assignee_id: User ID to assign to
            state_id: State ID (e.g., backlog, in progress)
            project_id: Project ID to add to
            label_ids: List of label IDs
            estimate: Story point estimate

        Returns:
            Created issue dictionary
        """
        mutation = """
        mutation IssueCreate($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                    state {
                        name
                    }
                }
            }
        }
        """

        input_data = {
            "teamId": team_id,
            "title": title
        }

        if description:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id:
            input_data["assigneeId"] = assignee_id
        if state_id:
            input_data["stateId"] = state_id
        if project_id:
            input_data["projectId"] = project_id
        if label_ids:
            input_data["labelIds"] = label_ids
        if estimate is not None:
            input_data["estimate"] = estimate

        result = self._execute_query(mutation, {"input": input_data})
        issue_create = result.get("issueCreate", {})

        if not issue_create.get("success"):
            raise LinearAPIError("Failed to create issue")

        return issue_create.get("issue", {})

    def update_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
        state_id: Optional[str] = None,
        project_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None,
        estimate: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update an existing issue.

        Args:
            issue_id: Issue ID to update
            title: New title
            description: New description
            priority: New priority
            assignee_id: New assignee ID
            state_id: New state ID
            project_id: New project ID
            label_ids: New label IDs
            estimate: New estimate

        Returns:
            Updated issue dictionary
        """
        mutation = """
        mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    url
                    state {
                        name
                    }
                }
            }
        }
        """

        input_data = {}

        if title is not None:
            input_data["title"] = title
        if description is not None:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id is not None:
            input_data["assigneeId"] = assignee_id
        if state_id is not None:
            input_data["stateId"] = state_id
        if project_id is not None:
            input_data["projectId"] = project_id
        if label_ids is not None:
            input_data["labelIds"] = label_ids
        if estimate is not None:
            input_data["estimate"] = estimate

        result = self._execute_query(mutation, {"id": issue_id, "input": input_data})
        issue_update = result.get("issueUpdate", {})

        if not issue_update.get("success"):
            raise LinearAPIError("Failed to update issue")

        return issue_update.get("issue", {})

    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all projects in the workspace.

        Returns:
            List of project dictionaries
        """
        query = """
        query Projects {
            projects {
                nodes {
                    id
                    name
                    description
                    state
                    startDate
                    targetDate
                }
            }
        }
        """
        result = self._execute_query(query)
        return result.get("projects", {}).get("nodes", [])

    def list_workflow_states(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List workflow states, optionally filtered by team.

        Args:
            team_id: Optional team ID to filter states

        Returns:
            List of workflow state dictionaries
        """
        if team_id:
            query = """
            query TeamStates($teamId: String!) {
                team(id: $teamId) {
                    states {
                        nodes {
                            id
                            name
                            type
                            color
                            description
                        }
                    }
                }
            }
            """
            result = self._execute_query(query, {"teamId": team_id})
            return result.get("team", {}).get("states", {}).get("nodes", [])
        else:
            query = """
            query WorkflowStates {
                workflowStates {
                    nodes {
                        id
                        name
                        type
                        color
                        description
                    }
                }
            }
            """
            result = self._execute_query(query)
            return result.get("workflowStates", {}).get("nodes", [])

    def get_state_by_name(self, state_name: str, team_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get workflow state by name (case-insensitive).

        Args:
            state_name: State name to search for
            team_id: Optional team ID to scope search

        Returns:
            State dictionary if found, None otherwise
        """
        states = self.list_workflow_states(team_id)
        for state in states:
            if state["name"].lower() == state_name.lower():
                return state
        return None

    def create_comment(
        self,
        issue_id: str,
        body: str
    ) -> Dict[str, Any]:
        """
        Add a comment to an issue.

        Args:
            issue_id: Issue ID to comment on
            body: Comment text (markdown supported)

        Returns:
            Created comment dictionary
        """
        mutation = """
        mutation CommentCreate($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
                comment {
                    id
                    body
                    createdAt
                }
            }
        }
        """

        input_data = {
            "issueId": issue_id,
            "body": body
        }

        result = self._execute_query(mutation, {"input": input_data})
        comment_create = result.get("commentCreate", {})

        if not comment_create.get("success"):
            raise LinearAPIError("Failed to create comment")

        return comment_create.get("comment", {})

    def list_labels(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all labels, optionally filtered by team.

        Args:
            team_id: Optional team ID to filter by

        Returns:
            List of label dictionaries
        """
        if team_id:
            query = """
            query TeamLabels($teamId: String!) {
                team(id: $teamId) {
                    labels {
                        nodes {
                            id
                            name
                            color
                            description
                        }
                    }
                }
            }
            """
            result = self._execute_query(query, {"teamId": team_id})
            return result.get("team", {}).get("labels", {}).get("nodes", [])
        else:
            query = """
            query Labels {
                issueLabels {
                    nodes {
                        id
                        name
                        color
                        description
                    }
                }
            }
            """
            result = self._execute_query(query)
            return result.get("issueLabels", {}).get("nodes", [])

    def create_label(
        self,
        name: str,
        team_id: Optional[str] = None,
        color: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new label.

        Args:
            name: Label name
            team_id: Optional team ID to scope label to
            color: Optional color hex code (e.g., "#ff0000")
            description: Optional label description

        Returns:
            Created label dictionary
        """
        mutation = """
        mutation LabelCreate($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
                success
                issueLabel {
                    id
                    name
                    color
                }
            }
        }
        """

        input_data = {"name": name}

        if team_id:
            input_data["teamId"] = team_id
        if color:
            input_data["color"] = color
        if description:
            input_data["description"] = description

        result = self._execute_query(mutation, {"input": input_data})
        label_create = result.get("issueLabelCreate", {})

        if not label_create.get("success"):
            raise LinearAPIError("Failed to create label")

        return label_create.get("issueLabel", {})


if __name__ == "__main__":
    # Simple test/demo
    try:
        client = LinearClient()
        print("✓ Linear client initialized")

        teams = client.list_teams()
        print(f"✓ Found {len(teams)} teams")

        for team in teams[:3]:  # Show first 3 teams
            print(f"  - {team['name']} ({team['key']})")

    except LinearAPIError as e:
        print(f"✗ Error: {e}")
