"""Entry point for the standalone Windows build: starts the app on a local
production server (waitress) and opens it in the default browser tab.
Packaged into a single-folder executable via PyInstaller -- see
desktop_app.spec and packaging/stage_tesseract.py for the build.

Not used for local development -- use `flask --app wsgi run --debug` (or
just `python wsgi.py`) for that instead, which runs Flask's own dev server
without touching the bundled-Tesseract/browser-launch logic below.
"""
import os
import socket
import sys
import threading
import webbrowser


def _resource_dir() -> str:
    """Where bundled read-only resources (the Tesseract build, etc.) live --
    the PyInstaller extraction directory when frozen, otherwise this file's
    own directory."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.dirname(__file__))


def _configure_tesseract() -> None:
    """Point pytesseract at the Tesseract binary bundled alongside this
    build (see packaging/stage_tesseract.py), if present -- a no-op when
    running from source, where TESSERACT_CMD (if needed) is set the normal
    way via the environment or PATH."""
    tesseract_dir = os.path.join(_resource_dir(), "tesseract")
    tesseract_exe = os.path.join(tesseract_dir, "tesseract.exe")
    if os.path.isfile(tesseract_exe):
        os.environ.setdefault("TESSERACT_CMD", tesseract_exe)
        os.environ.setdefault("TESSDATA_PREFIX", os.path.join(tesseract_dir, "tessdata"))


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    _configure_tesseract()

    # Imported after _configure_tesseract() so TESSERACT_CMD/TESSDATA_PREFIX
    # are already set before anything that might touch OCR is loaded.
    from app import create_app
    from app.db import init_db

    app = create_app()
    with app.app_context():
        if not os.path.exists(app.config["DATABASE"]):
            init_db()

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}/"

    # Open the browser shortly after the server starts listening, rather
    # than blocking on it here.
    threading.Timer(1.0, webbrowser.open, args=(url,)).start()

    print("Alcohol Label Verification")
    print(f"Running at {url}")
    print("Close this window to stop the app.")

    from waitress import serve

    serve(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
