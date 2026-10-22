import io
import json
import tempfile
import unittest
import urllib.error
from datetime import date
from pathlib import Path

import fetch_meta


class FakeAPI:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, path, params=None, retries=3):
        self.calls.append((path, params or {}))
        return self.handler(path, params or {})

    def get_url(self, url, retries=3):
        raise AssertionError(f"Paginación inesperada: {url}")


def insights_response(metric, value, end_time="2026-10-05T07:00:00+0000"):
    return {
        "data": [
            {
                "name": metric,
                "period": "lifetime",
                "values": [{"value": value, "end_time": end_time}],
            }
        ]
    }


class MonthBoundsTests(unittest.TestCase):
    def test_explicit_month(self):
        first, last = fetch_meta.month_bounds("2026-10")
        self.assertEqual(first, date(2026, 10, 1))
        self.assertEqual(last, date(2026, 10, 31))

    def test_previous_month_from_first_day(self):
        first, last = fetch_meta.month_bounds(today=date(2026, 11, 1))
        self.assertEqual(first, date(2026, 10, 1))
        self.assertEqual(last, date(2026, 10, 31))

    def test_previous_month_across_year(self):
        first, last = fetch_meta.month_bounds(today=date(2026, 1, 15))
        self.assertEqual(first, date(2025, 12, 1))
        self.assertEqual(last, date(2025, 12, 31))

    def test_leap_year(self):
        first, last = fetch_meta.month_bounds("2024-02")
        self.assertEqual(first, date(2024, 2, 1))
        self.assertEqual(last, date(2024, 2, 29))


class InsightParsingTests(unittest.TestCase):
    def test_parse_insights_and_daily_fill(self):
        payload = {
            "data": [
                {
                    "name": "page_media_view",
                    "values": [
                        {"value": 10, "end_time": "2026-10-01T07:00:00+0000"},
                        {"value": 30, "end_time": "2026-10-03T07:00:00+0000"},
                    ],
                },
                {
                    "name": "page_total_media_view_unique",
                    "values": [{"value": 4, "end_time": "2026-10-01T07:00:00+0000"}],
                },
                {
                    "name": "page_views_total",
                    "values": [{"value": 2, "end_time": "2026-10-02T07:00:00+0000"}],
                },
                {
                    "name": "page_daily_follows",
                    "values": [{"value": 1, "end_time": "2026-10-01T07:00:00+0000"}],
                },
            ]
        }
        parsed = fetch_meta.parse_insights(payload)
        rows = fetch_meta.build_daily(parsed, date(2026, 10, 1), date(2026, 10, 3))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"date": "2026-10-01", "views": 10, "viewers": 4, "visits": 0, "follows": 1})
        self.assertEqual(rows[1], {"date": "2026-10-02", "views": 0, "viewers": 0, "visits": 2, "follows": 0})
        self.assertEqual(rows[2], {"date": "2026-10-03", "views": 30, "viewers": 0, "visits": 0, "follows": 0})

    def test_latest_value_ignores_empty_points(self):
        self.assertIsNone(fetch_meta.latest_value({}))
        self.assertIsNone(fetch_meta.latest_value({"2026-10-01": None}))
        self.assertEqual(fetch_meta.latest_value({"2026-10-01": 5, "2026-10-02": 7}), 7)

    def test_fetch_insights_falls_back_to_individual_metrics(self):
        def handler(path, params):
            metric = params["metric"]
            if "," in metric:
                raise fetch_meta.MetaAPIError("invalid metric", code=100)
            if metric == "post_media_view":
                return insights_response(metric, 100)
            raise fetch_meta.MetaAPIError("invalid metric", code=100)

        api = FakeAPI(handler)
        parsed = fetch_meta.fetch_insights(
            api, "post-1", ("post_media_view", "post_clicks"), "lifetime"
        )
        self.assertEqual(parsed["post_media_view"]["2026-10-05"], 100)
        self.assertNotIn("post_clicks", parsed)


