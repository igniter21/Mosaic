# Mosaic Memory API

The local FastAPI service stores approved Mosaic events in SQLite. It is designed for local-first use: a source must be explicitly enabled before the API will accept events from it.

## Run locally

From this directory:

```powershell
uv run uvicorn mosaic_memory_api.main:app --app-dir src --reload
```

The API is served at `http://127.0.0.1:8000`; interactive API documentation is at `/docs`.

The default database is `../data/mosaic.db`. To configure the app, copy the repository-root `.env.example` to `.env` and adjust the `MOSAIC_` values as needed.

## Evidence-backed local retrieval

`POST /api/v1/memory/ask` searches derived local memories using deterministic keyword ranking and feature-hash similarity. The response includes the raw events supporting each result; it does not call a cloud model. See [`../docs/retrieval.md`](../docs/retrieval.md) for the data model and deletion behavior.

## Browser collector CORS

The browser collector is an unpacked Chrome extension whose origin is unique to its installation. After loading it, copy its extension ID from `chrome://extensions` and add this to the repository-root `.env`:

```dotenv
MOSAIC_COLLECTOR_ORIGINS=chrome-extension://YOUR_EXTENSION_ID
```

Restart the API after changing the environment file. This deliberate allowlist prevents arbitrary web pages from posting events to the local server.

See [`../docs/collectors.md`](../docs/collectors.md) for browser, YouTube, LeetCode, VS Code, and document collector installation and privacy details.
