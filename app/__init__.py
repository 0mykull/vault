from __future__ import annotations
import datetime
import os

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
from peewee import BooleanField, CharField, DateTimeField, Model, SqliteDatabase, TextField
from playhouse.shortcuts import model_to_dict

load_dotenv()
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

NOTE_COLORS = ["slate", "amber", "emerald", "rose", "sky", "violet"]

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
    created_at = DateTimeField(default=datetime.datetime.utcnow)
    updated_at = DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):  # noqa: D401
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

db.connect(reuse_if_open=True)
db.create_tables([Note])

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

def _create_note_from_payload(payload: dict) -> Note:
    title = payload.get("title", "").strip()
    content = payload.get("content", "").strip()
    color = _normalize_color(payload.get("color"))
    pinned = _parse_bool(payload.get("pinned"))
    if not title and not content:
        raise ValueError("Notes need a title or content")
    return Note.create(title=title, content=content, color=color, pinned=pinned)

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
    return note

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
    )

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
    return render_template("partials/note_edit_form.html", note=note, color_choices=NOTE_COLORS)

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
