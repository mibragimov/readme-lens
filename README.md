# README Lens

Paste a GitHub repo URL → get a documentation/onboarding readiness report + generated `ONBOARDING.md`.

Live demo: (set after deploy)

## What it checks

- Core community/docs files (LICENSE, CONTRIBUTING, SECURITY, CHANGELOG)
- `.env.example` presence
- README headings for common sections (Installation/Usage/Config/Tests/etc)

## Local dev

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Deploy (Render)

This repo includes a `render.yaml`. Create a new Render Blueprint from this repo.

