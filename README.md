# Vault
_Vault keeps remembering simple._ Two buttons—**New note** and **Recall**—that is a Gemini-powered Memory, turn every text snippet into a searchable second brain.

## Why it exists
- **Plain text capture**: jot thoughts without markdown or block clutter; pin or color notes when needed.
- **Smart recall**: Memory sends a lightweight tag index to Gemini 2.5 Flash Lite and returns concise answers; when Gemini is offline, a keyword engine delivers the closest matches.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp example.env .env   # add GEMINI_API_KEY for live Memory
flask --app app run
```
Visit `http://localhost:5000`.

### Environment knobs
| Variable | Purpose | Default |
| --- | --- | --- |
| `VAULT_DB_PATH` | SQLite file location | `vault.db` |
| `GEMINI_API_KEY` | Google AI Studio key for tags + Memory | _unset_ |
| `GEMINI_MODEL_NAME` | Gemini model id | `gemini-2.5-flash-lite` |
| `TESTING` | In-memory DB for tests | `false` |

Memory still works without Gemini (it falls back to keyword recall), but you’ll miss the richer answers.

## Architecture snapshot
- `app/__init__.py` – Flask app, Peewee model, Memory engine, HTMX routes
- `app/templates` – Tailwind/HTMX UI with panels, indicators, and cards
- `tests/` – unit tests (run via `./run-tests.sh`, which sets `TESTING=true`)
- `dev_notes/` – hackathon worksheet + roadmap

## Memory workflow
1. **Tagging** – on every save/update, Gemini generates 1–5 lowercase tags (titles become tags too). A deterministic tokenizer backs up Gemini when it’s unavailable.
2. **Querying** – Recall builds `[{id}] title | tags | preview` lines and asks Gemini for JSON: `{"ids": [...], "answer": "..."}`.
3. **Fallback** – if Gemini returns prose or errors, Vault extracts ids with regex or reverts to keyword scoring, keeping the UI responsive.

## API surface (for automations)
| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/api/notes` | List notes (pinned first) |
| `POST` | `/api/notes` | Create note (`title`, `content`, optional `color`, `pinned`) |
| `GET` | `/api/notes/<id>` | Fetch note |
| `PUT` | `/api/notes/<id>` | Update fields |
| `DELETE` | `/api/notes/<id>` | Remove note |

## Helpful scripts
- `docker-compose.yml` / `.prod` – single-container dev/prod setups
- `redeploy-site.sh`, `stop-deployment.sh` – remote workflow helpers
- `test-curl.sh` – quick API check

## Development tips
- Run tests via `./run-tests.sh` (uses in-memory SQLite)
- Want to reset locally? stop Flask, `rm vault.db`, restart
- Need fresh tags? `flask shell -c "from app import Note, memory_engine; [memory_engine.ensure_tags(n) for n in Note.select()]"`
