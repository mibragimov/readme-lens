from __future__ import annotations

import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


GITHUB_RE = re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#?]+)")


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str


class GitHubError(RuntimeError):
    pass


def parse_github_url(repo_url: str) -> RepoRef:
    m = GITHUB_RE.match(repo_url.strip())
    if not m:
        raise GitHubError("Please provide a URL like https://github.com/owner/repo")
    return RepoRef(owner=m.group("owner"), repo=m.group("repo"))


async def get_repo_meta(client: httpx.AsyncClient, ref: RepoRef) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{ref.owner}/{ref.repo}"
    r = await client.get(url, headers={"Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        raise GitHubError("Repo not found (or not public).")
    if r.status_code == 403:
        raise GitHubError("GitHub API rate-limited this server (HTTP 403). Try later.")
    r.raise_for_status()
    return r.json()


async def get_latest_sha(client: httpx.AsyncClient, ref: RepoRef, branch: str) -> str:
    url = f"https://api.github.com/repos/{ref.owner}/{ref.repo}/commits/{branch}"
    r = await client.get(url, headers={"Accept": "application/vnd.github+json"})
    if r.status_code in (404, 409):
        raise GitHubError("Could not resolve default branch commit.")
    if r.status_code == 403:
        raise GitHubError("GitHub API rate-limited this server (HTTP 403). Try later.")
    r.raise_for_status()
    data = r.json()
    return data.get("sha") or ""


async def download_default_branch_zip(
    client: httpx.AsyncClient, ref: RepoRef, branch: str
) -> Path:
    # codeload is optimized for archive download and doesn't require auth for public repos
    url = f"https://codeload.github.com/{ref.owner}/{ref.repo}/zip/refs/heads/{branch}"
    r = await client.get(url, follow_redirects=True)
    if r.status_code == 404:
        raise GitHubError("Could not download zip for default branch (public repos only).")
    if r.status_code == 403:
        raise GitHubError("GitHub blocked the archive download (HTTP 403). Try later.")
    r.raise_for_status()

    tmpdir = Path(tempfile.mkdtemp(prefix="readme-lens-"))
    zip_path = tmpdir / "repo.zip"
    zip_path.write_bytes(r.content)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmpdir / "src")

    # The extracted folder is typically "{repo}-{sha}/"
    src_root = tmpdir / "src"
    subdirs = [p for p in src_root.iterdir() if p.is_dir()]
    if not subdirs:
        raise GitHubError("Downloaded archive was empty.")
    return subdirs[0]
