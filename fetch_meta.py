import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "data" / "archive"
TZ = ZoneInfo("America/Lima")
API_VERSION = "v26.0"
PAGE_METRICS = (
    "page_media_view",
    "page_total_media_view_unique",
    "page_views_total",
    "page_daily_follows",
)
POST_METRICS = (
    "post_media_view",
    "post_total_media_view_unique",
    "post_reactions_by_type_total",
    "post_clicks",
    "post_clicks_by_type",
    "post_activity_by_action_type",
)
AUDIENCE_METRICS = ("page_follows_city", "page_follows_country")
VIDEO_METRICS = (
    "total_video_views",
    "total_video_complete_views",
    "total_video_view_total_time",
    "total_video_avg_time_watched",
)


class MetaAPIError(Exception):
    def __init__(self, message, code=None, subcode=None, error_type=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.subcode = subcode
        self.error_type = error_type

    def __str__(self):
        parts = [self.message]
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.subcode is not None:
            parts.append(f"subcode={self.subcode}")
        if self.error_type:
            parts.append(str(self.error_type))
        return " · ".join(parts)


class GraphAPI:
    def __init__(self, token, version=API_VERSION, opener=None, sleep=time.sleep):
        self.token = token
        self.base = f"https://graph.facebook.com/{version}"
        self._opener = opener or urllib.request.urlopen
        self._sleep = sleep

    def get(self, path, params=None, retries=3):
        url = f"{self.base}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._get_url(url, retries)

    def get_url(self, url, retries=3):
        return self._get_url(url, retries)

    def _get_url(self, url, retries):
        parsed = urllib.parse.urlparse(url)
        query = [
            (key, value)
            for key, value in urllib.parse.parse_qsl(parsed.query)
            if key != "access_token"
        ]
        clean_url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
        request = urllib.request.Request(
            clean_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": "ferre-experto-dashboard/1.0",
            },
        )
        for attempt in range(retries):
            try:
                with self._opener(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")
                error = {}
                try:
                    error = json.loads(body).get("error", {})
                except ValueError:
                    pass
                if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    self._sleep(2 ** attempt)
                    continue
                message = str(error.get("message", f"HTTP {exc.code}")).replace(self.token, "[redacted]")
                raise MetaAPIError(
                    message,
                    error.get("code"),
                    error.get("error_subcode"),
                    error.get("type"),
                ) from None
            except urllib.error.URLError as exc:
                if attempt < retries - 1:
                    self._sleep(2 ** attempt)
                    continue
                raise MetaAPIError(f"No se pudo conectar con Meta: {exc.reason}") from None
        raise MetaAPIError("No se pudo completar la solicitud a Meta")


def get_all(api, path, params):
    payload = api.get(path, params)
    items = list(payload.get("data", []))
    seen = set()
    while True:
        next_url = payload.get("paging", {}).get("next")
        if not next_url or next_url in seen:
            break
        seen.add(next_url)
        payload = api.get_url(next_url)
        items.extend(payload.get("data", []))
    return items


def to_num(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if text in ("", "N/A", "-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value):
    number = to_num(value)
    return int(round(number)) if number is not None else None


def to_seconds(value):
    number = to_num(value)
    return int(round(number / 1000)) if number is not None else None


def numeric(value):
    if isinstance(value, dict):
        numbers = [numeric(item) for item in value.values()]
        numbers = [item for item in numbers if item is not None]
        return sum(numbers) if numbers else None
    if isinstance(value, (list, tuple)):
        numbers = [numeric(item) for item in value]
        numbers = [item for item in numbers if item is not None]
        return sum(numbers) if numbers else None
    return to_int(value)


def month_bounds(month=None, today=None):
    if month:
        try:
            year, month_number = [int(part) for part in month.split("-")]
            first = date(year, month_number, 1)
        except (ValueError, TypeError):
            raise SystemExit(f"Mes inválido: {month!r}. Usa el formato YYYY-MM.")
    else:
        today = today or datetime.now(TZ).date()
        first_this_month = today.replace(day=1)
        first = (first_this_month - timedelta(days=1)).replace(day=1)
    if first.month == 12:
        next_month = date(first.year + 1, 1, 1)
    else:
        next_month = date(first.year, first.month + 1, 1)
    return first, next_month - timedelta(days=1)


def parse_insights(payload):
    result = {}
    for item in payload.get("data", []):
        name = item.get("name")
        if not name:
            continue
        points = {}
        for point in item.get("values", []):
            end_time = point.get("end_time")
            key = end_time[:10] if end_time else "lifetime"
            points[key] = point.get("value")
        result[name] = points
    return result


def latest_value(points):
    if not points:
        return None
    for key in sorted(points, reverse=True):
        if points[key] is not None:
            return points[key]
    return None


def fetch_insights(api, object_id, metrics, period, since=None, until=None):
    params = {"metric": ",".join(metrics), "period": period}
    if since:
        params["since"] = since.isoformat()
    if until:
        params["until"] = until.isoformat()
    try:
        payload = api.get(f"{object_id}/insights", params)
    except MetaAPIError as exc:
        if len(metrics) == 1:
            raise
        rows = []
        for metric in metrics:
            single = dict(params)
            single["metric"] = metric
            try:
                rows.extend(api.get(f"{object_id}/insights", single).get("data", []))
            except MetaAPIError:
                continue
        if not rows:
            raise exc
        payload = {"data": rows}
    return parse_insights(payload)


def fetch_page(api, page_id):
    payload = api.get(page_id, {"fields": "id,name,followers_count,fan_count"})
    followers = to_int(payload.get("followers_count"))
    if followers is None:
        followers = to_int(payload.get("fan_count")) or 0
    return {
        "id": str(payload.get("id", page_id)),
        "name": payload.get("name") or "Ferre Experto Pacasmayo",
        "followers": followers,
    }


def build_daily(page_insights, first, last):
    fields = (
        ("views", "page_media_view"),
        ("viewers", "page_total_media_view_unique"),
        ("visits", "page_views_total"),
        ("follows", "page_daily_follows"),
    )
    rows = []
    current = first
    while current <= last:
        key = current.isoformat()
        row = {"date": key}
        for field, metric in fields:
            row[field] = numeric(page_insights.get(metric, {}).get(key)) or 0
        rows.append(row)
        current += timedelta(days=1)
    return rows


def parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(TZ).date().isoformat()


def post_type(post):
    attachments = (post.get("attachments") or {}).get("data") or []
    media_type = ""
    if attachments:
        media_type = str(attachments[0].get("media_type") or "").lower()
    mapping = {
        "video": ("Video", True),
        "photo": ("Foto", False),
        "album": ("Álbum", False),
        "share": ("Enlace", False),
        "link": ("Enlace", False),
        "sticker": ("Sticker", False),
        "status": ("Texto", False),
    }
    if media_type in mapping:
        return mapping[media_type]
    return (media_type.title() if media_type else "Texto", False)


def reaction_total(value):
    if isinstance(value, dict):
        numbers = [to_int(item) for item in value.values()]
        numbers = [item for item in numbers if item is not None]
        return sum(numbers) if numbers else None
    return to_int(value)


def click_total(clicks, needle):
    if not isinstance(clicks, dict):
        return None
    for key, value in clicks.items():
        normalized = str(key).lower().replace("_", " ").strip()
        if needle in normalized:
            return to_int(value)
    return None


def post_insight_ids(post):
    raw_id = str(post.get("id") or "")
    if not raw_id:
        return []
    suffix = raw_id.split("_", 1)[1] if "_" in raw_id else raw_id
    candidates = [raw_id]
    match = re.search(r"facebook\.com/(\d+)/posts/(\d+)", str(post.get("permalink_url") or ""))
    if match and match.group(2) == suffix:
        candidates.append(f"{match.group(1)}_{match.group(2)}")
    from_id = str((post.get("from") or {}).get("id") or "")
    if from_id:
        candidates.append(f"{from_id}_{suffix}")
    result = []
    for item in candidates:
        if item and item not in result:
            result.append(item)
    return result


def post_media_ids(post):
    ids = []
    for attachment in (post.get("attachments") or {}).get("data") or []:
        target = attachment.get("target") or {}
        if target.get("id"):
            ids.append(str(target["id"]))
        for sub in (attachment.get("subattachments") or {}).get("data") or []:
            target = sub.get("target") or {}
            if target.get("id"):
                ids.append(str(target["id"]))
    return list(dict.fromkeys(ids))


def has_insight_data(insights):
    return any(latest_value(points) is not None for points in insights.values())


def fetch_post_insights(api, post):
    last_error = None
    for object_id in post_insight_ids(post) + post_media_ids(post):
        try:
            insights = fetch_insights(api, object_id, POST_METRICS, "lifetime")
        except MetaAPIError as exc:
            last_error = exc
            continue
        if has_insight_data(insights):
            return insights
    if last_error and not post_media_ids(post):
        print(
            f"Advertencia: no se pudieron leer métricas del post {post.get('id')}: {last_error}",
            file=sys.stderr,
        )
    return {}


def parse_video_insights(payload):
    result = {}
    for item in payload.get("data", []):
        values = item.get("values") or []
        if values:
            result[item.get("name")] = values[-1].get("value")
    return result


def fetch_video_insights(api, post):
    for media_id in post_media_ids(post):
        params = {"metric": ",".join(VIDEO_METRICS)}
        try:
            payload = api.get(f"{media_id}/video_insights", params)
        except MetaAPIError as exc:
            if exc.code != 100:
                continue
            rows = []
            for metric in VIDEO_METRICS:
                try:
                    rows.extend(api.get(f"{media_id}/video_insights", {"metric": metric}).get("data", []))
                except MetaAPIError:
                    continue
            payload = {"data": rows}
        insights = parse_video_insights(payload)
        if insights:
            return insights
    return {}


def build_post(api, post):
    insights = fetch_post_insights(api, post)
    label, is_video = post_type(post)
    video = fetch_video_insights(api, post) if is_video else {}
    activity = latest_value(insights.get("post_activity_by_action_type", {}))
    if not isinstance(activity, dict):
        activity = {}
    reactions = reaction_total(latest_value(insights.get("post_reactions_by_type_total", {})))
    if reactions is None:
        reactions = to_int(activity.get("like"))
    if reactions is None:
        reactions = to_int(((post.get("reactions") or {}).get("summary") or {}).get("total_count"))
    comments = to_int(((post.get("comments") or {}).get("summary") or {}).get("total_count"))
    if comments in (None, 0) and activity.get("comment") is not None:
        comments = to_int(activity.get("comment"))
    shares = to_int((post.get("shares") or {}).get("count"))
    if shares in (None, 0) and activity.get("share") is not None:
        shares = to_int(activity.get("share"))
    interactions = None
    if any(item is not None for item in (reactions, comments, shares)):
        interactions = (reactions or 0) + (comments or 0) + (shares or 0)
    clicks = latest_value(insights.get("post_clicks_by_type", {}))
    views = numeric(latest_value(insights.get("post_media_view", {})))
    viewers = numeric(latest_value(insights.get("post_total_media_view_unique", {})))
    if is_video:
        video_views = to_int(video.get("total_video_views"))
        if video_views is not None:
            views = video_views
        viewers = None
    return {
        "id": str(post["id"]),
        "date": parse_date(post.get("created_time")),
        "type": label,
        "caption": (post.get("message") or "").strip(),
        "permalink": post.get("permalink_url") or None,
        "image": None,
        "isVideo": is_video,
        "metrics": {
            "views": views,
            "viewers": viewers,
            "reach": None,
            "interactions": interactions,
            "reactions": reactions,
            "comments": comments,
            "shares": shares,
            "totalClicks": numeric(latest_value(insights.get("post_clicks", {}))),
            "linkClicks": click_total(clicks, "link"),
            "otherClicks": click_total(clicks, "other"),
            "photoClicks": click_total(clicks, "photo"),
            "secondsViewed": to_seconds(video.get("total_video_view_total_time")),
            "averageSecondsViewed": to_seconds(video.get("total_video_avg_time_watched")),
            "threeSecondViews": to_int(video.get("total_video_views")),
            "oneMinuteViews": None,
            "threeSecondViewers": None,
            "oneMinuteViewers": None,
            "duration": None,
        },
    }


def fetch_posts(api, page_id, first, last):
    params = {
        "fields": "id,created_time,message,permalink_url,from{id,name},shares,comments.summary(true).limit(0),reactions.summary(true).limit(0),attachments{media_type,target,subattachments}",
        "since": first.isoformat(),
        "until": (last + timedelta(days=1)).isoformat(),
        "limit": 100,
    }
    posts = []
    for raw in get_all(api, f"{page_id}/posts", params):
        day = parse_date(raw.get("created_time"))
        if not day or not (first.isoformat() <= day <= last.isoformat()):
            continue
        post = build_post(api, raw)
        if post["date"]:
            post["month"] = post["date"][:7]
            posts.append(post)
    posts.sort(key=lambda item: item["date"], reverse=True)
    return posts


def breakdown_rows(points, limit=10):
    value = latest_value(points)
    rows = []
    if isinstance(value, dict):
        rows = [(str(key), to_num(item)) for key, item in value.items()]
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                name = item.get("name") or item.get("key")
                count = item.get("value") if item.get("value") is not None else item.get("count")
                if name is not None:
                    rows.append((str(name), to_num(count)))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                rows.append((str(item[0]), to_num(item[1])))
    rows = [(name, count) for name, count in rows if name and count is not None]
    total = sum(count for _, count in rows)
    if total <= 0:
        return []
    result = [{"name": name, "pct": round(count / total * 100, 1)} for name, count in rows]
    result.sort(key=lambda item: item["pct"], reverse=True)
    return result[:limit]


def fetch_audience(api, page_id):
    insights = fetch_insights(api, page_id, AUDIENCE_METRICS, "lifetime")
    return {
        "cities": breakdown_rows(insights.get("page_follows_city", {})),
        "countries": breakdown_rows(insights.get("page_follows_country", {})),
    }


def build_month_payload(api, page_id, first, last):
    page = fetch_page(api, page_id)
    page_insights = fetch_insights(api, page_id, PAGE_METRICS, "day", first, last)
    return {
        "month": first.strftime("%Y-%m"),
        "since": first.isoformat(),
        "until": last.isoformat(),
        "cutoff": last.isoformat(),
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "page": page,
        "daily": build_daily(page_insights, first, last),
        "posts": fetch_posts(api, page_id, first, last),
        "audience": fetch_audience(api, page_id),
    }


def save_archive(payload, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def probe(api, page_id, first, last):
    page = fetch_page(api, page_id)
    print(f"Página: {page['name']} ({page['id']})")
    print(f"Seguidores: {page['followers']}")
    print(f"Período: {first} → {last}")

    for metric in PAGE_METRICS:
        try:
            payload = api.get(
                f"{page_id}/insights",
                {
                    "metric": metric,
                    "period": "day",
                    "since": first.isoformat(),
                    "until": last.isoformat(),
                },
            )
            points = parse_insights(payload).get(metric, {})
            print(f"page {metric}: OK ({len(points)} días)")
        except MetaAPIError as exc:
            print(f"page {metric}: ERROR {exc}")

    posts = get_all(api, f"{page_id}/posts", {"fields": "id,created_time", "limit": 1})
    if posts:
        post_id = posts[0]["id"]
        for metric in POST_METRICS:
            try:
                api.get(f"{post_id}/insights", {"metric": metric, "period": "lifetime"})
                print(f"post {metric}: OK")
            except MetaAPIError as exc:
                print(f"post {metric}: ERROR {exc}")
    else:
        print("post insights: no hay publicaciones para probar")

    for metric in AUDIENCE_METRICS:
        try:
            api.get(f"{page_id}/insights", {"metric": metric, "period": "lifetime"})
            print(f"audience {metric}: OK")
        except MetaAPIError as exc:
            print(f"audience {metric}: ERROR {exc}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Descarga las métricas mensuales del fanpage desde Meta Graph API."
    )
    parser.add_argument("--month", help="Mes a descargar en formato YYYY-MM. Por defecto, el mes anterior.")
    parser.add_argument("--page-id", default=os.environ.get("META_PAGE_ID"), help="ID de la página. También META_PAGE_ID.")
    parser.add_argument("--token", default=os.environ.get("META_PAGE_TOKEN"), help="Token de página. También META_PAGE_TOKEN.")
    parser.add_argument("--output", help="Ruta del JSON. Por defecto data/archive/YYYY-MM.json.")
    parser.add_argument("--probe", action="store_true", help="Comprueba permisos y métricas sin guardar datos.")
    args = parser.parse_args(argv)

    if not args.token:
        raise SystemExit(
            "Falta META_PAGE_TOKEN. Créalo en Meta y guárdalo como secreto; no lo pases por el chat."
        )
    if not args.page_id:
        raise SystemExit("Falta META_PAGE_ID. Usa --page-id o la variable META_PAGE_ID.")

    first, last = month_bounds(args.month)
    api = GraphAPI(args.token)

    try:
        if args.probe:
            probe(api, args.page_id, first, last)
            return 0

        payload = build_month_payload(api, args.page_id, first, last)
    except MetaAPIError as exc:
        raise SystemExit(f"Error de Meta: {exc}") from None

    output = Path(args.output) if args.output else ARCHIVE / f"{payload['month']}.json"
    save_archive(payload, output)

    totals = {
        key: sum(row[key] for row in payload["daily"])
        for key in ("views", "viewers", "visits", "follows")
    }
    print(f"Mes: {payload['month']} ({payload['since']} → {payload['until']})")
    print(f"Publicaciones: {len(payload['posts'])}")
    print(
        f"Views: {totals['views']} · Viewers: {totals['viewers']} · "
        f"Visits: {totals['visits']} · Follows: {totals['follows']}"
    )
    print(f"Archivo: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
