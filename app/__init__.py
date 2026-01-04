from __future__ import annotations
import datetime
import json
import logging
import os
import re
from collections import Counter
from typing import List, Sequence

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from peewee import (
    BooleanField,
    CharField,
    DateTimeField,
    Model,
    SqliteDatabase,
    TextField,
)
from playhouse.shortcuts import model_to_dict

try:  # Optional: only needed when Gemini support is enabled
    import google.generativeai as genai
except Exception:  # pragma: no cover - the package may not be installed yet
    genai = None

load_dotenv()
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
logger = logging.getLogger(__name__)

NOTE_COLORS = ["slate", "amber", "emerald", "rose", "sky", "violet"]
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")


def _is_testing() -> bool:
    return os.getenv("TESTING") == "true"


def _sqlite_path() -> str:
    if _is_testing():
        return "file:memory?mode=memory&cache=shared"
    db_path = os.getenv("VAULT_DB_PATH", os.path.join(os.getcwd(), "vault.db"))
    directory = os.path.dirname(db_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return db_path


def _init_db() -> SqliteDatabase:
    if _is_testing():
        return SqliteDatabase(_sqlite_path(), uri=True)
    return SqliteDatabase(_sqlite_path())


db = _init_db()


class BaseModel(Model):
    class Meta:
        database = db


class Note(BaseModel):
    title = CharField(default="")
    content = TextField(default="")
    pinned = BooleanField(default=False)
    color = CharField(default="slate")
    tags = TextField(default="")
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):  # noqa: D401
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    @property
    def tag_list(self) -> List[str]:
        return _split_tags(self.tags)


db.connect(reuse_if_open=True)
db.create_tables([Note])


def _ensure_tags_column():
    columns = db.get_columns("note")
    if any(column.name == "tags" for column in columns):
        return
    logger.info("Adding tags column to note table")
    db.execute_sql("ALTER TABLE note ADD COLUMN tags TEXT DEFAULT ''")


_ensure_tags_column()


def _split_tags(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag and tag.strip()]


def _serialize_tags(tags: Sequence[str]) -> str:
    cleaned: List[str] = []
    for tag in tags:
        tag = (tag or "").strip().lower()
        if not tag or " " in tag:
            tag = tag.replace(" ", "")
        if tag and tag not in cleaned:
            cleaned.append(tag)
    return ",".join(cleaned[:5])


def _normalize_color(value: str | None) -> str:
    value = (value or "slate").strip().lower()
    if value not in NOTE_COLORS:
        return "slate"
    return value


def _parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in {"true", "1", "on", "yes"}


def _split_notes():
    pinned = list(
        Note.select().where(Note.pinned == True).order_by(Note.updated_at.desc())  # noqa: E712
    )
    unpinned = list(
        Note.select().where(Note.pinned == False).order_by(Note.updated_at.desc())  # noqa: E712
    )
    return pinned, unpinned


def _note_to_dict(note: Note) -> dict:
    data = model_to_dict(note, recurse=False)
    data["created_at"] = note.created_at.isoformat()
    data["updated_at"] = note.updated_at.isoformat()
    data["tags"] = note.tag_list
    return data


def _render_note_card(note: Note) -> str:
    return render_template("partials/note_card.html", note=note)


def _render_note_grid() -> str:
    pinned, unpinned = _split_notes()
    return render_template(
        "partials/note_grid.html",
        pinned_notes=pinned,
        other_notes=unpinned,
    )


