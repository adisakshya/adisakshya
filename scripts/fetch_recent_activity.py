#!/usr/bin/env python3
"""Fetch recent public GitHub activity and render README markdown."""

from __future__ import annotations

from datetime import datetime

from github_api import api_error_message, fail, read_json, username, write_markdown

EVENT_LABELS = {
    "CommitCommentEvent": "commented on a commit in",
    "CreateEvent": "created a branch, tag, or repository in",
    "DeleteEvent": "deleted a branch or tag in",
    "ForkEvent": "forked",
    "GollumEvent": "updated the wiki in",
    "IssueCommentEvent": "commented on an issue or PR in",
    "IssuesEvent": "updated an issue in",
    "PullRequestEvent": "updated a pull request in",
    "PullRequestReviewEvent": "reviewed a pull request in",
    "PullRequestReviewCommentEvent": "commented on a pull request in",
    "PushEvent": "pushed commits to",
    "ReleaseEvent": "published a release in",
    "WatchEvent": "starred",
}


def event_url(event: dict) -> str:
    repo = event.get("repo", {})
    repo_name = repo.get("name", "")
    payload = event.get("payload", {})
    if event.get("type") == "PushEvent" and payload.get("head"):
        return f"https://github.com/{repo_name}/commit/{payload['head']}"
    if payload.get("pull_request", {}).get("html_url"):
        return payload["pull_request"]["html_url"]
    if payload.get("issue", {}).get("html_url"):
        return payload["issue"]["html_url"]
    if payload.get("release", {}).get("html_url"):
        return payload["release"]["html_url"]
    return f"https://github.com/{repo_name}"


def format_date(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%Y-%m-%d")


def render_event(event: dict) -> str:
    repo_name = event.get("repo", {}).get("name", "unknown repository")
    event_type = event.get("type", "GitHub event")
    action = EVENT_LABELS.get(event_type, event_type.replace("Event", "").lower())
    created_at = format_date(event.get("created_at", "1970-01-01T00:00:00Z"))
    url = event_url(event)
    return f"- {created_at}: {action} [{repo_name}]({url})."


def render_activity(events: list[dict]) -> str:
    if not events:
        return "No recent public activity found."
    rendered = [render_event(event) for event in events[:8]]
    return "\n".join(rendered)


def main() -> None:
    profile = username()
    try:
        events = read_json(f"/users/{profile}/events/public?per_page=30")
    except Exception as error:
        fail(api_error_message(error))

    output = render_activity(events)
    path = write_markdown("recent_activity.md", output)
    print(f"Wrote recent activity to {path}")


if __name__ == "__main__":
    main()
