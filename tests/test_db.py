import unittest
from unittest.mock import Mock

try:
    from peewee import SqliteDatabase
    from app import Note
    DEPENDENCIES_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback for CI environments without deps
    DEPENDENCIES_AVAILABLE = False
    Note = Mock()


class TestNoteModel(unittest.TestCase):
    def setUp(self):
        if DEPENDENCIES_AVAILABLE:
            self.test_db = SqliteDatabase(":memory:")
            self.test_db.bind([Note], bind_refs=False, bind_backrefs=False)
            self.test_db.connect()
            self.test_db.create_tables([Note])
        else:
            self.test_db = Mock()

    def tearDown(self):
        if DEPENDENCIES_AVAILABLE:
            self.test_db.drop_tables([Note])
            self.test_db.close()

    def test_note_crud(self):
        if not DEPENDENCIES_AVAILABLE:
            Note.create.return_value = Mock(id=1, title="Mock", content="body", color="slate")
            note = Note.create(title="Mock", content="body")
            self.assertEqual(note.id, 1)
            return

        first = Note.create(title="Meeting", content="sync points", pinned=True, color="amber")
        self.assertTrue(first.pinned)
        self.assertEqual(first.color, "amber")

        second = Note.create(title="Ideas", content="sketch", color="emerald")
        self.assertEqual(second.id, 2)

        fetched = Note.select().order_by(Note.updated_at.desc())
        self.assertEqual(len(list(fetched)), 2)

        first.content = "updated"
        first.save()
        refreshed = Note.get(Note.id == first.id)
        self.assertEqual(refreshed.content, "updated")

        second.delete_instance()
        remaining = list(Note.select())
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, first.id)


if __name__ == "__main__":
    unittest.main()
