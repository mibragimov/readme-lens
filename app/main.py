from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.github import GitHubError, download_default_branch_zip, get_latest_sha, get_repo_meta, parse_github_url
from app.scanner import generate_onboarding_md, scan_repo

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = BASE_DIR / "data" / "readme-lens.sqlite3"

app = FastAPI(title="README Lens", version="0.2.0")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_conn = db.connect(DB_PATH)
db.init_db(_conn)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "example": "https://github.com/tiangolo/fastapi",
        },
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/recent", response_class=HTMLResponse)
async def recent(request: Request):
    rows = db.list_recent(_conn, limit=25)
    return templates.TemplateResponse(
        "recent.html",
        {
            "request": request,
            "rows": rows,
        },
    )


@app.post("/scan", response_class=HTMLResponse)
async def scan(request: Request, repo_url: str = Form(...)):
    try:
        ref = parse_github_url(repo_url)
        async with httpx.AsyncClient(timeout=30) as client:
            meta = await get_repo_meta(client, ref)
            branch = meta.get("default_branch") or "main"
            sha = await get_latest_sha(client, ref, branch)

            cached_scan = db.get_cached(_conn, ref.owner, ref.repo, sha) if sha else None
            if cached_scan:
                scan_result = cached_scan
                cached = True
            else:
                root = await download_default_branch_zip(client, ref, branch)
                scan_result = scan_repo(root)
                cached = False
                if sha:
                    db.save_scan(
                        _conn,
                        owner=ref.owner,
                        repo=ref.repo,
                        branch=branch,
                        sha=sha,
                        scanned_at=int(time.time()),
                        result=scan_result,
                    )

        key_files = {
            "README": scan_result.get("readme", {}).get("path"),
            "LICENSE": scan_result.get("files", {}).get("LICENSE"),
            "CONTRIBUTING": scan_result.get("files", {}).get("CONTRIBUTING"),
            "CODE OF CONDUCT": scan_result.get("files", {}).get("CODE_OF_CONDUCT"),
            "SECURITY": scan_result.get("files", {}).get("SECURITY"),
            "CHANGELOG": scan_result.get("files", {}).get("CHANGELOG"),
            "ENV EXAMPLE": scan_result.get("files", {}).get("ENV_EXAMPLE"),
        }

        return templates.TemplateResponse(
            "report.html",
            {
                "request": request,
                "owner": ref.owner,
                "repo": ref.repo,
                "branch": branch,
                "sha": sha,
                "scan": scan_result,
                "key_files": key_files,
                "cached": cached,
            },
        )
    except GitHubError as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": str(e),
            },
            status_code=400,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": f"Unexpected error: {type(e).__name__}: {e}",
            },
            status_code=500,
        )


@app.get("/onboarding", response_class=PlainTextResponse)
async def onboarding(owner: str, repo: str, branch: str, sha: str):
    scan_result = db.get_cached(_conn, owner, repo, sha)
    if not scan_result:
        return PlainTextResponse("Scan not found in cache. Please re-scan.", status_code=404)

    md = generate_onboarding_md(owner, repo, scan_result)
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=ONBOARDING-{owner}-{repo}.md"},
    )
