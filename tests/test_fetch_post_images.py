import tempfile
import unittest
from pathlib import Path

import fetch_post_images


class FakeHeaders:
    def __init__(self, content_type):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class FakeResponse:
    def __init__(self, data, content_type):
        self.data = data
        self.headers = FakeHeaders(content_type)

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeAPI:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return self.payloads.pop(0)


class PostImageTests(unittest.TestCase):
    def test_post_image_url_prefers_full_picture(self):
        self.assertEqual(
            fetch_post_images.post_image_url({"full_picture": "https://example.com/a.jpg"}),
            "https://example.com/a.jpg",
        )

    def test_post_image_url_falls_back_to_attachment_media(self):
        payload = {
            "attachments": {
                "data": [{
                    "media": {"image": {"src": "https://example.com/b.jpg"}},
                    "subattachments": {
                        "data": [{"media": {"image": {"src": "https://example.com/c.jpg"}}}],
                    },
                }],
            },
        }
        self.assertEqual(fetch_post_images.post_image_url(payload), "https://example.com/b.jpg")

    def test_post_image_url_returns_none_without_media(self):
        self.assertIsNone(fetch_post_images.post_image_url({}))

    def test_existing_image_finds_jpg(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-07-06.jpg"
            path.write_bytes(b"jpg")
            self.assertEqual(fetch_post_images.existing_image("2026-07-06", directory), path)

    def test_download_image_writes_content_type_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            path = fetch_post_images.download_image(
                "https://example.com/a.jpg",
                "2026-07-06",
                directory,
                opener=lambda request, timeout: FakeResponse(b"image", "image/png"),
            )
            self.assertEqual(path.name, "2026-07-06.png")
            self.assertEqual(path.read_bytes(), b"image")

    def test_fetch_missing_skips_existing_and_downloads_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "2026-07-06.jpg"
            existing.write_bytes(b"old")
            api = FakeAPI([{"full_picture": "https://example.com/new.jpg"}])
            downloaded, skipped, failed = fetch_post_images.fetch_missing(
                api,
                [
                    {"id": "1", "date": "2026-07-06"},
                    {"id": "2", "date": "2026-07-07"},
                ],
                directory,
                opener=lambda request, timeout: FakeResponse(b"new", "image/jpeg"),
            )
            self.assertEqual([path.name for path in downloaded], ["2026-07-07.jpg"])
            self.assertEqual([path.name for path in skipped], ["2026-07-06.jpg"])
            self.assertEqual(failed, [])
            self.assertEqual(len(api.calls), 1)

    def test_fetch_missing_uses_attachment_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            api = FakeAPI([
                {},
                {"attachments": {"data": [{"media": {"image": {"src": "https://example.com/b.jpg"}}}]}},
            ])
            downloaded, _, failed = fetch_post_images.fetch_missing(
                api,
                [{"id": "1", "date": "2026-07-06"}],
                directory,
                opener=lambda request, timeout: FakeResponse(b"image", "image/jpeg"),
            )
            self.assertEqual(len(downloaded), 1)
            self.assertEqual(failed, [])
            self.assertEqual(len(api.calls), 2)


if __name__ == "__main__":
    unittest.main()
