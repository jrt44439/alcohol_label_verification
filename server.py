"""Production entry point for container/server deployments (Docker,
Fly.io, Render, ...). Initializes the database on first run, then serves
the app via waitress, bound to all interfaces so it's reachable from
outside the container.

This is distinct from desktop_app.py (the standalone Windows build's entry
point, which binds to localhost only and opens a browser) and wsgi.py
(used by `flask run` for local development).
"""
import os

from app import create_app
from app.db import init_db

app = create_app()

with app.app_context():
    if not os.path.exists(app.config["DATABASE"]):
        init_db()


def main() -> None:
    from waitress import serve

    port = int(os.environ.get("PORT", "8080"))
    serve(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
