from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


README_NAMES = [
    "README.md",
    "readme.md",
    "README.MD",
    "README",
]


DOC_FILES = {
    "LICENSE": ["LICENSE", "LICENSE.md", "LICENSE.txt"],
    "CONTRIBUTING": ["CONTRIBUTING.md", "CONTRIBUTING"],
    "CODE_OF_CONDUCT": ["CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT"],
    "SECURITY": ["SECURITY.md", "SECURITY"],
    "CHANGELOG": ["CHANGELOG.md", "CHANGELOG"],
}


ENV_FILES = [".env.example", ".env.sample", ".env.template", "env.example"]


BUILD_FILES = [
    "Makefile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
]


COMMON_HEADINGS = {
    "installation": ["installation", "install", "setup"],
    "usage": ["usage", "quickstart", "getting started"],
    "development": ["development", "dev", "contributing"],
    "configuration": ["configuration", "config", "environment variables", "env"],
    "tests": ["tests", "testing"],
    "license": ["license"],
}


HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def find_first(root: Path, names: list[str]) -> Path | None:
    for n in names:
        p = root / n
        if p.exists() and p.is_file():
            return p
    return None


def read_text_safe(path: Path, max_bytes: int = 200_000) -> str:
    try:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_headings(markdown: str) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        m = HEADING_RE.match(line.strip())
        if not m:
            continue
        h = m.group(1)
        h = re.sub(r"`+", "", h)
        h = re.sub(r"\s+", " ", h).strip().lower()
        headings.append(h)
    return headings


def heading_present(headings: list[str], variants: list[str]) -> bool:
    for h in headings:
        for v in variants:
            if v in h:
                return True
    return False


def scan_repo(root: Path) -> dict[str, Any]:
    found: dict[str, Any] = {
        "files": {},
        "readme": {
            "path": None,
            "headings": [],
            "sections": {},
        },
        "score": 0,
        "suggestions": [],
    }

    # README
    readme_path = find_first(root, README_NAMES)
    if readme_path:
        found["readme"]["path"] = str(readme_path.relative_to(root))
        md = read_text_safe(readme_path)
        headings = extract_headings(md)
        found["readme"]["headings"] = headings
        for k, variants in COMMON_HEADINGS.items():
            found["readme"]["sections"][k] = heading_present(headings, variants)
    else:
        for k in COMMON_HEADINGS.keys():
            found["readme"]["sections"][k] = False

    # Common docs
    for key, names in DOC_FILES.items():
        p = find_first(root, names)
        found["files"][key] = str(p.relative_to(root)) if p else None

    # Env example
    env = find_first(root, ENV_FILES)
    found["files"]["ENV_EXAMPLE"] = str(env.relative_to(root)) if env else None

    # Build tooling
    for name in BUILD_FILES:
        p = root / name
        if p.exists() and p.is_file():
            found["files"][name] = str(p.relative_to(root))

    # Score model (simple but useful)
    score = 0
    def add(points: int, ok: bool):
        nonlocal score
        if ok:
            score += points

    add(25, readme_path is not None)
    add(8, found["files"]["LICENSE"] is not None)
    add(8, found["files"]["CONTRIBUTING"] is not None)
    add(5, found["files"]["CODE_OF_CONDUCT"] is not None)
    add(5, found["files"]["SECURITY"] is not None)
    add(4, found["files"]["CHANGELOG"] is not None)
    add(10, found["files"]["ENV_EXAMPLE"] is not None)

    # README sections
    add(6, found["readme"]["sections"]["installation"])
    add(6, found["readme"]["sections"]["usage"])
    add(6, found["readme"]["sections"]["configuration"])
    add(4, found["readme"]["sections"]["tests"])
    add(4, found["readme"]["sections"]["development"])

    found["score"] = min(score, 100)

    # Suggestions
    suggestions: list[str] = []
    if not readme_path:
        suggestions.append("Add a README.md with purpose + quickstart + dev instructions.")
    else:
        for section, ok in found["readme"]["sections"].items():
            if not ok and section in ("installation", "usage", "configuration", "tests"):
                suggestions.append(f"Add a README section: {section.title()}.")

    if not found["files"]["LICENSE"]:
        suggestions.append("Add a LICENSE file (MIT/Apache-2.0/etc).")
    if not found["files"]["CONTRIBUTING"]:
        suggestions.append("Add CONTRIBUTING.md with local dev + PR guidelines.")
    if not found["files"]["ENV_EXAMPLE"]:
        suggestions.append("Add .env.example (or document required environment variables).")

    found["suggestions"] = suggestions

    return found


def generate_onboarding_md(owner: str, repo: str, scan: dict[str, Any]) -> str:
    sections = scan.get("readme", {}).get("sections", {})
    has_env = bool(scan.get("files", {}).get("ENV_EXAMPLE"))

    def yn(v: bool) -> str:
        return "✅" if v else "⬜"

    return f"""# Onboarding — {owner}/{repo}

This is a generated starter onboarding doc. Customize it for your project.

## Quick checklist

- {yn(bool(scan.get('readme', {}).get('path')))} README present
- {yn(bool(scan.get('files', {}).get('LICENSE')))} License
- {yn(bool(scan.get('files', {}).get('CONTRIBUTING')))} Contributing guide
- {yn(has_env)} Environment variables documented
- {yn(bool(sections.get('tests')))} Tests documented

## Local development

### Prerequisites

- Language/runtime installed
- Package manager (npm/pnpm/pip/poetry/etc)

### Setup

1. Clone the repo
2. Install dependencies
3. Configure environment variables
4. Run the app

### Environment variables

{'See `.env.example` and copy it to `.env`.' if has_env else 'Document required env vars here. Consider adding `.env.example`.'}

### Running tests

- Add the commands used to run unit/integration tests

## Repo structure

- `app/` — main application code
- `scripts/` — helper scripts
- `docs/` — documentation

## Contribution workflow

- Create a branch
- Make a focused change
- Add/adjust tests
- Open a PR with context + screenshots (if UI)

"""