class MemoryEngine:
    def __init__(self):
        self._model = None
        self._configured_key = None

    def ask(self, question: str) -> dict:
        question = (question or "").strip()
        if not question:
            return {
                "status": "error",
                "message": "Ask a question before invoking Memory.",
            }

        notes = self._ordered_notes()
        if not notes:
            return {
                "status": "ok",
                "answer": "Your vault is empty so far. Capture a note and Memory will start indexing it.",
                "mode": "local",
            }

        model = self._ensure_model()
        if model:
            try:
                result = self._remote_answer_with_metadata(model, question, notes)
                answer_text = result.get("answer", "").strip()
                ids = result.get("ids", [])
                reason = result.get("reason")
                matched = self._notes_by_ids(notes, ids)
                if not matched:
                    matched = [
                        note for _, note in self._local_tag_search(question, notes)
                    ]
                    if matched and not reason:
                        reason = "Gemini returned no matches, so Memory surfaced the closest tags locally."
                if answer_text:
                    payload = {"status": "ok", "answer": answer_text, "mode": "gemini"}
                    if reason:
                        payload["message"] = reason
                    return payload
                if matched:
                    payload = {
                        "status": "ok",
                        "answer": self._format_answer_from_notes(matched),
                        "mode": "local",
                    }
                    if reason:
                        payload.setdefault("message", reason)
                    return payload
            except Exception as exc:  # pragma: no cover - defensive network handling
                logger.exception("Gemini memory request failed: %s", exc)
                matches = [note for _, note in self._local_tag_search(question, notes)]
                return self._build_local_response(
                    matches, error=self._friendly_error_message(exc)
                )

        matches = [note for _, note in self._local_tag_search(question, notes)]
        response = self._build_local_response(matches)
        if not os.getenv("GEMINI_API_KEY"):
            response.setdefault(
                "message",
                "Gemini answers unlock once GEMINI_API_KEY is configured.",
            )
        elif genai is None:
            response.setdefault(
                "message",
                "Install google-generativeai to enable Gemini answers.",
            )
        return response

    def ensure_tags(self, note: Note) -> Note:
        tags = self._generate_tags(note)
        title_tokens = self._title_tokens(note)
        tags = title_tokens + [tag for tag in tags if tag not in title_tokens]
        serialized = _serialize_tags(tags)
        note.tags = serialized
        Note.update(tags=serialized).where(Note.id == note.id).execute()
        return note

    def _generate_tags(self, note: Note) -> List[str]:
        model = self._ensure_model()
        if model:
            try:
                tags = self._remote_tags(model, note)
                if tags:
                    return tags
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception(
                    "Gemini tag generation failed for note %s: %s", note.id, exc
                )
        return self._fallback_tags(note)

    def _ensure_model(self):
        if _is_testing():
            return None
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or genai is None:
            return None
        if self._model and self._configured_key == api_key:
            return self._model
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        self._configured_key = api_key
        return self._model

    def _ordered_notes(self) -> List[Note]:
        return list(Note.select().order_by(Note.updated_at.desc()))

    def _remote_answer_with_metadata(self, model, question: str, notes: Sequence[Note]):
        tag_lines = self._tag_lines(notes, include_preview=True)
        if not tag_lines:
            raise RuntimeError("Memory index is empty")
        instructions = (
            "You are Memory, the built-in second brain for the Vault notes app. "
            "Each entry below includes a note id, title, tags, and a preview excerpt pulled from the note body. "
            "Identify the entries that directly answer the user's question and craft a concrete reply. If the preview lists items, echo the relevant ones back as bullets or short phrases. "
            "Always cite note ids in brackets (e.g., [3]) when referencing details. Keep the tone concise, warm, and proactive. "
            "If information looks incomplete, point that out and suggest capturing more detail. "
            'Respond with JSON: {"ids":[numbers],"answer":"final reply","reason":"optional note"}. '
            "When nothing matches, return an empty ids array and clearly explain why in the answer."
        )
        prompt = (
            f"{instructions}\n\nEntries:\n{tag_lines}\n\nQuestion: {question}\nJSON:"
        )
        response = model.generate_content(prompt)
        text = self._response_text(response)
        try:
            data = self._parse_model_json(text)
        except RuntimeError:
            ids = self._extract_ids_from_text(text)
            if ids:
                return {"ids": ids, "answer": text.strip()}
            raise
        ids = [self._coerce_int(value) for value in data.get("ids", [])]
        ids = [value for value in ids if value is not None]
        data["ids"] = ids
        return data

    def _remote_tags(self, model, note: Note) -> List[str]:
        title = note.title.strip() if note.title else "Untitled"
        body = (note.content or "").strip()
        instructions = (
            "Generate 1-5 lowercase, single-word tags summarizing this note. "
            "Prefer nouns. Respond with comma-separated words only."
        )
        prompt = f"{instructions}\nTitle: {title}\nBody: {body[:600]}\nTags:"
        response = model.generate_content(prompt)
        text = self._response_text(response)
        return self._extract_tags(text)

    def _fallback_tags(self, note: Note) -> List[str]:
        tokens = [
            token
            for token in re.split(r"\W+", f"{note.title} {note.content}".lower())
            if len(token) >= 3
        ]
        if not tokens:
            return ["note"]
        counts = Counter(tokens)
        return [word for word, _ in counts.most_common(5)]

    def _title_tokens(self, note: Note) -> List[str]:
        title = (note.title or "").strip().lower()
        if not title:
            return []
        tokens = []
        for raw in re.split(r"\W+", title):
            cleaned = re.sub(r"[^a-z0-9]", "", raw)
            if len(cleaned) < 3:
                continue
            if cleaned not in tokens:
                tokens.append(cleaned)
        return tokens[:5]

    def _extract_tags(self, text: str) -> List[str]:
        parts = re.split(r"[,\n]", text)
        tags = []
        for part in parts:
            cleaned = self._sanitize_tag(part)
            if cleaned:
                tags.append(cleaned)
        return tags[:5]

    def _sanitize_tag(self, value: str) -> str | None:
        tag = (value or "").strip().lower()
        tag = re.sub(r"[^a-z0-9]", "", tag)
        if len(tag) < 3:
            return None
        return tag

    def _parse_model_json(self, response) -> dict:
        text = (response or "").strip()
        if not text:
            raise RuntimeError("Empty response from Gemini")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                return json.loads(match.group(0))
        raise RuntimeError("Could not parse Gemini response")

    def _response_text(self, response) -> str:
        text = getattr(response, "text", None)
        if text:
            return text.strip()
        candidates = getattr(response, "candidates", None)
        if candidates:
            for candidate in candidates:
                parts = getattr(candidate, "content", None)
                if not parts:
                    continue
                parts_list = getattr(parts, "parts", None) or []
                for part in parts_list:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        return part_text.strip()
        raise RuntimeError("Gemini returned no text")

    def _extract_ids_from_text(self, text: str) -> List[int]:
        ids = [int(match) for match in re.findall(r"\[(\d+)\]", text)]
        if ids:
            return ids
        return [int(match) for match in re.findall(r"\b(\d{1,4})\b", text)]

    def _tag_lines(self, notes: Sequence[Note], include_preview: bool = False) -> str:
        lines = []
        for note in notes:
            tags = note.tag_list
            if not tags:
                continue
            title = (note.title or "Untitled").strip() or "Untitled"
            short_title = title[:60]
            if include_preview:
                preview = (note.content or "").strip().replace("\n", " ")
                if len(preview) > 140:
                    preview = f"{preview[:137].rstrip()}..."
                lines.append(
                    f"[{note.id}] {short_title} | tags: {', '.join(tags)} | preview: {preview or '(empty)'}"
                )
            else:
                lines.append(f"[{note.id}] {short_title} | tags: {', '.join(tags)}")
        return "\n".join(lines)

    def _coerce_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _notes_by_ids(self, notes: Sequence[Note], ids: Sequence[int]) -> List[Note]:
        lookup = {note.id: note for note in notes}
        ordered = []
        for note_id in ids:
            note = lookup.get(note_id)
            if note and note not in ordered:
                ordered.append(note)
        return ordered

    def _local_tag_search(self, question: str, notes: Sequence[Note], limit: int = 5):
        question_tokens = self._tokenize(question)
        if not question_tokens:
            return []
        matches = []
        for note in notes:
            tokens = self._tag_tokens(note)
            score = len(question_tokens & tokens)
            if score:
                matches.append((score, note))
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[:limit]

    def _tag_tokens(self, note: Note) -> set[str]:
        tags = note.tag_list
        if tags:
            return {self._normalize_token(tag) for tag in tags if len(tag) >= 3}
        return self._tokenize(f"{note.title} {note.content}")

    def _tokenize(self, text: str) -> set[str]:
        tokens = set()
        for raw in re.split(r"\W+", (text or "").lower()):
            if len(raw) < 3:
                continue
            tokens.add(self._normalize_token(raw))
        return tokens

    def _normalize_token(self, token: str) -> str:
        if token.endswith("ies") and len(token) > 4:
            return token[:-3] + "y"
        if token.endswith("s") and len(token) > 3:
            return token[:-1]
        return token

    def _format_answer_from_notes(self, notes: Sequence[Note]) -> str:
        if not notes:
            return (
                "Memory couldn't link that question to a note yet. Try a different keyword "
                "or capture the details in a note first."
            )
        lines = []
        for note in notes[:5]:
            title = note.title.strip() if note.title else "Untitled"
            preview_source = (note.content or "").strip() or title
            preview = preview_source.replace("\n", " ")
            if len(preview) > 160:
                preview = f"{preview[:157].rstrip()}..."
            tags_display = f" #{' #'.join(note.tag_list)}" if note.tag_list else ""
            lines.append(f"- [{note.id}] {title}{tags_display} — {preview}")
        return "Here's what surfaced:\n" + "\n".join(lines)

    def _build_local_response(
        self, notes: Sequence[Note], error: str | None = None
    ) -> dict:
        answer = self._format_answer_from_notes(notes)
        payload = {"status": "ok", "answer": answer, "mode": "local"}
        if error:
            payload["status"] = "error"
            payload["message"] = error
        return payload

    def _friendly_error_message(self, exc: Exception) -> str:
        text = str(exc)
        if "not found" in text and "models/" in text:
            return (
                "Gemini couldn't find the configured model "
                f"({GEMINI_MODEL_NAME}). Update GEMINI_MODEL_NAME or switch to "
                "`gemini-2.5-flash-lite`. Showing local recall instead."
            )
        if "API key" in text or "permission" in text.lower():
            return (
                "Gemini rejected the request. Double-check GEMINI_API_KEY permissions. "
                "Showing local recall instead."
            )
        return "Gemini was unavailable, so Memory shared local recall instead."


