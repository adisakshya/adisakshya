#!/usr/bin/env python3
"""Fetch aggregate GitHub profile statistics and render README markdown."""

from __future__ import annotations

from collections import Counter
from html import escape

from github_api import api_error_message, fail, read_json, read_paginated, username, write_markdown


def visible_repositories(repositories: list[dict]) -> list[dict]:
    return [repo for repo in repositories if not repo.get("fork") and not repo.get("private")]


def language_summary(repositories: list[dict]) -> str:
    languages = Counter(repo.get("language") for repo in repositories if repo.get("language"))
    if not languages:
        return "No primary languages detected yet."
    return ", ".join(f"{language} ({count})" for language, count in languages.most_common(6))


def render_stats(user: dict, repositories: list[dict], profile: str) -> str:
    own_repositories = visible_repositories(repositories)
    total_stars = sum(repo.get("stargazers_count", 0) for repo in own_repositories)
    total_forks = sum(repo.get("forks_count", 0) for repo in own_repositories)
    public_repos = user.get("public_repos", len(own_repositories))
    followers = user.get("followers", 0)
    following = user.get("following", 0)
    languages = language_summary(own_repositories)
    safe_profile = escape(profile, quote=True)

    return f"""
<p>
  <img height="165" alt="{safe_profile}'s GitHub stats" src="https://github-readme-stats.vercel.app/api?username={safe_profile}&show_icons=true&theme=transparent&hide_border=true" />
  <img height="165" alt="{safe_profile}'s top languages" src="https://github-readme-stats.vercel.app/api/top-langs/?username={safe_profile}&layout=compact&theme=transparent&hide_border=true" />
</p>

- **Public repositories**: {public_repos}
- **Followers / Following**: {followers} / {following}
- **Stars across original public repositories**: {total_stars}
- **Forks across original public repositories**: {total_forks}
- **Primary repository languages**: {languages}
"""


def main() -> None:
    profile = username()
    try:
        user = read_json(f"/users/{profile}")
        repositories = read_paginated(f"/users/{profile}/repos?sort=updated&direction=desc")
    except Exception as error:
        fail(api_error_message(error))

    output = render_stats(user, repositories, profile)
    path = write_markdown("github_stats.md", output)
    print(f"Wrote GitHub stats to {path}")


if __name__ == "__main__":
    main()
