import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.src.db.sqlite import SQLiteStore
from backend.src.main import create_app
from backend.src.main import initialize_store


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        app = create_app(db_path=db_path, static_dir=None)
        with TestClient(app) as test_client:
            yield test_client


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        sqlite_store = SQLiteStore(db_path)
        initialize_store(sqlite_store)
        yield sqlite_store