memory_engine = MemoryEngine()


def _render_memory_response(payload: dict) -> str:
    return render_template("partials/memory_response.html", memory=payload)


def _create_note_from_payload(payload: dict) -> Note:
    title = payload.get("title", "").strip()
    content = payload.get("content", "").strip()
    color = _normalize_color(payload.get("color"))
    pinned = _parse_bool(payload.get("pinned"))
    if not title and not content:
        raise ValueError("Notes need a title or content")
    note = Note.create(title=title, content=content, color=color, pinned=pinned)
    return memory_engine.ensure_tags(note)


def _update_note_from_payload(note: Note, payload: dict) -> Note:
    title = payload.get("title", note.title).strip()
    content = payload.get("content", note.content).strip()
    color = _normalize_color(payload.get("color", note.color))
    if not title and not content:
        raise ValueError("Notes need a title or content")
    note.title = title
    note.content = content
    note.color = color
    note.save()
    return memory_engine.ensure_tags(note)


def _is_htmx() -> bool:
    return bool(request.headers.get("HX-Request"))


@app.route("/")
def vault_home():
    pinned_notes, other_notes = _split_notes()
    return render_template(
        "main.html",
        pinned_notes=pinned_notes,
        other_notes=other_notes,
        color_choices=NOTE_COLORS,
        memory_initial={"status": "idle", "mode": "local"},
    )


