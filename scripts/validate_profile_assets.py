#!/usr/bin/env python3
"""Validate the generated profile assets and README against the project's
privacy, structure and consistency requirements. Exits non-zero on failure.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "profile-readme.yml"

PROFILE_SVGS = [
    REPO_ROOT / "assets" / "profile-dark.svg",
    REPO_ROOT / "assets" / "profile-light.svg",
]
METRICS_SVG = REPO_ROOT / "assets" / "github-metrics.svg"

EXPECTED_LABELS = [
    "adi@github",
    "Uptime",
    "Languages.Programming",
    "Languages.Real",
    "Hobbies.Software",
    "Hobbies.Hardware",
    "Hobbies.Real",
    "Email.Personal",
]

BANNED_TERMS = [
    "ZS Associates",
    "Medical Affairs",
    "HCP Knowledge Graph",
    "Healthcare Tech",
    "healthcare",
    "consulting",
    "employer",
    "Full-stack engineer",
    "Data Engineer",
]

OLD_STATS_URL = "github-readme-stats.vercel.app"
OLD_MARKERS = [
    "github-stats-start",
    "github-stats-end",
    "recent-activity-start",
    "recent-activity-end",
    "blog-posts-start",
    "blog-posts-end",
    "last-updated-start",
    "last-updated-end",
]

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def check_svg_xml(path: Path, *, require_viewbox: bool) -> str | None:
    if not path.exists():
        fail(f"{path} does not exist")
        return None
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        fail(f"{path} is empty")
        return None
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        fail(f"{path} is not valid XML: {error}")
        return None
    if require_viewbox and not root.get("viewBox"):
        fail(f"{path} is missing a viewBox attribute")
    return content


def extract_texts(content: str) -> list[str]:
    return re.findall(r"<text[^>]*>([^<]*)</text>", content)


def check_profile_svgs() -> None:
    contents = []
    for path in PROFILE_SVGS:
        content = check_svg_xml(path, require_viewbox=True)
        if content is None:
            continue
        contents.append(content)
        texts = extract_texts(content)
        for label in EXPECTED_LABELS:
            if not any(label in text for text in texts):
                fail(f"{path} is missing expected label '{label}'")

    if len(contents) == 2:
        texts_a = extract_texts(contents[0])
        texts_b = extract_texts(contents[1])
        if texts_a != texts_b:
            fail("profile-dark.svg and profile-light.svg have different textual content")


def check_metrics_svg() -> None:
    check_svg_xml(METRICS_SVG, require_viewbox=False)


def check_readme() -> None:
    if not README_PATH.exists():
        fail("README.md does not exist")
        return
    readme = README_PATH.read_text(encoding="utf-8")

    referenced_assets = re.findall(r'(?:srcset|src)="([^"]+)"', readme)
    for ref in referenced_assets:
        if ref.startswith("http"):
            continue
        if not (REPO_ROOT / ref.lstrip("./")).exists():
            fail(f"README.md references '{ref}' which does not exist")

    if OLD_STATS_URL in readme:
        fail(f"README.md still references old stats service '{OLD_STATS_URL}'")

    for marker in OLD_MARKERS:
        if marker in readme:
            fail(f"README.md still contains old generated marker '{marker}'")

    line_count = len(readme.splitlines())
    if line_count > 32:
        fail(f"README.md is {line_count} lines, expected ~30 or fewer")

    lower_readme = readme.lower()
    for term in BANNED_TERMS:
        if term.lower() in lower_readme:
            fail(f"README.md contains disallowed professional/confidential term '{term}'")


def check_workflow_pinning() -> None:
    if not WORKFLOW_PATH.exists():
        fail(f"{WORKFLOW_PATH} does not exist")
        return
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    for match in re.finditer(r"uses:\s*([^\s#]+)", workflow):
        action_ref = match.group(1)
        if "@" not in action_ref:
            fail(f"workflow action '{action_ref}' is not pinned to a ref")
            continue
        _, ref = action_ref.rsplit("@", 1)
        if not FULL_SHA_RE.match(ref):
            fail(f"workflow action '{action_ref}' is not pinned to a full commit SHA")

    if "repositories_affiliations: owner" not in workflow:
        fail("workflow does not restrict repositories_affiliations to 'owner'")
    if "repositories_forks: no" not in workflow:
        fail("workflow does not exclude forks (repositories_forks: no)")


def main() -> int:
    check_profile_svgs()
    check_metrics_svg()
    check_readme()
    check_workflow_pinning()

    if errors:
        print("Validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
