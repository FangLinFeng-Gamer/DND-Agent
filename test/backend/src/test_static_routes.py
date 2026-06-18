from pathlib import Path

from fastapi.testclient import TestClient

from backend.src.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_frontend_root_redirects_to_home_and_spa_routes_load(tmp_path):
    static_dir = PROJECT_ROOT / "frontend" / "static"
    app = create_app(db_path=tmp_path / "dnd-agent.sqlite3", static_dir=static_dir)

    with TestClient(app) as client:
      root = client.get("/", follow_redirects=False)
      assert root.status_code in {307, 308}
      assert root.headers["location"] == "/home"

      for path in ["/home", "/character-create", "/stories", "/game", "/game/42", "/models", "/races"]:
          response = client.get(path)
          assert response.status_code == 200
          assert "text/html" in response.headers["content-type"]
          assert 'id="home-view"' in response.text
