import argparse
import getpass
import json
import os
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_VERSION = "v26.0"
BASE = f"https://graph.facebook.com/{API_VERSION}"
DEFAULT_PAGE_NAME = "Ferre Experto Pacasmayo"


class TokenError(Exception):
    pass


def request_json(url, data=None, token=None, opener=None, secrets=()):
    headers = {
        "Accept": "application/json",
        "User-Agent": "ferre-experto-dashboard/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = urllib.parse.urlencode(data).encode("utf-8") if data else None
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with (opener or urllib.request.urlopen)(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            message = json.loads(raw).get("error", {}).get("message", f"HTTP {exc.code}")
        except ValueError:
            message = f"HTTP {exc.code}"
        for secret in secrets:
            if secret:
                message = message.replace(secret, "[redacted]")
        raise TokenError(message) from None
    except urllib.error.URLError as exc:
        raise TokenError(f"No se pudo conectar con Meta: {exc.reason}") from None


def exchange_user_token(app_id, app_secret, short_token, opener=None):
    payload = request_json(
        f"{BASE}/oauth/access_token",
        data={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        opener=opener,
        secrets=(app_secret, short_token),
    )
    token = payload.get("access_token")
    if not token:
        raise TokenError("Meta no devolvió un token de larga duración.")
    return token


def list_pages(user_token, opener=None):
    url = f"{BASE}/me/accounts?fields=id,name,access_token&limit=100"
    pages = []
    seen = set()
    while url and url not in seen:
        seen.add(url)
        payload = request_json(url, token=user_token, opener=opener, secrets=(user_token,))
        pages.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
    return pages


def select_page(pages, name):
    wanted = name.strip().casefold()
    exact = [page for page in pages if str(page.get("name", "")).strip().casefold() == wanted]
    if len(exact) == 1:
        return exact[0]
    partial = [page for page in pages if wanted in str(page.get("name", "")).strip().casefold()]
    if len(partial) == 1:
        return partial[0]
    available = ", ".join(str(page.get("name", "sin nombre")) for page in pages) or "ninguna"
    if not exact and not partial:
        raise TokenError(f"No se encontró la página {name!r}. Páginas disponibles: {available}")
    raise TokenError(f"Hay varias páginas que coinciden con {name!r}: {available}. Usa --page-name exacto.")


def debug_token(page_token, app_id, app_secret, opener=None):
    app_token = f"{app_id}|{app_secret}"
    url = f"{BASE}/debug_token?input_token={urllib.parse.quote(page_token, safe='')}"
    payload = request_json(
        url,
        token=app_token,
        opener=opener,
        secrets=(app_secret, app_token, page_token),
    )
    return payload.get("data", {})


def validate_page_token(page_id, page_token, opener=None):
    payload = request_json(
        f"{BASE}/{page_id}?fields=id,name",
        token=page_token,
        opener=opener,
        secrets=(page_token,),
    )
    if str(payload.get("id", "")) != str(page_id):
        raise TokenError("Meta no confirmó el acceso a la página con el token generado.")
    return payload


def write_env(path, page_id, page_token):
    path = Path(path)
    text = (
        f"META_PAGE_ID={shlex.quote(str(page_id))}\n"
        f"META_PAGE_TOKEN={shlex.quote(page_token)}\n"
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Convierte un token de usuario en un token de página de larga duración."
    )
    parser.add_argument("--app-id", default=os.environ.get("META_APP_ID"))
    parser.add_argument("--app-secret", default=os.environ.get("META_APP_SECRET"))
    parser.add_argument("--short-token", default=os.environ.get("META_SHORT_TOKEN"))
    parser.add_argument("--page-name", default=DEFAULT_PAGE_NAME)
    parser.add_argument("--output", default=".env")
    parser.add_argument("--force", action="store_true", help="Sobrescribe el archivo de salida.")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists() and not args.force:
        raise SystemExit(f"{output} ya existe. Usa --force para sobrescribirlo.")

    app_id = args.app_id or input("App ID: ").strip()
    app_secret = args.app_secret or getpass.getpass("App Secret (no se muestra): ").strip()
    short_token = args.short_token or getpass.getpass(
        "Token de usuario de corta duración (no se muestra): "
    ).strip()

    if not app_id or not app_secret or not short_token:
        raise SystemExit("Faltan App ID, App Secret o token de usuario.")

    try:
        long_user_token = exchange_user_token(app_id, app_secret, short_token)
        pages = list_pages(long_user_token)
        page = select_page(pages, args.page_name)
        page_id = str(page.get("id", "")).strip()
        page_token = str(page.get("access_token", "")).strip()
        if not page_id or not page_token:
            raise TokenError(
                "La página apareció, pero Meta no devolvió su Page Access Token. "
                "Verifica que la cuenta sea administradora de la página y tenga pages_show_list."
            )
        validate_page_token(page_id, page_token)
        try:
            info = debug_token(page_token, app_id, app_secret)
        except TokenError as exc:
            info = {}
            print(f"Aviso: no se pudo verificar la expiración del token: {exc}", file=sys.stderr)
    except TokenError as exc:
        raise SystemExit(f"Error: {exc}") from None

    if not info.get("is_valid", True):
        raise SystemExit(f"Meta marcó el token como inválido: {info.get('error') or 'sin detalle'}")

    write_env(output, page_id, page_token)

    expires_at = info.get("expires_at")
    if expires_at == 0:
        expiry = "nunca"
    elif expires_at:
        expiry = f"timestamp {expires_at}"
    else:
        expiry = "desconocido"
    scopes = ", ".join(info.get("scopes", [])) or "no informados"

    print(f"Página: {page.get('name')} ({page_id})")
    print(f"Token guardado en {output} (no se imprime).")
    print(f"Expira: {expiry}")
    print(f"Permisos: {scopes}")
    print()
    print("Siguiente paso:")
    print(f"  set -a; source {output}; set +a")
    print("  python3 fetch_meta.py --probe --month 2026-10")
    print("  printf '%s' \"$META_PAGE_TOKEN\" | gh secret set META_PAGE_TOKEN")
    print("  printf '%s' \"$META_PAGE_ID\" | gh secret set META_PAGE_ID")
    print(f"  rm {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
