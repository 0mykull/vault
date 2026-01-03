import os
import unittest

os.environ["TESTING"] = "true"

from app import Note, app  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
