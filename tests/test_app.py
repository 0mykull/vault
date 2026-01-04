import os
import unittest
from unittest import mock

os.environ["TESTING"] = "true"

from app import Note, app, memory_engine  # noqa: E402


class VaultAppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        Note.delete().execute()

    def test_homepage_loads_vault_branding(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Vault", html)
        self.assertIn("Save to Vault", html)

    def test_create_note_via_api(self):
        payload = {
            "title": "Weeklies",
            "content": "Prep talking points",
            "color": "amber",
            "pinned": True,
        }
        response = self.client.post("/api/notes", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertEqual(data["title"], payload["title"])
        self.assertTrue(data["pinned"])

        response = self.client.get("/api/notes")
        notes_payload = response.get_json()
        self.assertEqual(notes_payload["count"], 1)
        self.assertEqual(notes_payload["notes"][0]["color"], "amber")
        self.assertTrue(notes_payload["notes"][0]["tags"])

    def test_htmx_validation_blocks_empty_notes(self):
        response = self.client.post("/notes", data={}, headers={"HX-Request": "true"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Notes need a title or content", response.get_data(as_text=True))

    def test_toggle_pin_and_delete(self):
        create = self.client.post("/api/notes", json={"title": "Refactor", "content": "Ship it"})
        note_id = create.get_json()["id"]

        toggle = self.client.post(
            f"/notes/{note_id}/toggle-pin",
            headers={"HX-Request": "true"},
        )
        self.assertEqual(toggle.status_code, 200)

        single = self.client.get(f"/api/notes/{note_id}")
        self.assertTrue(single.get_json()["pinned"])

        delete = self.client.post(
            f"/notes/{note_id}/delete",
            headers={"HX-Request": "true"},
        )
        self.assertEqual(delete.status_code, 200)
        self.assertEqual(self.client.get("/api/notes").get_json()["count"], 0)

    def test_edit_flow_updates_note(self):
        note_id = self.client.post(
            "/api/notes",
            json={"title": "Scratch", "content": "v1"},
        ).get_json()["id"]

        response = self.client.post(
            f"/notes/{note_id}/update",
            data={"title": "Scratch 2", "content": "updated", "color": "emerald"},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Scratch 2", html)
        self.assertIn("emerald", html)
        self.assertIn("#scratch", html.lower())

    def test_memory_query_returns_local_recall(self):
        self.client.post(
            "/api/notes",
            json={"title": "Groceries", "content": "milk, eggs, sourdough"},
        )

        response = self.client.post(
            "/memory/query",
            data={"question": "What was on my grocery list?"},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Memory", html)
        self.assertIn("Groceries", html)

    def test_memory_query_requires_question(self):
        response = self.client.post(
            "/memory/query",
            data={"question": "   "},
            headers={"HX-Request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ask a question", response.get_data(as_text=True))

    def test_memory_query_handles_remote_failure_gracefully(self):
        self.client.post(
            "/api/notes",
            json={"title": "Gym list", "content": "Creatine and protein"},
        )
        fake_model = object()
        with mock.patch.object(memory_engine, "_ensure_model", return_value=fake_model), mock.patch.object(
            memory_engine,
            "_remote_select_notes",
            side_effect=RuntimeError("models/gemini-1.5-flash is not found"),
        ):
            response = self.client.post(
                "/memory/query",
                data={"question": "what supplements do i need"},
                headers={"HX-Request": "true"},
            )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Gemini couldn&#39;t find the configured model", html)
        self.assertIn("Showing local recall", html)


if __name__ == "__main__":
    unittest.main()
