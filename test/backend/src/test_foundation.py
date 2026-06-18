import os
import subprocess
import sys

from fastapi.testclient import TestClient

from backend.src.core.settings import DEFAULT_DB_PATH
from backend.src.main import create_app


def test_importing_main_does_not_create_default_database(tmp_path):
    db_path = tmp_path / "import-check.sqlite3"

    subprocess.run(
        [sys.executable, "-c", "import backend.src.main"],
        check=True,
        cwd=DEFAULT_DB_PATH.parents[1],
        env={**os.environ, "DND_AGENT_DB_PATH": str(db_path)},
    )

    assert not db_path.exists()


def test_client_fixture_initializes_store_schema(client):
    store = client.app.state.store

    with store.connect() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("characters",),
        ).fetchone()

    assert row["name"] == "characters"


def test_api_recovers_schema_if_database_file_is_recreated(client):
    store = client.app.state.store
    store.db_path.unlink()

    response = client.get("/api/characters")

    assert response.status_code == 200
    assert response.json() == []


def test_first_start_creates_missing_database_directory_and_schema(tmp_path):
    db_path = tmp_path / "missing" / "nested" / "dnd_agent.sqlite3"
    app = create_app(db_path=db_path, static_dir=None)

    assert not db_path.parent.exists()

    with TestClient(app) as client:
        response = client.get("/api/characters")

    assert response.status_code == 200
    assert db_path.is_file()


def test_repository_ignores_local_database_and_environment_files():
    gitignore = (DEFAULT_DB_PATH.parents[1] / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "*.sqlite3" in gitignore
    assert "*.sqlite" in gitignore
    assert "*.db" in gitignore
    assert ".env" in gitignore
    assert ".env.*" in gitignore
