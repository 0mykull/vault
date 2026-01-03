# Vault transformation + deployment guide

## What changed from the original portfolio
- Replaced the portfolio/timeline routes with a Vault-branded notes experience that uses HTMX partials instead of static sections.
- Moved persistence from MySQL/MariaDB to SQLite (peewee ORM). `VAULT_DB_PATH` controls where the `.db` file lives, defaulting to `vault.db` in the repo.
- Introduced the `Note` model (title, content, color, pinned flag, created/updated timestamps), server-rendered note cards, and HTMX endpoints for inline pin/edit/delete.
- Added a JSON API (`/api/notes`) that mirrors the HTMX behavior so integrations/tests can create, read, update, and delete notes without HTML scraping.
- Rewrote templates with Tailwind/Turbo-glass styling to match the "Vault" product language.
- Updated scripts (compose files, Dockerfile, redeploy/test helpers, nginx config, README) to remove MySQL dependencies and document the new behavior.

## How the stack fits together

### Backend
- **Framework**: Flask serves both HTML and API responses from `app/__init__.py`.
- **ORM**: Peewee + SQLite keeps things embedded and easy to back up. During tests (`TESTING=true`), Peewee uses an in-memory DB.
- **Model**: `Note` stores title/content/color/pinned plus timestamps. `save()` automatically refreshes `updated_at` before persisting.
- **Helpers**: `_create_note_from_payload` and `_update_note_from_payload` centralize validation and normalization (colors limited to a curated palette, blank title+body blocked).
- **HTMX endpoints**: `/notes`, `/notes/<id>/update`, `/notes/<id>/toggle-pin`, `/notes/<id>/delete`, etc., render partial templates that HTMX swaps into the DOM without full-page reloads.

### Frontend
- **Template**: `templates/main.html` hosts the layout: hero, capture form, and a `#notes-grid` container. Tailwind CDN + custom gradients/theme create the glassmorphic look.
- **Partials**: `partials/note_grid.html`, `note_card.html`, `note_edit_form.html` drive the HTMX swaps. Buttons trigger POST/GET requests with `hx-` attributes, hitting the Flask endpoints above.
- **Micro-interactions**: `htmx:afterRequest` updates the inline status message; auto-growing textareas keep the editor minimal.

### API layer
| Method | Route | Notes |
| --- | --- | --- |
| GET | `/api/notes` | Returns `{count, notes}`; pinned notes are ordered first. |
| POST | `/api/notes` | Accepts JSON body (`title`, `content`, `color`, `pinned`). Enforces non-empty data. |
| GET | `/api/notes/<id>` | Single note payload. 404 if missing. |
| PUT | `/api/notes/<id>` | Updates text/color/pinned with the same validation logic as the form. |
| DELETE | `/api/notes/<id>` | Removes a note; returns HTTP 204. |

### Testing story
- `tests/test_app.py` exercises Flask routes + API with the TESTING flag, ensuring HTMX validation, pin/delete flows, and edit swaps render correctly.
- `tests/test_db.py` runs peewee CRUD operations in an in-memory SQLite DB (or mocks when Peewee is unavailable) to verify the model lifecycle.
- `run-tests.sh` wraps both modules with the appropriate env vars.

## Deploying Vault to a VPS
1. **Prereqs**: Docker + docker-compose, domain pointing to the VPS IP, and (optionally) DNS + port 80/443 access for Let’s Encrypt.
2. **Environment file**: copy `example.env` to `.env` and set at least `VAULT_DB_PATH` (e.g., `/data/vault.db`) plus any Flask settings you need. This path must map to a persistent volume.
3. **Bring up the stack**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
   - The `vault` service hosts Flask on port 5000.
   - The `nginx` service (jonasal/nginx-certbot) forwards 80/443 -> vault and handles certificates, using `user_conf.d/vault.conf`.
4. **Redeploy workflow**: `redeploy-site.sh` fetches `origin/main`, resets the repo, and recreates the prod compose stack (`docker compose -f docker-compose.prod.yml down && ... up -d --build`). Run it after each push.
5. **Persistence/backups**: `vault_data` volume holds the SQLite file defined by `VAULT_DB_PATH`. Snapshot or copy this volume to back up notes.
6. **Health checks**: use `test-curl.sh` locally or remotely to confirm `/api/notes` responds and newly created notes are retrievable.

With this flow, Vault stays a single-container Flask app behind nginx, so updates are just Git pulls + `docker compose up -d --build`.
