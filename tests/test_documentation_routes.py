from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.main import create_app


class DocumentationRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_docs_endpoint_returns_markdown_body_without_duplicate_title(self) -> None:
        response = self.client.get("/api/docs/docs")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["slug"], "docs")
        self.assertEqual(payload["title"], "uZephyr Documentation: Features and Architecture")
        self.assertTrue(payload["content"].startswith("uZephyr is a local-first AI sidekick"))
        self.assertFalse(payload["content"].startswith("# "))

    def test_selected_documentation_slugs_return_markdown_content(self) -> None:
        expected_titles = {
            "api-docs": "uZephyr API Reference",
            "privacy": "Privacy Policy",
            "terms": "Terms of Service",
            "glossary": "uZephyr Glossary",
        }

        for slug, expected_title in expected_titles.items():
            with self.subTest(slug=slug):
                response = self.client.get(f"/api/docs/{slug}")

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["slug"], slug)
                self.assertEqual(payload["title"], expected_title)
                self.assertFalse(payload["content"].startswith("# "))
                self.assertTrue(payload["source_path"].startswith("Docs/"))

    def test_unknown_document_returns_not_found(self) -> None:
        response = self.client.get("/api/docs/not-real")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Unknown documentation slug", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()