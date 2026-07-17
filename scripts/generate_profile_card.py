#!/usr/bin/env python3
"""Generate and validate compact SVG assets for the profile README."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "profile.json"
README_PATH = ROOT / "README.md"
ASSETS_DIR = ROOT / "assets"
DARK_PATH = ASSETS_DIR / "profile-dark.svg"
LIGHT_PATH = ASSETS_DIR / "profile-light.svg"
METRICS_PATH = ASSETS_DIR / "github-metrics.svg"
API_ROOT = "https://api.github.com"
VIEW_BOX = "0 0 980 280"
EXPECTED_LABELS = [
    "Uptime",
    "Languages.Programming",
    "Languages.Real",
    "Hobbies.Software",
    "Hobbies.Hardware",
    "Hobbies.Real",
    "Email.Personal",
]
BANNED_README_PATTERNS = [
    "github-readme-stats",
    "github-stats-start",
    "github-stats-end",
    "recent-activity-start",
    "recent-activity-end",
    "blog-posts-start",
    "blog-posts-end",
    "last-updated-start",
    "last-updated-end",
    "Building intelligent systems for complex healthcare decisions",
    "Healthcare Tech",
    "ZS Associates",
    "Current Employer",
    "HCP Knowledge Graph",
    "Medical Affairs",
    "visitor counter",
    "contribution snake",
    "GitHub trophies",
]

PALETTES = {
    "dark": {
        "background": "#0d1117",
        "panel": "#161b22",
        "primary": "#c9d1d9",
        "muted": "#8b949e",
        "accent": "#7ee787",
        "border": "#30363d",
        "leader": "#30363d",
        "shadow": "#010409",
    },
    "light": {
        "background": "#ffffff",
        "panel": "#f6f8fa",
        "primary": "#24292f",
        "muted": "#57606a",
        "accent": "#1a7f37",
        "border": "#d0d7de",
        "leader": "#d0d7de",
        "shadow": "#d8dee4",
    },
}


def xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "adisakshya-profile-card-generator",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_created_at(username: str, fallback: str) -> str:
    request = Request(f"{API_ROOT}/users/{username}", headers=github_headers())
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        created_at = payload.get("created_at")
        if isinstance(created_at, str) and created_at:
            return created_at
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        print(f"Using fallback GitHub account creation date: {error}")
    return fallback


def parse_github_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def completed_years_months(start: datetime, now: datetime | None = None) -> tuple[int, int]:
    today = now or datetime.now(UTC)
    months = (today.year - start.year) * 12 + today.month - start.month
    if today.day < start.day:
        months -= 1
    return months // 12, months % 12


def uptime_text(created_at: str) -> str:
    years, months = completed_years_months(parse_github_datetime(created_at))
    year_word = "year" if years == 1 else "years"
    month_word = "month" if months == 1 else "months"
    return f"{years} {year_word}, {months} {month_word} on GitHub"


def join_items(items: list[str]) -> str:
    return ", ".join(items)


def rows(config: dict[str, Any], uptime: str) -> list[tuple[str, str]]:
    return [
        ("Uptime", uptime),
        ("Languages.Programming", join_items(config["languages_programming"])),
        ("Languages.Real", join_items(config["languages_real"])),
        ("Hobbies.Software", join_items(config["hobbies_software"])),
        ("Hobbies.Hardware", join_items(config["hobbies_hardware"])),
        ("Hobbies.Real", join_items(config["hobbies_real"])),
        ("Email.Personal", config["email_personal"]),
    ]


def text_node(x: int, y: int, value: str, css_class: str, anchor: str = "start") -> str:
    return f'<text x="{x}" y="{y}" class="{css_class}" text-anchor="{anchor}">{xml_escape(value)}</text>'


def wrap_value(value: str, limit: int = 32) -> list[str]:
    if len(value) <= limit:
        return [value]
    parts = value.split(", ")
    lines: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else f"{current}, {part}"
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            lines.append(current)
            current = part
    if current:
        lines.append(current)
    return lines


def value_node(x: int, y: int, value: str) -> str:
    lines = wrap_value(value)
    if len(lines) == 1:
        return text_node(x, y, value, "value")
    tspans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else 18}">{xml_escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x}" y="{y}" class="value small-value">{tspans}</text>'


def row_svg(label: str, value: str, x: int, y: int, value_x: int) -> str:
    leader_start = x + (178 if x >= 500 else 205)
    leader_end = value_x - 18
    return "\n".join(
        [
            text_node(x, y, label, "key"),
            f'<line x1="{leader_start}" y1="{y - 5}" x2="{leader_end}" y2="{y - 5}" class="leader" />',
            value_node(value_x, y, value),
        ]
    )


def render_card(theme: str, config: dict[str, Any], card_rows: list[tuple[str, str]]) -> str:
    palette = PALETTES[theme]
    left_rows = card_rows[:3]
    right_rows = card_rows[3:]
    left = "\n".join(row_svg(label, value, 72, 122 + index * 38, 314) for index, (label, value) in enumerate(left_rows))
    right_y = [84, 132, 180, 228]
    right = "\n".join(row_svg(label, value, 510, right_y[index], 718) for index, (label, value) in enumerate(right_rows))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="{VIEW_BOX}" width="980" height="280">
  <title id="title">Terminal-style profile summary for Adisakshya Chauhan</title>
  <desc id="desc">adi@github profile card with GitHub uptime, languages, hobbies, and personal email.</desc>
  <defs>
    <filter id="soft-shadow" x="-2%" y="-6%" width="104%" height="112%">
      <feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="{palette['shadow']}" flood-opacity="0.20"/>
    </filter>
    <style>
      .terminal-bg {{ fill: {palette['background']}; }}
      .panel {{ fill: {palette['panel']}; stroke: {palette['border']}; stroke-width: 1.5; }}
      .dot-red {{ fill: #ff7b72; }}
      .dot-yellow {{ fill: #d29922; }}
      .dot-green {{ fill: {palette['accent']}; }}
      .handle {{ fill: {palette['accent']}; font: 700 22px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .prompt {{ fill: {palette['muted']}; font: 500 15px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .key {{ fill: {palette['muted']}; font: 600 16px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .value {{ fill: {palette['primary']}; font: 500 16px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
      .small-value {{ font-size: 14px; }}
      .leader {{ stroke: {palette['leader']}; stroke-width: 2; stroke-linecap: round; stroke-dasharray: 1 8; }}
      .divider {{ stroke: {palette['border']}; stroke-width: 1; }}
      .accent-bar {{ fill: {palette['accent']}; opacity: 0.85; }}
    </style>
  </defs>
  <rect class="terminal-bg" width="980" height="280" rx="16" />
  <rect class="panel" x="18" y="18" width="944" height="244" rx="15" filter="url(#soft-shadow)" />
  <rect class="accent-bar" x="18" y="18" width="944" height="4" rx="2" />
  <circle class="dot-red" cx="51" cy="50" r="6" />
  <circle class="dot-yellow" cx="73" cy="50" r="6" />
  <circle class="dot-green" cx="95" cy="50" r="6" />
  {text_node(72, 88, config['handle'], 'handle')}
  {text_node(510, 50, '~/profile --compact', 'prompt')}
  <line class="divider" x1="474" y1="62" x2="474" y2="222" />
  {left}
  {right}
</svg>
'''


def write_cards() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    config = load_config()
    created_at = fetch_created_at(config["username"], config["github_created_at_fallback"])
    card_rows = rows(config, uptime_text(created_at))
    DARK_PATH.write_text(render_card("dark", config, card_rows), encoding="utf-8")
    LIGHT_PATH.write_text(render_card("light", config, card_rows), encoding="utf-8")
    if not METRICS_PATH.exists():
        METRICS_PATH.write_text(render_metrics_placeholder(), encoding="utf-8")
    validate(config)


def render_metrics_placeholder() -> str:
    return '''<svg xmlns="http://www.w3.org/2000/svg" role="img" viewBox="0 0 980 220" width="980" height="220">
  <title>GitHub activity, community, language, repository and code-change metrics for adisakshya</title>
  <rect width="980" height="220" rx="14" fill="#f6f8fa" stroke="#d0d7de"/>
  <text x="40" y="58" fill="#24292f" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="22" font-weight="700">GitHub Metrics</text>
  <text x="40" y="96" fill="#57606a" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="16">Generated weekly by lowlighter/metrics in GitHub Actions.</text>
  <text x="40" y="136" fill="#24292f" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="15">Activity · Community statistics · Repository statistics · Most-used languages</text>
  <text x="40" y="170" fill="#24292f" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="15">Lines of code changed · Lines added · Lines removed</text>
</svg>
'''


def parse_svg(path: Path) -> ElementTree.Element:
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"{path} is missing or empty")
    return ElementTree.parse(path).getroot()


def visible_text(path: Path) -> list[str]:
    root = parse_svg(path)
    values: list[str] = []
    for element in root.iter():
        if element.tag.endswith("style"):
            continue
        if element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def validate(config: dict[str, Any]) -> None:
    for path in [DARK_PATH, LIGHT_PATH, METRICS_PATH]:
        root = parse_svg(path)
        view_box = root.attrib.get("viewBox")
        if not view_box or not re.fullmatch(r"\d+ \d+ \d+ \d+", view_box):
            raise ValueError(f"{path} has an invalid viewBox")

    dark_text = visible_text(DARK_PATH)
    light_text = visible_text(LIGHT_PATH)
    if dark_text != light_text:
        raise ValueError("Dark and light profile cards must contain identical text")

    combined_card_text = "\n".join(dark_text)
    for label in EXPECTED_LABELS:
        if label not in combined_card_text:
            raise ValueError(f"Missing profile card label: {label}")
    if join_items(config["hobbies_real"]) != "Aeromodelling, Reading, Writing, Research":
        raise ValueError("Hobbies.Real must remain exactly configured")

    readme = README_PATH.read_text(encoding="utf-8")
    for reference in re.findall(r'src(?:set)?="(\./assets/[^"]+\.svg)"', readme):
        if not (ROOT / reference.removeprefix("./")).exists():
            raise ValueError(f"README references a missing asset: {reference}")
    for pattern in BANNED_README_PATTERNS:
        if pattern.lower() in readme.lower() or pattern.lower() in combined_card_text.lower():
            raise ValueError(f"Banned profile content detected: {pattern}")
    if readme.count("<picture>") != 1 or readme.count("./assets/github-metrics.svg") != 1:
        raise ValueError("README must contain one profile card and one metrics SVG")
    if len(readme.splitlines()) > 30:
        raise ValueError("README should remain below 30 lines")


if __name__ == "__main__":
    write_cards()
