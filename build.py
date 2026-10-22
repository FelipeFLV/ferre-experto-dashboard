import json
import shutil
import subprocess
from calendar import monthrange
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ARCHIVE = DATA / "archive"
SRC = ROOT / "src"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets" / "posts"

SERIES_KEYS = ("views", "viewers", "visits", "follows")
METRIC_KEYS = (
    "views",
    "viewers",
    "reach",
    "interactions",
    "reactions",
    "comments",
    "shares",
    "totalClicks",
    "linkClicks",
    "otherClicks",
    "photoClicks",
    "secondsViewed",
    "averageSecondsViewed",
    "threeSecondViews",
    "oneMinuteViews",
    "threeSecondViewers",
    "oneMinuteViewers",
    "duration",
)
MONTH_NAMES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)
MONTH_SHORT = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def read_text(path):
    raw = Path(path).read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig")
    return raw.decode("utf-8")


def to_int(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def month_bounds(month):
    try:
        year, month_number = [int(part) for part in month.split("-")]
        first = date(year, month_number, 1)
    except (TypeError, ValueError):
        raise SystemExit(f"Mes inválido en el archivo: {month!r}")
    last = date(year, month_number, monthrange(year, month_number)[1])
    return first, last


def month_meta(month):
    year, month_number = [int(part) for part in month.split("-")]
    return {
        "key": month,
        "label": f"{MONTH_NAMES[month_number - 1]} {year}",
        "short": MONTH_SHORT[month_number - 1],
    }


def load_archives(archive_dir=None):
    archive_dir = Path(archive_dir or ARCHIVE)
    files = sorted(archive_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"No hay archivos de Meta en {archive_dir}")
    archives = []
    for path in files:
        try:
            payload = json.loads(read_text(path))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"JSON inválido en {path}: {exc}") from None
        month = payload.get("month") or path.stem
        if month != path.stem:
            raise SystemExit(f"El mes de {path.name} no coincide con su nombre: {month!r}")
        if not payload.get("daily"):
            raise SystemExit(f"El archivo {path.name} no tiene serie diaria")
        payload["month"] = month
        archives.append(payload)
    archives.sort(key=lambda item: item["month"])
    return archives


def archive_cutoff(archive):
    first, last = month_bounds(archive["month"])
    fetched = str(archive.get("fetched_at") or "")[:10]
    try:
        fetched_date = date.fromisoformat(fetched)
    except ValueError:
        fetched_date = None
    if fetched_date is not None and first <= fetched_date < last:
        return fetched_date.isoformat()
    return last.isoformat()


def engagement_rate(interactions, reach, views):
    if interactions is None:
        return None
    denominator = reach or views
    if not denominator:
        return None
    return round(interactions / denominator * 100, 1)


def has_image_optimizer():
    if shutil.which("sips"):
        return True
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def image_for(day, extension):
    if not day:
        return None
    if (ASSETS / f"{day}.png").exists():
        return f"assets/posts/{day}{extension}"
    candidate = ASSETS / f"{day}{extension}"
    if candidate.exists():
        return f"assets/posts/{candidate.name}"
    return None


def build_audience(archives):
    target = {"ageGender": [], "cities": [], "countries": []}
    for archive in reversed(archives):
        raw = archive.get("audience") or {}
        candidate = {
            "ageGender": raw.get("ageGender") or [],
            "cities": raw.get("cities") or [],
            "countries": raw.get("countries") or [],
        }
        if any(candidate.values()):
            return candidate
    return target


def build_payload(archive_dir=None):
    archives = load_archives(archive_dir)
    latest = archives[-1]
    cutoff = archive_cutoff(latest)

    months = []
    for archive in archives:
        meta = month_meta(archive["month"])
        _, last = month_bounds(archive["month"])
        meta["partial"] = meta["key"] == cutoff[:7] and cutoff < last.isoformat()
        months.append(meta)

    by_date = {}
    for archive in archives:
        for row in archive.get("daily", []):
            day = row.get("date")
            if not day or day > cutoff:
                continue
            by_date[day] = {key: to_int(row.get(key)) or 0 for key in SERIES_KEYS}
    daily = [{"date": day, **by_date[day]} for day in sorted(by_date)]

    monthly = []
    for meta in months:
        rows = [row for row in daily if row["date"].startswith(meta["key"])]
        entry = {"month": meta["key"]}
        for key in SERIES_KEYS:
            entry[key] = sum(row[key] for row in rows)
        monthly.append(entry)

    extension = ".jpg" if has_image_optimizer() else ".png"
    posts_by_id = {}
    for archive in archives:
        for post in archive.get("posts", []):
            post_id = post.get("id")
            if post_id:
                posts_by_id[post_id] = post

    posts = []
    for raw in posts_by_id.values():
        post = dict(raw)
        post["month"] = str(post.get("date") or "")[:7]
        metrics = dict(post.get("metrics") or {})
        for key in METRIC_KEYS:
            metrics.setdefault(key, None)
        post["metrics"] = metrics
        if not post.get("image"):
            post["image"] = image_for(post.get("date"), extension)
        post["engagementRate"] = engagement_rate(
            metrics["interactions"], metrics["reach"], metrics["views"]
        )
        posts.append(post)
    posts.sort(key=lambda item: item["date"], reverse=True)

    page = latest.get("page") or {}
    return {
        "page": {
            "name": page.get("name", "Ferre Experto Pacasmayo"),
            "cutoff": cutoff,
            "updatedAt": latest.get("fetched_at"),
            "followers": to_int(page.get("followers")) or 0,
        },
        "months": months,
        "results": {"daily": daily, "monthly": monthly},
        "posts": posts,
        "audience": build_audience(archives),
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
    if not payload["posts"]:
        raise SystemExit("No se encontraron publicaciones para generar el dashboard.")
    copy_static()
    optimize_images()
    (DIST / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Publicaciones: {len(payload['posts'])}")
    for month in payload["results"]["monthly"]:
        print(
            f"{month['month']}: views={month['views']:.0f} viewers={month['viewers']:.0f} "
            f"visits={month['visits']:.0f} follows={month['follows']:.0f}"
        )
    print(f"Sitio generado en {DIST}")


if __name__ == "__main__":
    main()
