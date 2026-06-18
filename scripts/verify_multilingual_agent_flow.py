import json
import time

import httpx


BASE_URL = "http://127.0.0.1:5000"


def contains_chinese(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def main() -> None:
    character_name = f"LocaleHero{int(time.time())}"
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        session = client.post(
            "/api/character-creation/sessions",
            json={"locale": "zh-CN"},
        ).json()
        draft = client.post(
            f"/api/character-creation/sessions/{session['id']}/messages",
            json={
                "content": (
                    f"My name is {character_name}, an Elf Ranger "
                    "with a Soldier background."
                ),
                "locale": "zh-CN",
            },
        ).json()
        confirmed = client.post(
            f"/api/character-creation/sessions/{session['id']}/messages",
            json={"content": "\u786e\u8ba4\u521b\u5efa", "locale": "zh-CN"},
        ).json()
        character = confirmed["created_character"]
        if character is None:
            raise AssertionError(
                f"Character was not created: draft={draft['draft']}, "
                f"errors={confirmed['validation_errors']}"
            )

        adventure = client.post(
            "/api/adventures",
            json={
                "title": "locale-flow",
                "character_id": character["id"],
                "locale": "zh-CN",
            },
        ).json()
        response = client.post(
            f"/api/adventures/{adventure['id']}/messages/stream",
            json={
                "content": "\u6211\u68c0\u67e5\u623f\u95f4\u91cc\u662f\u5426\u6709\u9690\u85cf\u7684\u95e8\u3002",
                "locale": "zh-CN",
            },
        )
        response.raise_for_status()
        events = [
            json.loads(line)
            for line in response.text.splitlines()
            if line.strip()
        ]
        narration = events[-1]["dm_message"]["content"]
        if not contains_chinese(narration):
            raise AssertionError(f"Expected Chinese narration, got: {narration}")

        english_response = client.post(
            f"/api/adventures/{adventure['id']}/messages/stream",
            json={
                "content": "I ask the mayor what happened at the tower.",
                "locale": "en",
            },
        )
        english_response.raise_for_status()
        english_events = [
            json.loads(line)
            for line in english_response.text.splitlines()
            if line.strip()
        ]
        english_narration = english_events[-1]["dm_message"]["content"]
        if contains_chinese(english_narration):
            raise AssertionError(
                f"Expected English narration after locale switch, got: {english_narration}"
            )

        print(
            {
                "session_locale": confirmed["locale"],
                "character": character["name"],
                "stream_status": response.status_code,
                "event_types": [event["type"] for event in events],
                "dm_has_chinese": True,
                "dm_text": narration[:160],
                "english_switch_status": english_response.status_code,
                "english_text": english_narration[:160],
            }
        )


if __name__ == "__main__":
    main()
