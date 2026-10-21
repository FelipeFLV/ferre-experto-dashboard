import http.server
import os
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "dist"
PORT = int(os.environ.get("PORT", "8000"))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        pass


def main():
    if not (ROOT / "index.html").exists():
        raise SystemExit("Primero ejecuta: python3 build.py")
    url = f"http://127.0.0.1:{PORT}/"
    print(f"Dashboard disponible en {url}")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


if __name__ == "__main__":
    main()
