import httpx


def main() -> None:
    base_url = "http://127.0.0.1:5000"
    with httpx.Client(base_url=base_url, timeout=30) as client:
        session = client.post(
            "/api/character-creation/sessions",
            json={"locale": "zh-CN"},
        ).json()
        race = client.patch(
            f"/api/character-creation/sessions/{session['id']}/draft",
            json={
                "expected_revision": session["revision"],
                "operation": "race",
                "payload": {
                    "race_id": "race.dwarf",
                    "subrace_id": "race.mountain-dwarf",
                    "choice_values": {},
                },
                "locale": "zh-CN",
            },
        ).json()
        abilities = client.patch(
            f"/api/character-creation/sessions/{session['id']}/draft",
            json={
                "expected_revision": race["revision"],
                "operation": "abilities",
                "payload": {
                    "base": {
                        "strength": 15,
                        "dexterity": 12,
                        "constitution": 14,
                        "intelligence": 8,
                        "wisdom": 10,
                        "charisma": 10,
                    }
                },
                "locale": "zh-CN",
            },
        ).json()
        draft = abilities["draft"]
        assert abilities["revision"] == 2
        assert draft["abilities"]["point_buy_spent"] == 24
        assert draft["abilities"]["final"]["strength"] == 17
        assert draft["abilities"]["final"]["constitution"] == 16
        print(
            {
                "session_id": abilities["id"],
                "revision": abilities["revision"],
                "current_step": draft["current_step"],
                "point_buy_spent": draft["abilities"]["point_buy_spent"],
                "strength": draft["abilities"]["final"]["strength"],
                "constitution": draft["abilities"]["final"]["constitution"],
            }
        )


if __name__ == "__main__":
    main()
