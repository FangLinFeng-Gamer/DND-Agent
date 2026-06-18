import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.src.main import create_app


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(db_path=Path(tmpdir) / "flow.sqlite3", static_dir=None)
        with TestClient(app) as client:
            session = client.post(
                "/api/character-creation/sessions",
                json={"locale": "en"},
            ).json()
            draft = client.post(
                f"/api/character-creation/sessions/{session['id']}/messages",
                json={"content": "My name is Lyra, an Elf Ranger with a Soldier background."},
            ).json()
            confirmed = client.post(
                f"/api/character-creation/sessions/{session['id']}/messages",
                json={"content": "confirm"},
            ).json()
            character = confirmed["created_character"]
            adventure = client.post(
                "/api/adventures",
                json={"title": "LangGraph Trial", "character_id": character["id"]},
            ).json()
            response = client.post(
                f"/api/adventures/{adventure['id']}/messages/stream",
                json={"content": "I inspect the old gate for traps."},
            )
            events = [json.loads(line) for line in response.text.splitlines() if line.strip()]

            print("draft", draft["draft"])
            print("character", character["name"], character["race"], character["class_name"])
            print("adventure", adventure["id"], adventure["story_id"])
            print("stream_status", response.status_code)
            print("event_types", [event["type"] for event in events])
            print("final_scene", events[-1]["scene"]["location"])


if __name__ == "__main__":
    main()