class PostMappingTests(unittest.TestCase):
    def test_post_type(self):
        self.assertEqual(fetch_meta.post_type({"attachments": {"data": [{"media_type": "video"}]}}), ("Video", True))
        self.assertEqual(fetch_meta.post_type({"attachments": {"data": [{"media_type": "photo"}]}}), ("Foto", False))
        self.assertEqual(fetch_meta.post_type({"attachments": {"data": []}}), ("Texto", False))

    def test_reaction_total(self):
        self.assertEqual(fetch_meta.reaction_total({"like": 10, "love": 2}), 12)
        self.assertIsNone(fetch_meta.reaction_total({}))
        self.assertEqual(fetch_meta.reaction_total("3"), 3)

    def test_click_total_normalizes_keys(self):
        clicks = {"link_clicks": 20, "Other Clicks": 5, "photo clicks": 2}
        self.assertEqual(fetch_meta.click_total(clicks, "link"), 20)
        self.assertEqual(fetch_meta.click_total(clicks, "other"), 5)
        self.assertEqual(fetch_meta.click_total(clicks, "photo"), 2)
        self.assertIsNone(fetch_meta.click_total(None, "link"))

    def test_build_post_requests_post_insights_path(self):
        seen = []

        def handler(path, params):
            seen.append(path)
            metrics = params["metric"].split(",")
            return {"data": [insights_response(metric, 1)["data"][0] for metric in metrics]}

        raw = {
            "id": "123_456",
            "created_time": "2026-10-05T18:30:00+0000",
            "attachments": {"data": [{"media_type": "photo"}]},
        }
        fetch_meta.build_post(FakeAPI(handler), raw)
        self.assertEqual(seen, ["123_456/insights"])

    def test_build_post_maps_lifetime_metrics(self):
        responses = {
            "post_media_view": insights_response("post_media_view", 1000),
            "post_total_media_view_unique": insights_response("post_total_media_view_unique", 800),
            "post_reactions_by_type_total": insights_response(
                "post_reactions_by_type_total", {"like": 10, "love": 2}
            ),
            "post_clicks": insights_response("post_clicks", 30),
            "post_clicks_by_type": insights_response(
                "post_clicks_by_type",
                {"link clicks": 20, "other clicks": 5, "photo clicks": 5},
            ),
            "post_activity_by_action_type": insights_response(
                "post_activity_by_action_type",
                {"like": 12, "comment": 7, "share": 3},
            ),
        }

        def handler(path, params):
            metrics = params["metric"].split(",")
            if len(metrics) > 1:
                return {"data": [responses[metric]["data"][0] for metric in metrics]}
            return responses[metrics[0]]

        raw = {
            "id": "123_456",
            "created_time": "2026-10-05T18:30:00+0000",
            "message": "Post de prueba",
            "permalink_url": "https://facebook.com/123/posts/456",
            "shares": {"count": 3},
            "comments": {"summary": {"total_count": 7}},
            "attachments": {"data": [{"media_type": "photo"}]},
        }
        post = fetch_meta.build_post(FakeAPI(handler), raw)
        self.assertEqual(post["date"], "2026-10-05")
        self.assertEqual(post["type"], "Foto")
        self.assertFalse(post["isVideo"])
        self.assertEqual(post["metrics"]["views"], 1000)
        self.assertEqual(post["metrics"]["viewers"], 800)
        self.assertEqual(post["metrics"]["reactions"], 12)
        self.assertEqual(post["metrics"]["comments"], 7)
        self.assertEqual(post["metrics"]["shares"], 3)
        self.assertEqual(post["metrics"]["interactions"], 22)
        self.assertEqual(post["metrics"]["totalClicks"], 30)
        self.assertEqual(post["metrics"]["linkClicks"], 20)
        self.assertEqual(post["metrics"]["otherClicks"], 5)
        self.assertEqual(post["metrics"]["photoClicks"], 5)

    def test_build_post_tries_legacy_permalink_id(self):
        legacy_id = "1712999594163303_1705230774940185"
        values = {
            "post_media_view": 1472,
            "post_total_media_view_unique": 763,
            "post_reactions_by_type_total": {"like": 26, "love": 1},
            "post_clicks": 20,
            "post_clicks_by_type": {"other clicks": 10, "photo view": 4, "link clicks": 6},
            "post_activity_by_action_type": {"share": 8, "like": 27, "comment": 1},
        }
        seen = []

        def handler(path, params):
            seen.append(path)
            if path.startswith("657698394862718_"):
                return {"data": []}
            metrics = params["metric"].split(",")
            return {"data": [insights_response(metric, values[metric])["data"][0] for metric in metrics]}

        raw = {
            "id": "657698394862718_1705230774940185",
            "created_time": "2026-10-14T14:24:00+0000",
            "permalink_url": "https://www.facebook.com/1712999594163303/posts/1705230774940185",
            "attachments": {"data": [{"media_type": "photo"}]},
        }
        post = fetch_meta.build_post(FakeAPI(handler), raw)
        self.assertEqual(seen[0], "657698394862718_1705230774940185/insights")
        self.assertEqual(seen[1], f"{legacy_id}/insights")
        self.assertEqual(post["metrics"]["views"], 1472)
        self.assertEqual(post["metrics"]["viewers"], 763)
        self.assertEqual(post["metrics"]["reactions"], 27)
        self.assertEqual(post["metrics"]["comments"], 1)
        self.assertEqual(post["metrics"]["shares"], 8)
        self.assertEqual(post["metrics"]["interactions"], 36)
        self.assertEqual(post["metrics"]["totalClicks"], 20)
        self.assertEqual(post["metrics"]["linkClicks"], 6)
        self.assertEqual(post["metrics"]["otherClicks"], 10)
        self.assertEqual(post["metrics"]["photoClicks"], 4)

    def test_build_post_uses_activity_for_missing_comments_and_shares(self):
        def handler(path, params):
            return insights_response(
                "post_activity_by_action_type",
                {"like": 27, "comment": 1, "share": 8},
            )

        raw = {
            "id": "123_456",
            "created_time": "2026-10-14T14:24:00+0000",
            "shares": {"count": 0},
            "comments": {"summary": {"total_count": 0}},
            "reactions": {"summary": {"total_count": 11}},
            "attachments": {"data": [{"media_type": "photo"}]},
        }
        post = fetch_meta.build_post(FakeAPI(handler), raw)
        self.assertEqual(post["metrics"]["reactions"], 27)
        self.assertEqual(post["metrics"]["comments"], 1)
        self.assertEqual(post["metrics"]["shares"], 8)
        self.assertEqual(post["metrics"]["interactions"], 36)


