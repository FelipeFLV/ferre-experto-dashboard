import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path

import meta_page_token


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def __call__(self, request, timeout=30):
        self.requests.append(request)
        return FakeResponse(self.payload)


class TokenExchangeTests(unittest.TestCase):
    def test_exchange_sends_form_data_and_returns_token(self):
        opener = FakeOpener({"access_token": "LONG_USER_TOKEN", "expires_in": 5184000})
        token = meta_page_token.exchange_user_token(
            "APP_ID", "APP_SECRET", "SHORT_TOKEN", opener=opener
        )
        self.assertEqual(token, "LONG_USER_TOKEN")
        request = opener.requests[0]
        self.assertEqual(request.get_method(), "POST")
        body = request.data.decode("utf-8")
        self.assertIn("grant_type=fb_exchange_token", body)
        self.assertIn("client_id=APP_ID", body)
        self.assertIn("client_secret=APP_SECRET", body)
        self.assertIn("fb_exchange_token=SHORT_TOKEN", body)

    def test_exchange_rejects_missing_token(self):
        opener = FakeOpener({"error": {"message": "bad"}})
        with self.assertRaises(meta_page_token.TokenError):
            meta_page_token.exchange_user_token(
                "APP_ID", "APP_SECRET", "SHORT_TOKEN", opener=opener
            )


class PageSelectionTests(unittest.TestCase):
    def test_select_exact_page(self):
        pages = [
            {"id": "1", "name": "Otra Página", "access_token": "a"},
            {"id": "2", "name": "Ferre Experto Pacasmayo", "access_token": "b"},
        ]
        self.assertEqual(meta_page_token.select_page(pages, "Ferre Experto Pacasmayo")["id"], "2")

    def test_select_partial_page(self):
        pages = [{"id": "2", "name": "Ferre Experto Pacasmayo", "access_token": "b"}]
        self.assertEqual(meta_page_token.select_page(pages, "Ferre Experto")["id"], "2")

    def test_select_missing_page_lists_available(self):
        pages = [{"id": "1", "name": "Otra Página", "access_token": "a"}]
        with self.assertRaises(meta_page_token.TokenError) as context:
            meta_page_token.select_page(pages, "Ferre Experto")
        self.assertIn("Otra Página", str(context.exception))

    def test_select_ambiguous_page(self):
        pages = [
            {"id": "1", "name": "Ferre Experto Lima", "access_token": "a"},
            {"id": "2", "name": "Ferre Experto Pacasmayo", "access_token": "b"},
        ]
        with self.assertRaises(meta_page_token.TokenError):
            meta_page_token.select_page(pages, "Ferre Experto")


class EnvFileTests(unittest.TestCase):
    def test_write_env_quotes_values_and_restricts_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            meta_page_token.write_env(path, "123", "token with spaces")
            content = path.read_text(encoding="utf-8")
            self.assertIn("META_PAGE_ID=123", content)
            self.assertIn("META_PAGE_TOKEN='token with spaces'", content)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertFalse(path.with_suffix(".env.tmp").exists())


class ErrorRedactionTests(unittest.TestCase):
    def test_error_does_not_leak_secrets(self):
        def opener(request, timeout=30):
            body = json.dumps(
                {"error": {"message": "bad APP_SECRET and SHORT_TOKEN"}}
            ).encode("utf-8")
            raise urllib.error.HTTPError(
                request.full_url, 400, "Bad Request", {}, io.BytesIO(body)
            )

        with self.assertRaises(meta_page_token.TokenError) as context:
            meta_page_token.exchange_user_token(
                "APP_ID", "APP_SECRET", "SHORT_TOKEN", opener=opener
            )
        message = str(context.exception)
        self.assertNotIn("APP_SECRET", message)
        self.assertNotIn("SHORT_TOKEN", message)


if __name__ == "__main__":
    unittest.main()
