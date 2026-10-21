import csv
import io
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SRC = ROOT / "src"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets" / "posts"

MONTHS = [
    {"key": "2026-08", "label": "Agosto 2026", "short": "Ago"},
    {"key": "2026-09", "label": "Septiembre 2026", "short": "Sep"},
    {"key": "2026-10", "label": "Octubre 2026", "short": "Oct"},
]


def read_text(path):
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def to_num(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text in ("", "N/A", "-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value):
    number = to_num(value)
    if number is None:
        return None
    return int(round(number))


def parse_date(value):
    text = str(value).strip()
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise SystemExit(f"No se pudo interpretar la fecha: {value!r}")


def require(path):
    if not Path(path).exists():
        raise SystemExit(f"Falta el archivo requerido: {path}")
    return path


def read_results(path):
    require(path)
    lines = read_text(path).splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lstrip('"').lower().startswith("date"):
            start = index + 1
            break
    if start is None:
        raise SystemExit(f"No se encontró el encabezado 'Date' en {path}")
    rows = []
    for row in csv.reader(lines[start:]):
        if len(row) < 2 or not row[0].strip():
            continue
        rows.append((row[0].strip()[:10], to_num(row[1]) or 0.0))
    if not rows:
        raise SystemExit(f"La serie no tiene datos: {path}")
    return rows


def read_audience(path):
    require(path)
    lines = [line for line in read_text(path).splitlines() if line.strip()]
    rows = [row for row in csv.reader(lines)]
    rows = [row for row in rows if row and not row[0].strip().startswith("sep=")]
    markers = ("Age & gender", "Top cities", "Top countries")

    result = {"ageGender": [], "cities": [], "countries": []}
    index = 0
    while index < len(rows):
        title = rows[index][0].strip()
        if title == "Age & gender":
            index += 1
            if index < len(rows) and any(cell.strip().lower() == "men" for cell in rows[index]):
                index += 1
            while index < len(rows) and rows[index][0].strip() not in markers:
                row = rows[index]
                if len(row) >= 3 and row[0].strip():
                    result["ageGender"].append({
                        "age": row[0].strip(),
                        "men": to_num(row[1]) or 0.0,
                        "women": to_num(row[2]) or 0.0,
                    })
                index += 1
        elif title in ("Top cities", "Top countries"):
            key = "cities" if title == "Top cities" else "countries"
            index += 1
            names = rows[index] if index < len(rows) else []
            index += 1
            values = rows[index] if index < len(rows) else []
            index += 1
            for name, value in zip(names, values):
                if name.strip():
                    result[key].append({"name": name.strip(), "pct": to_num(value) or 0.0})
        else:
            index += 1

    if not result["ageGender"]:
        raise SystemExit(f"No se pudo leer la demografía en {path}")
    return result


def read_posts(path):
    require(path)
    reader = csv.DictReader(io.StringIO(read_text(path)))
    posts = []
    for row in reader:
        if not row.get("Post ID"):
            continue
        reactions = to_int(row.get("Reactions"))
        comments = to_int(row.get("Comments"))
        shares = to_int(row.get("Shares"))
        interactions = to_int(row.get("Reactions, Comments and Shares"))
        if interactions is None:
            interactions = (reactions or 0) + (comments or 0) + (shares or 0)
        posts.append({
            "id": row["Post ID"].strip(),
            "date": parse_date(row.get("Publish time")),
            "type": (row.get("Post type") or "").strip(),
            "caption": (row.get("Title") or "").strip(),
            "permalink": (row.get("Permalink") or "").strip() or None,
            "metrics": {
                "views": to_int(row.get("Views")),
                "reach": to_int(row.get("Reach")),
                "interactions": interactions,
                "reactions": reactions,
                "comments": comments,
                "shares": shares,
                "totalClicks": to_int(row.get("Total clicks")),
                "linkClicks": to_int(row.get("Link Clicks")),
                "otherClicks": to_int(row.get("Other Clicks")),
                "photoClicks": to_int(row.get("Matched Audience Targeting Consumption (Photo Click)")),
                "secondsViewed": to_num(row.get("Seconds viewed")),
                "averageSecondsViewed": to_num(row.get("Average Seconds viewed")),
                "threeSecondViews": None,
                "oneMinuteViews": None,
                "threeSecondViewers": None,
                "oneMinuteViewers": None,
                "duration": to_int(row.get("Duration (sec)")),
            },
            "isVideo": (row.get("Post type") or "").strip().lower() == "videos",
        })
    return posts


def read_videos(path):
    require(path)
    reader = csv.DictReader(io.StringIO(read_text(path)))
    videos = []
    for row in reader:
        if not row.get("Video asset ID"):
            continue
        videos.append({
            "id": row["Video asset ID"].strip(),
            "date": parse_date(row.get("Publish time")),
            "duration": to_int(row.get("Duration (sec)")),
            "reach": to_int(row.get("Reach")),
            "threeSecondViews": to_int(row.get("3-second video views")),
            "oneMinuteViews": to_int(row.get("1-minute video views")),
            "secondsViewed": to_num(row.get("Seconds viewed")),
            "averageSecondsViewed": to_num(row.get("Average Seconds viewed")),
            "threeSecondViewers": to_int(row.get("3-Second viewers")),
            "oneMinuteViewers": to_int(row.get("1-minute viewers")),
            "reactions": to_int(row.get("Reactions")),
            "comments": to_int(row.get("Comments")),
            "shares": to_int(row.get("Shares")),
            "interactions": to_int(row.get("Reactions, Comments and Shares")),
        })
    return videos


def engagement_rate(interactions, reach, views):
    if interactions is None or not reach or views is None:
        return None
    return round(interactions / reach * 100, 1)


def merge_videos(posts, videos):
    by_date = {}
    for post in posts:
        by_date[post["date"]] = post
    used = set()

    for video in videos:
        post = by_date.get(video["date"])
        if post is not None:
            metrics = post["metrics"]
            metrics["threeSecondViews"] = video["threeSecondViews"]
            metrics["oneMinuteViews"] = video["oneMinuteViews"]
            metrics["threeSecondViewers"] = video["threeSecondViewers"]
            metrics["oneMinuteViewers"] = video["oneMinuteViewers"]
            metrics["duration"] = post["metrics"]["duration"] or video["duration"]
            metrics["secondsViewed"] = metrics["secondsViewed"] or video["secondsViewed"]
            metrics["averageSecondsViewed"] = metrics["averageSecondsViewed"] or video["averageSecondsViewed"]
            post["isVideo"] = True
            used.add(video["date"])

    for video in videos:
        if video["date"] in used:
            continue
        interactions = video["interactions"]
        if interactions is None:
            interactions = (video["reactions"] or 0) + (video["comments"] or 0) + (video["shares"] or 0)
        posts.append({
            "id": f"video-{video['date']}",
            "date": video["date"],
            "type": "Video",
            "caption": "",
            "permalink": None,
            "image": None,
            "isVideo": True,
            "metrics": {
                "views": None,
                "reach": video["reach"],
                "interactions": interactions,
                "reactions": video["reactions"],
                "comments": video["comments"],
                "shares": video["shares"],
                "totalClicks": None,
                "linkClicks": None,
                "otherClicks": None,
                "photoClicks": None,
                "secondsViewed": video["secondsViewed"],
                "averageSecondsViewed": video["averageSecondsViewed"],
                "threeSecondViews": video["threeSecondViews"],
                "oneMinuteViews": video["oneMinuteViews"],
                "threeSecondViewers": video["threeSecondViewers"],
                "oneMinuteViewers": video["oneMinuteViewers"],
                "duration": video["duration"],
            },
        })
    return posts


def has_image_optimizer():
    if shutil.which("sips"):
        return True
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def image_for(date, extension):
    if (ASSETS / f"{date}.png").exists():
        return f"assets/posts/{date}{extension}"
    candidate = ASSETS / f"{date}{extension}"
    if candidate.exists():
        return f"assets/posts/{date}{extension}"
    return None


def build_payload():
    require(DATA / "page.json")
    page = json.loads(read_text(DATA / "page.json"))

    posts = merge_videos(read_posts(DATA / "posts.csv"), read_videos(DATA / "videos.csv"))
    posts.sort(key=lambda item: item["date"], reverse=True)

    extension = ".jpg" if has_image_optimizer() else ".png"
    for post in posts:
        post.setdefault("image", image_for(post["date"], extension))
        post["month"] = post["date"][:7]
        post["engagementRate"] = engagement_rate(
            post["metrics"]["interactions"],
            post["metrics"]["reach"],
            post["metrics"]["views"],
        )
        post["metrics"] = {key: value for key, value in post["metrics"].items()}

    series = {
        "views": read_results(DATA / "results-views.csv"),
        "viewers": read_results(DATA / "results-viewers.csv"),
        "visits": read_results(DATA / "results-visits.csv"),
        "follows": read_results(DATA / "results-follows.csv"),
    }

    dates = sorted({date for rows in series.values() for date, _ in rows})
    daily = []
    for date in dates:
        entry = {"date": date}
        for key, rows in series.items():
            entry[key] = next((value for day, value in rows if day == date), 0)
        daily.append(entry)

    monthly = []
    for month in MONTHS:
        entry = {"month": month["key"]}
        for key in series:
            entry[key] = sum(row[key] for row in daily if row["date"].startswith(month["key"]))
        monthly.append(entry)

    audience = read_audience(DATA / "audience.csv")

    return {
        "page": {
            "name": page.get("name", "Ferre Experto Pacasmayo"),
            "cutoff": page.get("cutoff", "2026-10-21"),
            "followers": page.get("followers", 0),
        },
        "months": MONTHS,
        "results": {"daily": daily, "monthly": monthly},
        "posts": posts,
        "audience": audience,
    }


def optimize_images():
    target = DIST / "assets" / "posts"
    target.mkdir(parents=True, exist_ok=True)
    sips = shutil.which("sips")
    try:
        from PIL import Image
    except ImportError:
        Image = None

    for source in sorted(ASSETS.glob("*.png")):
        destination = target / f"{source.stem}.jpg"
        if sips:
            result = subprocess.run(
                [sips, "-s", "format", "jpeg", "-s", "formatOptions", "80", str(source), "--out", str(destination)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                continue
        if Image is not None:
            with Image.open(source) as image:
                image = image.convert("RGB")
                if image.width > 640:
                    height = round(image.height * 640 / image.width)
                    image = image.resize((640, height), Image.LANCZOS)
                image.save(destination, "JPEG", quality=80, optimize=True, progressive=True)
            continue
        shutil.copy2(source, target / source.name)


def copy_static():
    DIST.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.js", "favicon.svg"):
        shutil.copy2(SRC / name, DIST / name)
    vendor_target = DIST / "vendor"
    vendor_target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC / "vendor" / "chart.umd.min.js", vendor_target / "chart.umd.min.js")


def main():
    payload = build_payload()
    if len(payload["posts"]) < 1:
        raise SystemExit("No se encontraron publicaciones para generar el dashboard.")
    copy_static()
    optimize_images()
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    totals = payload["results"]["monthly"]
    print(f"Publicaciones: {len(payload['posts'])}")
    for month in totals:
        print(f"{month['month']}: views={month['views']:.0f} viewers={month['viewers']:.0f} visits={month['visits']:.0f} follows={month['follows']:.0f}")
    print(f"Sitio generado en {DIST}")


if __name__ == "__main__":
    main()