@app.route("/memory/query", methods=["POST"])
def memory_query():
    payload = {}
    if request.is_json:
        payload = request.get_json(silent=True) or {}
    else:
        payload = request.form
    question = (payload.get("question") or "").strip()
    response_payload = memory_engine.ask(question)
    is_error = response_payload.get("status") == "error"
    if request.is_json and not _is_htmx():
        status_code = 400 if is_error else 200
        response_payload["question"] = question
        return jsonify(response_payload), status_code
    return (_render_memory_response(response_payload), 200)


@app.route("/notes", methods=["POST"])
def create_note():
    try:
        _create_note_from_payload(request.form)
    except ValueError as exc:
        return (str(exc), 400)
    if _is_htmx():
        return _render_note_grid()
    return redirect(url_for("vault_home"))


@app.route("/notes/<int:note_id>/edit")
def edit_note(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    return render_template(
        "partials/note_edit_form.html", note=note, color_choices=NOTE_COLORS
    )


@app.route("/notes/<int:note_id>/card")
def note_card(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    return _render_note_card(note)


@app.route("/notes/<int:note_id>/update", methods=["POST"])
def update_note(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    payload = {
        "title": request.form.get("title", note.title),
        "content": request.form.get("content", note.content),
        "color": request.form.get("color", note.color),
    }
    try:
        note = _update_note_from_payload(note, payload)
    except ValueError as exc:
        return (str(exc), 400)
    return _render_note_card(note)


@app.route("/notes/<int:note_id>/toggle-pin", methods=["POST"])
def toggle_pin(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    note.pinned = not note.pinned
    note.save()
    return _render_note_grid()


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def delete_note(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    note.delete_instance()
    return _render_note_grid()


@app.route("/notes/clear", methods=["POST"])
def clear_notes():
    Note.delete().execute()
    return _render_note_grid()


@app.route("/notes/grid")
def notes_grid():
    return _render_note_grid()


# JSON API
@app.route("/api/notes", methods=["GET"])
def api_notes():
    notes = [
        _note_to_dict(note)
        for note in Note.select().order_by(Note.pinned.desc(), Note.updated_at.desc())
    ]
    return jsonify({"notes": notes, "count": len(notes)})


@app.route("/api/notes", methods=["POST"])
def api_create_note():
    payload = request.get_json(silent=True) or {}
    try:
        note = _create_note_from_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_note_to_dict(note)), 201


@app.route("/api/notes/<int:note_id>", methods=["GET"])
def api_get_note(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    return jsonify(_note_to_dict(note))


@app.route("/api/notes/<int:note_id>", methods=["PUT"])
def api_update_note(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    payload = request.get_json(silent=True) or {}
    try:
        note = _update_note_from_payload(note, payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    note.pinned = _parse_bool(payload.get("pinned", note.pinned))
    note.save()
    return jsonify(_note_to_dict(note))


@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
def api_delete_note(note_id: int):
    note = Note.get_or_none(Note.id == note_id)
    if not note:
        abort(404)
    note.delete_instance()
    return ("", 204)
