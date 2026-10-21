import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build.build_payload()
        cls.posts = cls.payload["posts"]
        cls.months = {row["month"]: row for row in cls.payload["results"]["monthly"]}

    def test_posts_count(self):
        self.assertEqual(len(build.read_posts(build.DATA / "posts.csv")), 7)

    def test_videos_count(self):
        self.assertEqual(len(build.read_videos(build.DATA / "videos.csv")), 2)

    def test_publications_merge(self):
        self.assertEqual(len(self.posts), 8)
        dates = [post["date"] for post in self.posts]
        self.assertEqual(dates.count("2026-09-01"), 1)
        self.assertIn("2026-09-16", dates)
        september_first = next(post for post in self.posts if post["date"] == "2026-09-01")
        self.assertEqual(september_first["metrics"]["threeSecondViews"], 241)

    def test_results_totals(self):
        self.assertEqual(sum(row["views"] for row in self.payload["results"]["daily"]), 10574)
        self.assertEqual(sum(row["viewers"] for row in self.payload["results"]["daily"]), 3682)
        self.assertEqual(sum(row["visits"] for row in self.payload["results"]["daily"]), 2156)
        self.assertEqual(sum(row["follows"] for row in self.payload["results"]["daily"]), 67)

    def test_monthly_totals(self):
        self.assertEqual(self.months["2026-08"]["views"], 2797)
        self.assertEqual(self.months["2026-09"]["views"], 6154)
        self.assertEqual(self.months["2026-10"]["views"], 1623)
        self.assertEqual(self.months["2026-09"]["follows"], 55)

    def test_audience_gender_sums_to_100(self):
        men = sum(row["men"] for row in self.payload["audience"]["ageGender"])
        women = sum(row["women"] for row in self.payload["audience"]["ageGender"])
        self.assertAlmostEqual(men + women, 100, delta=0.2)

    def test_zero_reach_has_no_engagement(self):
        self.assertIsNone(build.engagement_rate(10, 0, 100))
        self.assertIsNone(build.engagement_rate(10, 100, None))
        self.assertEqual(build.engagement_rate(25, 100, 500), 25.0)

    def test_payload_shape(self):
        self.assertEqual(self.payload["page"]["followers"], 2725)
        self.assertEqual(len(self.payload["results"]["daily"]), 82)
        self.assertEqual(len(self.payload["audience"]["cities"]), 10)
        self.assertEqual(len(self.payload["audience"]["countries"]), 10)
        json.dumps(self.payload)


if __name__ == "__main__":
    unittest.main()