class AudienceTests(unittest.TestCase):
    def test_breakdown_dict_percentages(self):
        rows = fetch_meta.breakdown_rows({"2026-10-05": {"Lima": 60, "Trujillo": 30, "Otros": 10}})
        self.assertEqual(rows[0]["name"], "Lima")
        self.assertEqual(rows[0]["pct"], 60.0)
        self.assertAlmostEqual(sum(row["pct"] for row in rows), 100.0, delta=0.1)

    def test_breakdown_list(self):
        rows = fetch_meta.breakdown_rows(
            {"2026-10-05": [{"name": "Perú", "value": 80}, {"name": "Chile", "value": 20}]}
        )
        self.assertEqual(rows, [{"name": "Perú", "pct": 80.0}, {"name": "Chile", "pct": 20.0}])

    def test_breakdown_empty(self):
        self.assertEqual(fetch_meta.breakdown_rows({}), [])


class GraphAPIErrorTests(unittest.TestCase):
    def test_error_does_not_leak_token(self):
        def opener(request, timeout=30):
            body = json.dumps(
                {
                    "error": {
                        "message": "Invalid OAuth access token SECRET_TOKEN_VALUE",
                        "code": 190,
                        "type": "OAuthException",
                    }
                }
            ).encode("utf-8")
            raise urllib.error.HTTPError(
                request.full_url, 400, "Bad Request", {}, io.BytesIO(body)
            )

        api = fetch_meta.GraphAPI("SECRET_TOKEN_VALUE", opener=opener)
        with self.assertRaises(fetch_meta.MetaAPIError) as context:
            api.get("me")
        self.assertNotIn("SECRET_TOKEN_VALUE", str(context.exception))
        self.assertEqual(context.exception.code, 190)


class ArchiveTests(unittest.TestCase):
    def test_save_archive_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-10.json"
            fetch_meta.save_archive({"month": "2026-10", "posts": []}, path)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"month": "2026-10", "posts": []})
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
