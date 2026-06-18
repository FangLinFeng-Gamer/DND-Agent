import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.src.main import create_app


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.sqlite3"
        app = create_app(db_path=db_path, static_dir=None)
        with TestClient(app) as test_client:
            yield test_client
