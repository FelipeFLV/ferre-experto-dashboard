import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import fetch_meta

ROOT = Path(__file__).resolve().parent
POST_HISTORY = ROOT / "data" / "post-history"


def first_archive_date():
    months = sorted(path.stem for path in fetch_meta.ARCHIVE.glob("*.json"))
    if not months:
        return date(date.today().year, 1, 1)
    return date.fromisoformat(f"{months[0]}-01")


def save_snapshot(payload, path):
    path = Path(path)
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = None
        if current is not None:
            before = {key: value for key, value in current.items() if key != "fetched_at"}
            after = {key: value for key, value in payload.items() if key != "fetched_at"}
            if before == after:
                return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Guarda un snapshot diario de las métricas lifetime de cada publicación."
    )
    parser.add_argument("--page-id", default=os.environ.get("META_PAGE_ID"), help="ID de la página. También META_PAGE_ID.")
    parser.add_argument("--token", default=os.environ.get("META_PAGE_TOKEN"), help="Token de página. También META_PAGE_TOKEN.")
    parser.add_argument("--date", help="Fecha del snapshot en YYYY-MM-DD. Por defecto hoy en Perú.")
    parser.add_argument("--output", help="Ruta del snapshot. Por defecto data/post-history/YYYY-MM-DD.json.")
    args = parser.parse_args(argv)

    if not args.token:
        raise SystemExit("Falta META_PAGE_TOKEN.")
    if not args.page_id:
        raise SystemExit("Falta META_PAGE_ID.")

    now = datetime.now(fetch_meta.TZ)
    today = now.date()
    target = date.fromisoformat(args.date) if args.date else today
    if target > today or target < today - timedelta(days=1):
        raise SystemExit("El snapshot solo puede ser de hoy o de ayer.")
    if target == today - timedelta(days=1) and now.hour >= 6:
        raise SystemExit("Un snapshot de ayer debe capturarse antes de las 06:00.")
    first = first_archive_date()
    api = fetch_meta.GraphAPI(args.token)
    posts = fetch_meta.fetch_posts(api, args.page_id, first, target)
    payload = {
        "date": target.isoformat(),
        "partial": target == today and now.hour < 23,
        "fetched_at": datetime.now(fetch_meta.TZ).isoformat(timespec="seconds"),
        "posts": {post["id"]: post["metrics"] for post in posts},
    }

    output = Path(args.output) if args.output else POST_HISTORY / f"{target.isoformat()}.json"
    written = save_snapshot(payload, output)
    print(f"Publicaciones: {len(payload['posts'])}")
    print(f"Snapshot: {output}")
    if not written:
        print("Sin cambios reales; se conserva el snapshot existente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
