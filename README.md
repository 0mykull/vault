# Vault

Vault is a lightweight notes cockpit inspired by Google Keep and Obsidian. It stores quick memos, deep research, and pinned priorities in a SQLite database, served through Flask + HTMX with a glassmorphic Tailwind UI.

## Features

- **Zero-friction capture** – create notes inline, auto-pinned, and color-coded without leaving the board.
- **SQLite by default** – no external database. Works locally, in containers, or behind nginx with the same file.
- **HTMX interactions** – pin, edit, or delete without reloads while keeping server-rendered HTML.
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
