import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import fetch_meta

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "posts"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
IMAGE_FIELD = "full_picture"
ATTACHMENT_FIELDS = "attachments{media{image{src}},subattachments{media{image{src}}}}"


def load_posts(archive_dir=None):
    directory = Path(archive_dir or fetch_meta.ARCHIVE)
    posts = {}
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data.get("posts") or {}
        if isinstance(rows, dict):
            rows = rows.values()
        for post in rows:
            if post.get("id") and post.get("date"):
                posts[post["id"]] = post
    return list(posts.values())


def existing_image(day, assets_dir=None):
    directory = Path(assets_dir or ASSETS)
    for suffix in IMAGE_SUFFIXES:
        candidate = directory / f"{day}{suffix}"
        if candidate.exists():
            return candidate
    return None


def post_image_url(payload):
    if payload.get("full_picture"):
        return payload["full_picture"]
    for attachment in (payload.get("attachments") or {}).get("data") or []:
        candidates = [attachment]
        candidates.extend((attachment.get("subattachments") or {}).get("data") or [])
        for candidate in candidates:
            media = candidate.get("media") or {}
            source = (media.get("image") or {}).get("src")
            if source:
                return source
    return None


def image_suffix(content_type):
    kind = str(content_type or "").split(";", 1)[0].strip().lower()
    if kind == "image/png":
        return ".png"
    return ".jpg"


def download_image(url, day, assets_dir=None, opener=None, timeout=30):
    directory = Path(assets_dir or ASSETS)
    opener = opener or urllib.request.urlopen
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/jpeg,image/png",
            "User-Agent": "ferre-experto-dashboard/1.0",
        },
    )
    with opener(request, timeout=timeout) as response:
        data = response.read()
        content_type = response.headers.get_content_type()
    if not data:
        raise ValueError("imagen vacía")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{day}{image_suffix(content_type)}"
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)
    return destination


def fetch_missing(api, posts, assets_dir=None, force=False, opener=None):
    downloaded = []
    skipped = []
    failed = []
    for post in posts:
        day = post.get("date")
        post_id = post.get("id")
        if not day or not post_id:
            continue
        current = existing_image(day, assets_dir)
        if current and not force:
            skipped.append(current)
            continue
        try:
            payload = api.get(post_id, {"fields": IMAGE_FIELD})
            url = post_image_url(payload)
            if not url:
                payload = api.get(post_id, {"fields": ATTACHMENT_FIELDS})
                url = post_image_url(payload)
        except fetch_meta.MetaAPIError as exc:
            print(f"Advertencia: no se pudo leer la imagen de {post_id}: {exc}", flush=True)
            failed.append(post_id)
            continue
        if not url:
            print(f"Advertencia: la publicación {post_id} no tiene imagen disponible.", flush=True)
            failed.append(post_id)
            continue
        try:
            path = download_image(url, day, assets_dir, opener)
            if force:
                for suffix in IMAGE_SUFFIXES:
                    candidate = Path(assets_dir or ASSETS) / f"{day}{suffix}"
                    if candidate != path:
                        candidate.unlink(missing_ok=True)
            downloaded.append(path)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            print(f"Advertencia: no se pudo descargar la imagen de {post_id}: {exc}", flush=True)
            failed.append(post_id)
    return downloaded, skipped, failed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Descarga las portadas de las publicaciones desde Meta Graph API."
    )
    parser.add_argument("--token", default=os.environ.get("META_PAGE_TOKEN"), help="Token de página. También META_PAGE_TOKEN.")
    parser.add_argument("--archive-dir", help="Directorio de archives. Por defecto data/archive.")
    parser.add_argument("--assets-dir", help="Directorio de imágenes. Por defecto assets/posts.")
    parser.add_argument("--force", action="store_true", help="Vuelve a descargar imágenes existentes.")
    args = parser.parse_args(argv)

    if not args.token:
        raise SystemExit("Falta META_PAGE_TOKEN.")

    posts = load_posts(args.archive_dir)
    downloaded, skipped, failed = fetch_missing(
        fetch_meta.GraphAPI(args.token),
        posts,
        args.assets_dir,
        args.force,
    )
    print(
        f"Publicaciones: {len(posts)} · descargadas: {len(downloaded)} · "
        f"omitidas: {len(skipped)} · fallidas: {len(failed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
