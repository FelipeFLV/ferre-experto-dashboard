import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "archive"
HISTORY_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "post-history"


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build.build_payload(FIXTURES, HISTORY_FIXTURES)
        cls.posts = cls.payload["posts"]
        cls.months = {row["month"]: row for row in cls.payload["results"]["monthly"]}

    def test_months_are_built_from_archives(self):
        self.assertEqual([month["key"] for month in self.payload["months"]], ["2026-08", "2026-09", "2026-10"])
        self.assertEqual(self.payload["months"][0]["label"], "Agosto 2026")
        self.assertEqual(self.payload["months"][-1]["short"], "Oct")
        self.assertEqual([month["partial"] for month in self.payload["months"]], [False, False, True])
        self.assertEqual(self.payload["page"]["cutoff"], "2026-10-21")

    def test_daily_series_stops_at_cutoff(self):
        daily = self.payload["results"]["daily"]
        self.assertEqual(len(daily), 82)
        self.assertEqual(daily[-1]["date"], "2026-10-21")
        self.assertTrue(all(row["date"] <= self.payload["page"]["cutoff"] for row in daily))
        self.assertEqual(len({row["date"] for row in daily}), len(daily))

    def test_results_totals(self):
        self.assertEqual(sum(row["views"] for row in self.payload["results"]["daily"]), 10531)
        self.assertEqual(sum(row["viewers"] for row in self.payload["results"]["daily"]), 3660)
        self.assertEqual(sum(row["visits"] for row in self.payload["results"]["daily"]), 2150)
        self.assertEqual(sum(row["follows"] for row in self.payload["results"]["daily"]), 67)

    def test_monthly_totals(self):
        self.assertEqual(self.months["2026-08"]["views"], 2767)
        self.assertEqual(self.months["2026-09"]["views"], 6145)
        self.assertEqual(self.months["2026-10"]["views"], 1619)
        self.assertEqual(self.months["2026-09"]["follows"], 55)

    def test_publications_merge_by_id(self):
        self.assertEqual(len(self.posts), 8)
        self.assertEqual(len({post["id"] for post in self.posts}), len(self.posts))
        self.assertEqual([post["date"] for post in self.posts], sorted((post["date"] for post in self.posts), reverse=True))

    def test_api_post_metrics(self):
        photo = next(post for post in self.posts if post["date"] == "2026-10-14")
        self.assertEqual(photo["metrics"]["views"], 1490)
        self.assertEqual(photo["metrics"]["viewers"], 763)
        self.assertEqual(photo["metrics"]["interactions"], 36)
        self.assertEqual(photo["metrics"]["totalClicks"], 20)
        self.assertEqual(photo["engagementRate"], 2.4)
        suffix = ".jpg" if build.has_image_optimizer() else ".png"
        self.assertEqual(photo["image"], f"assets/posts/2026-10-14{suffix}")

        video = next(post for post in self.posts if post["date"] == "2026-10-21")
        self.assertTrue(video["isVideo"])
        self.assertEqual(video["metrics"]["views"], 310)
        self.assertEqual(video["metrics"]["interactions"], 238)
        self.assertIsNone(video["metrics"]["reach"])
        self.assertEqual(video["engagementRate"], 76.8)

    def test_post_history_is_loaded_for_known_posts(self):
        history = self.payload["postHistory"]
        video_id = "657698394862718_1647944423485062"
        self.assertEqual(self.payload["postHistoryStart"], "2026-10-21")
        self.assertEqual([item["date"] for item in history[video_id]], ["2026-10-21", "2026-10-22"])
        self.assertEqual(history[video_id][-1]["metrics"]["views"], 310)

    def test_audience_is_empty_without_api_demographics(self):
        self.assertEqual(self.payload["audience"], {"ageGender": [], "cities": [], "countries": []})

    def test_zero_reach_falls_back_to_views(self):
        self.assertIsNone(build.engagement_rate(10, 0, None))
        self.assertIsNone(build.engagement_rate(10, None, None))
        self.assertEqual(build.engagement_rate(25, 100, 500), 25.0)
        self.assertEqual(build.engagement_rate(25, None, 500), 5.0)

    def test_payload_shape(self):
        self.assertEqual(self.payload["page"]["followers"], 2743)
        self.assertEqual(self.payload["page"]["updatedAt"], "2026-10-21T22:54:14-05:00")
        self.assertEqual(len(self.payload["months"]), 3)
        json.dumps(self.payload)


if __name__ == "__main__":
    unittest.main()
