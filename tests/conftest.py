import os
import tempfile

import pytest

from app import create_app
from app.db import init_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    upload_dir = tempfile.mkdtemp()

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": db_path,
            "UPLOAD_FOLDER": upload_dir,
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        init_db()

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()
