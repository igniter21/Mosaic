<p align="center">
  <img src="https://img.shields.io/badge/python-3.13-3776AB?logo=python&logoColor=white" alt="Python 3.13" />
  <img src="https://img.shields.io/badge/next.js-16-000000?logo=next.js&logoColor=white" alt="Next.js 16" />
  <img src="https://img.shields.io/badge/react-19-61DAFB?logo=react&logoColor=black" alt="React 19" />
  <img src="https://img.shields.io/badge/fastapi-0.141-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/sqlite-local--only-003B57?logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License" />
</p>

<h1 align="center">🧩 Mosaic Memory</h1>

<p align="center">
  <strong>A local-first, evidence-backed personal activity memory.</strong><br/>
  <em>Remember what mattered — on your device, under your control.</em>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-collectors">Collectors</a> •
  <a href="#-privacy-model">Privacy</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

## 🔍 Overview

**Mosaic Memory** is a self-hosted, privacy-first system that records your digital activity from explicitly approved sources — browser pages, YouTube videos, LeetCode problems, VS Code sessions, local documents, and Git history. Every piece of collected metadata stays in **local SQLite storage**, is transformed into searchable derived memories with evidence-backed retrieval, and can be deleted at any time — individually, by scope, or entirely.

> **No cloud account. No telemetry. No data leaves your machine** unless you explicitly click one of the optional Gemini-powered features.

---

## ✨ Features

### 📥 Opt-in Collectors
| Source | What's collected | What's **never** collected |
|--------|-----------------|---------------------------|
| **Browser** | Hostname, path, tab title | Query strings, URL fragments, cookies, page body |
| **YouTube** | Video ID, title | Watch history beyond explicit opt-in, audio/video |
| **LeetCode** | Problem slug, title | Code submissions, test results |
| **VS Code** | Workspace-relative filename, language ID, workspace name | File content, selections, diagnostics, absolute paths |
| **Documents** | Filename, extension, byte size, modified timestamp | File path, document text/content |
| **Git** | Commit message, branch, repository name, changed filenames | Source-code contents, diffs, credentials |

### 🧠 Derived Memories & Local Retrieval
- **Deterministic summaries** — source-aware, e.g. *"Watched Python sorting tutorial"*
- **192-dimension feature-hash vectors** — fully local, no API key needed
- **Keyword extraction & topic graph** — links related memories by shared keywords
- **Evidence-backed Ask** — every answer cites the raw events that support it
- **Time-aware queries** — supports *"today"*, *"yesterday"*, *"last week"*, *"last seven days"*
- **Context OS** — reconstructs sessions, connects project and goal signals, and provides local-only resume context

### 🔐 Privacy Controls
- Per-source enable/disable — events are rejected for disabled sources
- Delete individual events, scoped ranges, or **erase everything**
- Deleting a raw event cascades: derived memory, embedding, and graph links all go
- SQLite VACUUM after full erase for clean compaction

### 🌐 Optional Gemini Integration
- **Understand this tab** — click the toolbar icon to summarize one page (≤6,000 chars)
- **Ask with Gemini** — sends your question + top matching excerpts from understood tabs
- Incognito and browser-internal pages are always excluded
- API key stays in your local `.env` file, never in the extension

---

## 🏗 Architecture

```
mosaic-memory/
├── backend/               # Python FastAPI REST API
│   ├── src/mosaic_memory_api/
│   │   ├── api/           # Route handlers (events, sources, memory, privacy, health)
│   │   ├── core/          # Configuration & settings
│   │   ├── db/            # SQLAlchemy models, sessions, types
│   │   ├── domain/        # Domain models (events, memory, privacy, tab context)
│   │   └── services/      # Business logic (memory, gemini, privacy, event, source routing)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/              # Next.js 16 + React 19 + Tailwind CSS 4
│   ├── src/
│   │   ├── app/           # Pages: Dashboard, Ask, Context, Timeline, Sources, Privacy
│   │   ├── components/    # Shared UI (navigation, icons, source marks, erase dialog)
│   │   └── lib/           # API client & TypeScript types
│   └── Dockerfile
├── extensions/
│   ├── browser/           # Chrome MV3 extension (browser, YouTube, LeetCode collection)
│   └── vscode/            # VS Code extension (editor focus & save events)
├── scripts/               # Explicit document and Git metadata collectors
├── contracts/             # JSON Schema for the event contract
├── docs/                  # Collector boundaries, retrieval details, ADRs
├── compose.yaml           # One-command Docker Compose deployment
└── .github/workflows/     # CI: backend tests, frontend build, collector checks
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **API** | Python 3.13 · FastAPI · SQLAlchemy · Pydantic Settings |
| **Database** | SQLite (local file, zero-config) |
| **Frontend** | Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 |
| **Extensions** | Chrome Manifest V3 · VS Code Extension API |
| **Infrastructure** | Docker · Docker Compose · GitHub Actions CI |
| **Optional AI** | Google Gemini API (click-only, opt-in) |

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

The fastest way to run Mosaic Memory — one command, no local toolchains required.

```bash
# Clone the repository
git clone https://github.com/<your-username>/mosaic-memory.git
cd mosaic-memory

# Copy environment template
cp .env.example .env

# Launch both API and frontend
docker compose up --build
```

Open **http://localhost:3000** — the API runs on `127.0.0.1:8000`.

```bash
# Stop services (data is retained in a Docker volume)
docker compose down

