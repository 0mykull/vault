# Vault

Vault is a lightweight notes cockpit inspired by Google Keep and Obsidian. It stores quick memos, deep research, and pinned priorities in a SQLite database, served through Flask + HTMX with a glassmorphic Tailwind UI.

## Features

- **Zero-friction capture** – create notes inline, auto-pinned, and color-coded without leaving the board.
- **SQLite by default** – no external database. Works locally, in containers, or behind nginx with the same file.
- **HTMX interactions** – pin, edit, or delete without reloads while keeping server-rendered HTML.
- **Memory assistant** – tap the Memory button to ask Gemini what was on last week's grocery list; every note gets 1–5 smart tags so recall stays fast even with a big vault.
- **JSON API** – `/api/notes` exposes CRUD so automations and tests can manage notes.
- **Docker-native** – single container for dev or prod; optional nginx + certbot proxy stays unchanged.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp example.env .env
flask --app app run
```

Visit `http://localhost:5000` to open Vault.

## Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `FLASK_ENV` | Flask environment name | `development` |
| `VAULT_DB_PATH` | Path to the SQLite file | `vault.db` in project root |
| `TESTING` | When `true`, Vault uses an in-memory SQLite DB | `false` |
| `GEMINI_API_KEY` | Google AI Studio key for the Memory assistant | _unset_ |
| `GEMINI_MODEL_NAME` | Gemini model for tags + Memory retrieval | `gemini-2.5-flash-lite` |

If you run Vault in Docker, point `VAULT_DB_PATH` to a mounted volume so the `.db` file persists.

## API sketch

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/api/notes` | List notes (pinned first). |
| `POST` | `/api/notes` | Create a note. Body: `title`, `content`, optional `color`, `pinned`. |
| `GET` | `/api/notes/<id>` | Retrieve a single note. |
| `PUT` | `/api/notes/<id>` | Update title/content/color/pinned. |
| `DELETE` | `/api/notes/<id>` | Remove a note. |

## Testing

```
./run-tests.sh
```

Tests boot Vault in memory mode and cover HTML routes plus API/database behavior.

## Docker

- `docker-compose.yml` – one service (`vault`) exposing port 5000 for local dev.
- `docker-compose.prod.yml` – Vault + nginx-certbot. nginx proxies requests to the `vault` container and keeps certificates under `nginx_secrets`.

```
docker compose up -d --build
```

## Deployment helpers

- `redeploy-site.sh` – pulls `main` and recreates the prod compose stack.
- `stop-deployment.sh` – stops the tmux-based dev server, if running.
- `test-curl.sh` – sanity-checks the JSON API from the shell.

## File map

```
vault/
├── app/
│   ├── __init__.py          # Flask app + Peewee Note model
│   ├── templates/           # Vault UI + partials
│   └── static/              # Images/CSS hooks
├── tests/                   # App + DB unit tests
├── docker-compose*.yml      # Local + prod orchestration
└── user_conf.d/             # nginx virtual host for Vault
```

Vault stays intentionally minimal—extend it with tagging, search, or syncing if your workflow needs more structure.

### Memory assistant

1. Create a key at [Google AI Studio](https://aistudio.google.com/) and add it to `.env` as `GEMINI_API_KEY`. Optional: change `GEMINI_MODEL_NAME` (default `gemini-2.5-flash-lite`).
2. Install deps again (`pip install -r requirements.txt`) so `google-generativeai` is available.
3. Restart Flask and hit the **Memory** button.

How it works:

- On every note save, Gemini generates 1–5 lowercase, single-word tags; if Gemini is unavailable, Vault falls back to a heuristic keyword list.
- Memory stores the tags on each note. When you ask a question, Gemini only sees note ids + tags and returns the ids that fit your prompt.
- Vault then shows the matching notes (with previews and tag badges). If the API ever fails, Memory drops back to a local tag search so you still see relevant notes.
