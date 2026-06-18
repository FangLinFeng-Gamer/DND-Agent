# DND-Agent

Offline-first DND-Agent MVP with FastAPI, SQLite, static UI, character management, adventure sessions, DM narration, world/rule lookup, and basic combat.

## Run

```bash
uv run uvicorn backend.src.main:app --port 5000
```

Open `http://127.0.0.1:5000/`.

## Test

```bash
uv run pytest -q
```
