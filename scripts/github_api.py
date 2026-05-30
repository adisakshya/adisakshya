#!/usr/bin/env python3
"""Small GitHub REST API helper for profile README update scripts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
DEFAULT_USERNAME = "adisakshya"
DEFAULT_DATA_DIR = "/tmp/readme-data"


def username() -> str:
    return os.environ.get("GITHUB_USERNAME", DEFAULT_USERNAME)


def data_dir() -> Path:
    directory = Path(os.environ.get("README_DATA_DIR", DEFAULT_DATA_DIR))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def headers() -> dict[str, str]:
    request_headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "adisakshya-profile-readme-updater",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    return request_headers


def read_json(path: str) -> Any:
    request = Request(f"{API_ROOT}{path}", headers=headers())
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_paginated(path: str, max_pages: int = 10) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while page <= max_pages:
        separator = "&" if "?" in path else "?"
        page_path = f"{path}{separator}per_page=100&page={page}"
        page_items = read_json(page_path)
        if not page_items:
            break
        items.extend(page_items)
        if len(page_items) < 100:
            break
        page += 1
    return items


def write_markdown(filename: str, content: str) -> Path:
    path = data_dir() / filename
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def read_markdown(filename: str, fallback: str) -> str:
    path = data_dir() / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return fallback.strip()


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def api_error_message(error: Exception) -> str:
    if isinstance(error, HTTPError):
        details = error.read().decode("utf-8", errors="replace")
        return f"GitHub API request failed with status {error.code}: {details}"
    if isinstance(error, URLError):
        return f"GitHub API request failed: {error.reason}"
    return f"GitHub API request failed: {error}"


def next_page_from_link(link_header: str | None) -> int | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        if 'rel="next"' not in section:
            continue
        url = section[section.find("<") + 1 : section.find(">")]
        page_values = parse_qs(urlparse(url).query).get("page")
        if page_values:
            return int(page_values[0])
    return None
