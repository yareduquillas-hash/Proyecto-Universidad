import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from backend.app import create_app
from backend.extensions import db
from backend.seed.seed import seed

HEADERS = {"Content-Type": "application/json"}

CREDS = {
    "admin": ("V-00000001", "admin123"),
    "profesor": ("V-12345678", "prof123"),
    "secretaria": ("V-23456789", "prof123"),
    "jurado": ("V-34567890", "jurado123"),
    "alumno": ("V-28765432", "alumno123"),
}


import tempfile
from backend.utils.rate_limit import clear_rate_limits

@pytest.fixture(autouse=True)
def _clear_rate_limits():
    clear_rate_limits()
    yield
    clear_rate_limits()

@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    upload_dir = tempfile.mkdtemp(prefix="uploads_partituras_")

    app = create_app(
        "testing",
        config_override={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": upload_dir,
        },
    )
    with app.app_context():
        db.session.remove()
        seed(app, drop=True)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, role):
    cedula, password = CREDS[role]
    res = client.post("/api/v1/auth/login", json={"cedula": cedula, "password": password})
    assert res.status_code == 200, res.get_data(as_text=True)
    return res.get_json()["access_token"]


def _auth(client, role):
    return {"Authorization": f"Bearer {_login(client, role)}"}


@pytest.fixture
def admin_h(client):
    return _auth(client, "admin")


@pytest.fixture
def prof_h(client):
    return _auth(client, "profesor")


@pytest.fixture
def alumno_h(client):
    return _auth(client, "alumno")


@pytest.fixture
def jurado_h(client):
    return _auth(client, "jurado")