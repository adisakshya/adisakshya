#!/usr/bin/env python3
"""Replace generated sections in the root README."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from github_api import read_markdown

README_PATH = Path("README.md")

FALLBACK_STATS = """
<p>
  <img height="165" alt="adisakshya's GitHub stats" src="https://github-readme-stats.vercel.app/api?username=adisakshya&show_icons=true&theme=transparent&hide_border=true" />
  <img height="165" alt="adisakshya's top languages" src="https://github-readme-stats.vercel.app/api/top-langs/?username=adisakshya&layout=compact&theme=transparent&hide_border=true" />
</p>

Auto-updated by the `Update README with GitHub Stats and Activity` workflow.
"""
FALLBACK_ACTIVITY = "Auto-updated by the `Update README with GitHub Stats and Activity` workflow."


def replace_between_markers(content: str, marker: str, replacement: str) -> str:
    start = f"<!-- {marker}-start -->"
    end = f"<!-- {marker}-end -->"
    if start not in content or end not in content:
        raise ValueError(f"README.md is missing required markers for {marker}")
    before, rest = content.split(start, 1)
    _, after = rest.split(end, 1)
    return f"{before}{start}\n{replacement.strip()}\n{end}{after}"


def main() -> None:
    content = README_PATH.read_text(encoding="utf-8")
    stats = read_markdown("github_stats.md", FALLBACK_STATS)
    activity = read_markdown("recent_activity.md", FALLBACK_ACTIVITY)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    content = replace_between_markers(content, "github-stats", stats)
    content = replace_between_markers(content, "recent-activity", activity)
    content = replace_between_markers(content, "last-updated", today)

    README_PATH.write_text(content, encoding="utf-8")
    print("README.md updated")


if __name__ == "__main__":
    main()
