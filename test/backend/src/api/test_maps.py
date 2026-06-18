def test_upload_map_asset_stores_metadata_and_serves_file(client):
    response = client.post(
        "/api/map-assets?asset_type=map&name=Old%20Keep&filename=keep.png",
        content=b"fake-png",
        headers={"content-type": "image/png"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Old Keep"
    assert payload["asset_type"] == "map"
    assert payload["mime_type"] == "image/png"
    assert payload["size_bytes"] == len(b"fake-png")
    assert len(payload["sha256"]) == 64
    assert payload["file_url"] == f"/api/map-assets/{payload['id']}/file"

    file_response = client.get(payload["file_url"])

    assert file_response.status_code == 200
    assert file_response.content == b"fake-png"
    assert file_response.headers["content-type"].startswith("image/png")


def test_map_asset_upload_rejects_non_image_content(client):
    response = client.post(
        "/api/map-assets?asset_type=map&name=Notes&filename=notes.txt",
        content=b"not an image",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "unsupported_asset_mime_type"


def test_create_scene_with_background_and_activate_for_adventure(client):
    character = client.post(
        "/api/characters",
        json={"name": "Map Tester", "race": "Human", "class_name": "Fighter"},
    ).json()
    adventure = client.post(
        "/api/adventures",
        json={"title": "Mapped Ruins", "character_id": character["id"], "story_id": "mistbell_tower"},
    ).json()
    asset = client.post(
        "/api/map-assets?asset_type=map&name=Ruins&filename=ruins.png",
        content=b"map-bytes",
        headers={"content-type": "image/png"},
    ).json()

    scene_response = client.post(
        "/api/map-scenes",
        json={
            "name": "Ruined Hall",
            "adventure_id": adventure["id"],
            "background_asset_id": asset["id"],
            "grid_type": "square",
            "grid_size": 70,
            "scale": 5,
            "scale_unit": "ft",
            "background_color": "#1a1208",
        },
    )

    assert scene_response.status_code == 200
    scene = scene_response.json()
    assert scene["name"] == "Ruined Hall"
    assert scene["adventure_id"] == adventure["id"]
    assert scene["grid_size"] == 70
    assert scene["items"][0]["asset_id"] == asset["id"]
    assert scene["items"][0]["item_type"] == "background"
    assert scene["items"][0]["layer"] == "background"

    active_response = client.post(f"/api/map-scenes/{scene['id']}/activate")

    assert active_response.status_code == 200
    assert active_response.json()["active"] is True

    listed = client.get(f"/api/map-scenes?adventure_id={adventure['id']}").json()
    assert [entry["id"] for entry in listed] == [scene["id"]]
    assert listed[0]["active"] is True


def test_story_bound_scene_is_bound_to_new_adventure_on_start(client):
    character = client.post(
        "/api/characters",
        json={"name": "Story Map Tester", "race": "Human", "class_name": "Fighter"},
    ).json()
    story = client.post(
        "/api/stories",
        json={
            "title": "Mapped Story",
            "description": "Story with a prepared map.",
            "world_background": "A road through old woods.",
            "main_quest": "Reach the tower.",
            "opening_location": "Old Road",
            "opening_environment": "Wet stones and dense fog.",
            "opening_objective": "Find the missing scouts.",
        },
    ).json()
    asset = client.post(
        "/api/map-assets?asset_type=map&name=Story%20Road&filename=story-road.png",
        content=b"story-map",
        headers={"content-type": "image/png"},
    ).json()
    scene = client.post(
        "/api/map-scenes",
        json={
            "name": "Story Road Template",
            "story_id": story["id"],
            "background_asset_id": asset["id"],
            "grid_type": "square",
            "grid_size": 70,
            "scale": 5,
            "scale_unit": "ft",
        },
    ).json()

    story_scenes = client.get(f"/api/map-scenes?story_id={story['id']}").json()
    assert [entry["id"] for entry in story_scenes] == [scene["id"]]
    assert story_scenes[0]["adventure_id"] is None

    adventure = client.post(
        "/api/adventures",
        json={"title": "Mapped Story Run", "character_id": character["id"], "story_id": story["id"]},
    ).json()

    adventure_scenes = client.get(f"/api/map-scenes?adventure_id={adventure['id']}").json()
    assert len(adventure_scenes) == 1
    assert adventure_scenes[0]["id"] != scene["id"]
    assert adventure_scenes[0]["story_id"] == story["id"]
    assert adventure_scenes[0]["adventure_id"] == adventure["id"]
    assert adventure_scenes[0]["active"] is True
    assert adventure_scenes[0]["items"][0]["asset_id"] == asset["id"]

    story_scenes_after_start = client.get(f"/api/map-scenes?story_id={story['id']}").json()
    assert story_scenes_after_start[0]["id"] == scene["id"]
    assert story_scenes_after_start[0]["adventure_id"] is None


def test_scene_items_can_place_tokens_without_reuploading_assets(client):
    map_asset = client.post(
        "/api/map-assets?asset_type=map&name=Road&filename=road.jpg",
        content=b"jpg-map",
        headers={"content-type": "image/jpeg"},
    ).json()
    token_asset = client.post(
        "/api/map-assets?asset_type=token&name=Bandit&filename=bandit.webp",
        content=b"webp-token",
        headers={"content-type": "image/webp"},
    ).json()
    scene = client.post(
        "/api/map-scenes",
        json={"name": "Road Ambush", "background_asset_id": map_asset["id"]},
    ).json()

    item_response = client.post(
        f"/api/map-scenes/{scene['id']}/items",
        json={
            "asset_id": token_asset["id"],
            "item_type": "token",
            "layer": "token",
            "name": "Bandit",
            "x": 140,
            "y": 210,
            "width": 70,
            "height": 70,
            "rotation": 0,
            "locked": False,
            "visible": True,
        },
    )

    assert item_response.status_code == 200
    item = item_response.json()
    assert item["asset_id"] == token_asset["id"]
    assert item["x"] == 140
    assert item["y"] == 210

    full_scene = client.get(f"/api/map-scenes/{scene['id']}").json()
    assert [entry["item_type"] for entry in full_scene["items"]] == ["background", "token"]