# Stop and delete all stored data
docker compose down --volumes
```

### Option 2: Development Servers

#### Prerequisites
- **Python ≥ 3.13** with [`uv`](https://docs.astral.sh/uv/) package manager
- **Node.js ≥ 24** with `npm`

#### Backend

```bash
cd backend
uv sync --dev --extra context
uv run uvicorn mosaic_memory_api.main:app --app-dir src --reload
```

The API is now running at `http://127.0.0.1:8000`.

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. Use `localhost` (not `127.0.0.1`) for the web address — it's the API's default allowed frontend origin.

---

## 📡 Collectors

Every collector is **off by default**. Enable the matching source on the **Data Sources** page before using it.

### Browser / YouTube / LeetCode

1. Run the API and open the frontend.
2. In Chrome → `chrome://extensions` → enable **Developer mode** → **Load unpacked** → select `extensions/browser`.
3. Copy the extension ID and add it to `.env`:
   ```env
   MOSAIC_COLLECTOR_ORIGINS=chrome-extension://YOUR_EXTENSION_ID
   ```
4. Restart the API, open the extension **Options**, and enable desired sources. Then enable the same source in Mosaic's **Data Sources** page.

### VS Code

```bash
cd extensions/vscode
npm install
npm run compile
npx @vscode/vsce package
```

Install the `.vsix` in VS Code, enable `vscode` in Mosaic, then run **Mosaic Memory: Enable Metadata Collection** from the Command Palette.

### Documents (CLI)

```bash
# Preview what would be sent (dry run)
python scripts/collect_documents.py ~/Documents/notes.md --dry-run

# Collect a directory's supported files
python scripts/collect_documents.py ~/Documents/notes

# Recursively collect
python scripts/collect_documents.py ~/Documents/notes --recursive
```

Supported formats: `.doc`, `.docx`, `.md`, `.odt`, `.pdf`, `.pptx`, `.rtf`, `.txt`, `.xlsx`

### Git metadata (CLI)

Enable **Git** on the Data Sources page, then explicitly choose a repository to import. The collector sends commit metadata only; it never reads file contents or diffs.

```bash
python scripts/collect_git.py /path/to/a/repository
```

---

## 🔒 Privacy Model

| Principle | How it's enforced |
|-----------|------------------|
| **Opt-in only** | Every source must be enabled before events are accepted |
| **Local by default** | All retrieval uses deterministic local ranking — no cloud LLM |
| **Evidence-backed** | Every response names the raw events that support it |
| **Cascading delete** | Deleting an event removes its derived memory, embedding, and graph links |
| **Full erase** | One-click removal of all data with SQLite VACUUM compaction |
| **Cloud is click-only** | *Understand this tab* and *Ask with Gemini* run only when you explicitly click |
| **No incognito** | Browser-internal and incognito pages are always excluded |
| **Key isolation** | The Gemini API key lives in the local `.env`, never in the extension or committed |

For the exact data boundaries per collector, see [docs/collectors.md](docs/collectors.md).
For retrieval internals, see [docs/retrieval.md](docs/retrieval.md).

---

## 📘 API Reference

All endpoints are prefixed with `/api/v1`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/events` | List events (optional `?source=` & `?limit=` filters) |
| `POST` | `/events` | Create a new event |
| `DELETE` | `/events/{event_id}` | Delete a single event (cascades to derived data) |
| `DELETE` | `/events?source=&from=&to=` | Scoped bulk deletion |
| `GET` | `/sources` | List all source settings |
| `PATCH` | `/sources/{source}` | Enable or disable a source |
| `POST` | `/memory/ask` | Ask your memory (local retrieval) |
| `POST` | `/memory/ask-with-gemini` | Ask with Gemini (opt-in cloud) |
| `POST` | `/privacy/erase-all` | Full local erase with confirmation |
| `POST` | `/context/tab` | Understand a browser tab via Gemini |
| `GET` / `POST` | `/context/sessions`, `/context/ask` | Rebuild and query local activity context |
| `GET` / `POST` | `/context/projects`, `/context/goals` | Inspect project signals and manage goals |
| `GET` / `POST` | `/privacy/domain-rules` | Manage local host allow/deny rules |

The event contract is defined in [`contracts/event.schema.json`](contracts/event.schema.json).

---

## ✅ Validation & CI

GitHub Actions CI runs on every push to `main` and on pull requests:

| Job | What it checks |
|-----|---------------|
| **Backend** | `ruff check` linting + `pytest` test suite |
| **Frontend** | ESLint + Next.js production build |
| **Collectors** | JSON manifest validation, JS syntax, document dry-run |

Run the checks locally:

```bash
# Backend
cd backend
uv run ruff check src tests
uv run pytest tests -q

# Frontend
cd frontend
npm run lint
npm run build
```

---

## 🛠 Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Default | Description |
|----------|---------|-------------|
| `MOSAIC_ENVIRONMENT` | `development` | Runtime environment |
| `MOSAIC_DATA_DIR` | `./data` | SQLite database directory |
| `MOSAIC_FRONTEND_ORIGIN` | `http://localhost:3000` | Allowed CORS origin for the frontend |
| `MOSAIC_COLLECTOR_ORIGINS` | *(empty)* | Comma-separated browser extension origins |
| `MOSAIC_GEMINI_API_KEY` | *(empty)* | Optional Gemini API key for tab understanding |
| `MOSAIC_GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model for optional cloud features |

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes** and ensure CI passes locally
4. **Commit** with a clear message: `git commit -m "feat: add new collector for X"`
5. **Push** and open a **Pull Request**

Please follow the existing code style — `ruff` for Python, ESLint for TypeScript.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Built with care for privacy and personal sovereignty.</strong><br/>
  <sub>Your memory, your device, your rules.</sub>
</p>
