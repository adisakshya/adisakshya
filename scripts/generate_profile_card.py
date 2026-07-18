#!/usr/bin/env python3
"""Generate the terminal-style profile identity SVGs (light + dark) from config/profile.json.

Both assets/profile-dark.svg and assets/profile-light.svg are rendered from the same
row layout and the same config source; only the palette differs between them.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "profile.json"
ASSETS_DIR = REPO_ROOT / "assets"

GITHUB_API_ROOT = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 10

VIEWBOX_WIDTH = 980
VIEWBOX_HEIGHT = 280

CONTENT_LEFT = 32
CONTENT_RIGHT = VIEWBOX_WIDTH - 32

# Conservative (slightly wide) monospace advance-width ratio used only to lay out
# dotted leaders and to guard against clipping. Overestimating keeps text away
# from edges rather than letting it run past them.
CHAR_WIDTH_RATIO = 0.62

FONT_STACK = (
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
    "'Liberation Mono', monospace"
)

BODY_ROWS = [
    ("Languages.Programming", "languages_programming"),
    ("Languages.Real", "languages_real"),
    ("Hobbies.Software", "hobbies_software"),
    ("Hobbies.Hardware", "hobbies_hardware"),
    ("Hobbies.Real", "hobbies_real"),
]

BODY_ROW_START_Y = 104
BODY_ROW_STEP_Y = 30
BODY_FONT_SIZE = 14
BODY_VALUE_START_X = 280

HEADER_UPTIME_LABEL_X = 560
HEADER_UPTIME_VALUE_X = 660
HEADER_FONT_SIZE = 14
HEADER_BASELINE_Y = 58

PALETTES = {
    "dark": {
        "background": "#0d1117",
        "panel": "#161b22",
        "primary": "#c9d1d9",
        "muted": "#8b949e",
        "accent": "#7ee787",
        "border": "#30363d",
    },
    "light": {
        "background": "#f6f8fa",
        "primary": "#24292f",
        "muted": "#57606a",
        "accent": "#1a7f37",
        "border": "#d0d7de",
    },
}


def est_width(text: str, font_size: int) -> float:
    return len(text) * font_size * CHAR_WIDTH_RATIO


def esc(text: str) -> str:
    return escape(str(text))


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_account_created_at(username: str) -> str | None:
    """Best-effort live lookup of the GitHub account creation date.

    Returns None on any failure so the caller can fall back to the
    deterministic value stored in config/profile.json.
    """
    request_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "adisakshya-profile-card-generator",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request_headers["Authorization"] = f"Bearer {token}"

    request = Request(f"{GITHUB_API_ROOT}/users/{username}", headers=request_headers)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("created_at")
    except (URLError, TimeoutError, ValueError, OSError) as error:
        print(f"warning: live GitHub lookup failed, using config fallback ({error})", file=sys.stderr)
        return None


def compute_uptime(created_at: str, now: datetime | None = None) -> str:
    created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)

    months = (now.year - created.year) * 12 + (now.month - created.month)
    if now.day < created.day:
        months -= 1

    years, remaining_months = divmod(months, 12)

    parts = []
    if years > 0:
        parts.append(f"{years} year" + ("" if years == 1 else "s"))
    if remaining_months > 0 or years == 0:
        parts.append(f"{remaining_months} month" + ("" if remaining_months == 1 else "s"))

    return f"{', '.join(parts)} on GitHub"


def joined(values: list[str]) -> str:
    return ", ".join(values)


@dataclass
class BodyRow:
    label: str
    value: str


def build_body_rows(config: dict) -> list[BodyRow]:
    rows = [BodyRow(label, joined(config[key])) for label, key in BODY_ROWS]
    rows.append(BodyRow("Email.Personal", config["email_personal"]))
    return rows


def validate_rows(rows: list[BodyRow]) -> None:
    for row in rows:
        label_end = CONTENT_LEFT + est_width(row.label, BODY_FONT_SIZE)
        if label_end > BODY_VALUE_START_X - 8:
            raise ValueError(
                f"label '{row.label}' is too wide for the reserved label column"
            )
        value_end = BODY_VALUE_START_X + est_width(row.value, BODY_FONT_SIZE)
        if value_end > CONTENT_RIGHT:
            raise ValueError(
                f"value for '{row.label}' ({row.value!r}) is too wide and would clip"
            )


def dotted_leader(x1: float, x2: float, y: float, color: str) -> str:
    if x2 - x1 < 12:
        return ""
    return (
        f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
        f'stroke="{color}" stroke-width="1.5" stroke-linecap="round" '
        f'stroke-dasharray="0.5,6" opacity="0.7" />'
    )


def render_svg(config: dict, uptime_text: str, palette_name: str) -> str:
    palette = PALETTES[palette_name]
    rows = build_body_rows(config)
    validate_rows(rows)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEWBOX_WIDTH} {VIEWBOX_HEIGHT}" '
        f'width="100%" role="img" aria-label="Terminal-style profile summary for {esc(config["username"])}">'
    )
    parts.append(f'<rect width="{VIEWBOX_WIDTH}" height="{VIEWBOX_HEIGHT}" rx="14" fill="{palette["background"]}" />')
    parts.append(
        f'<rect x="1" y="1" width="{VIEWBOX_WIDTH - 2}" height="{VIEWBOX_HEIGHT - 2}" rx="13" '
        f'fill="none" stroke="{palette["border"]}" stroke-width="1.5" />'
    )

    # Title bar chrome: three muted terminal window dots.
    for cx in (20, 36, 52):
        parts.append(f'<circle cx="{cx}" cy="15" r="4.5" fill="{palette["border"]}" />')
    parts.append(
        f'<line x1="0" y1="30" x2="{VIEWBOX_WIDTH}" y2="30" stroke="{palette["border"]}" stroke-width="1" />'
    )

    text_style = f'font-family="{FONT_STACK}"'

    # Header row: handle + uptime, two-column.
    parts.append(
        f'<text x="{CONTENT_LEFT}" y="{HEADER_BASELINE_Y}" {text_style} font-size="20" '
        f'font-weight="700" fill="{palette["accent"]}">{esc(config["handle"])}</text>'
    )
    parts.append(
        f'<text x="{HEADER_UPTIME_LABEL_X}" y="{HEADER_BASELINE_Y}" {text_style} '
        f'font-size="{HEADER_FONT_SIZE}" fill="{palette["muted"]}">Uptime</text>'
    )
    label_end = HEADER_UPTIME_LABEL_X + est_width("Uptime", HEADER_FONT_SIZE)
    parts.append(dotted_leader(label_end + 6, HEADER_UPTIME_VALUE_X - 6, HEADER_BASELINE_Y - 4, palette["border"]))
    parts.append(
        f'<text x="{HEADER_UPTIME_VALUE_X}" y="{HEADER_BASELINE_Y}" {text_style} '
        f'font-size="{HEADER_FONT_SIZE}" fill="{palette["primary"]}">{esc(uptime_text)}</text>'
    )

    parts.append(
        f'<line x1="{CONTENT_LEFT}" y1="76" x2="{CONTENT_RIGHT}" y2="76" '
        f'stroke="{palette["border"]}" stroke-width="1" opacity="0.7" />'
    )

    # Body rows: label ... dotted leader ... value.
    for index, row in enumerate(rows):
        y = BODY_ROW_START_Y + index * BODY_ROW_STEP_Y
        parts.append(
            f'<text x="{CONTENT_LEFT}" y="{y}" {text_style} font-size="{BODY_FONT_SIZE}" '
            f'fill="{palette["muted"]}">{esc(row.label)}</text>'
        )
        label_end = CONTENT_LEFT + est_width(row.label, BODY_FONT_SIZE)
        parts.append(dotted_leader(label_end + 6, BODY_VALUE_START_X - 6, y - 4, palette["border"]))
        parts.append(
            f'<text x="{BODY_VALUE_START_X}" y="{y}" {text_style} font-size="{BODY_FONT_SIZE}" '
            f'fill="{palette["primary"]}">{esc(row.value)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    config = load_config()
    username = config["username"]

    created_at = fetch_account_created_at(username) or config["account_created_at"]
    uptime_text = compute_uptime(created_at)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    dark_svg = render_svg(config, uptime_text, "dark")
    light_svg = render_svg(config, uptime_text, "light")

    (ASSETS_DIR / "profile-dark.svg").write_text(dark_svg + "\n", encoding="utf-8")
    (ASSETS_DIR / "profile-light.svg").write_text(light_svg + "\n", encoding="utf-8")

    print(f"generated profile-dark.svg and profile-light.svg (uptime: {uptime_text})")


if __name__ == "__main__":
    main()
