import json
import tempfile
import unittest
from pathlib import Path

import snapshot_posts


class SnapshotTests(unittest.TestCase):
    def test_save_snapshot_skips_when_only_fetched_at_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-10-22.json"
            payload = {
                "date": "2026-10-22",
                "fetched_at": "2026-10-22T09:00:00-05:00",
                "posts": {"1": {"views": 10}},
            }
            self.assertTrue(snapshot_posts.save_snapshot(payload, path))
            changed = dict(payload, fetched_at="2026-10-22T10:00:00-05:00")
            self.assertFalse(snapshot_posts.save_snapshot(changed, path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), payload)

    def test_save_snapshot_writes_when_metrics_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-10-22.json"
            payload = {
                "date": "2026-10-22",
                "fetched_at": "2026-10-22T09:00:00-05:00",
                "posts": {"1": {"views": 10}},
            }
            snapshot_posts.save_snapshot(payload, path)
            changed = {
                "date": "2026-10-22",
                "fetched_at": "2026-10-22T10:00:00-05:00",
                "posts": {"1": {"views": 11}},
            }
            self.assertTrue(snapshot_posts.save_snapshot(changed, path))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["posts"]["1"]["views"], 11)


if __name__ == "__main__":
    unittest.main()
