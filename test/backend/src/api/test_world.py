def test_world_search_returns_seeded_entries(client):
    response = client.get("/api/world/search", params={"query": "initiative"})
    assert response.status_code == 200
    data = response.json()
    assert data["results"]
    assert any("initiative" in item["content"].lower() for item in data["results"])


def test_world_search_category_filter(client):
    response = client.get("/api/world/search", params={"category": "class", "query": "fighter"})
    assert response.status_code == 200
    names = [item["name"].lower() for item in response.json()["results"]]
    assert "fighter" in names


def test_world_search_returns_phb_base_races(client):
    response = client.get("/api/world/search", params={"category": "race"})

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["results"]}
    assert {
        "Human",
        "Elf",
        "Dwarf",
        "Halfling",
        "Dragonborn",
        "Gnome",
        "Half-Elf",
        "Half-Orc",
        "Tiefling",
    }.issubset(names)


def test_base_races_include_bilingual_details_and_mechanics(client):
    response = client.get("/api/world/search", params={"category": "race"})

    assert response.status_code == 200
    for race in response.json()["results"]:
        metadata = race["metadata"]
        assert len(metadata["summary"]["en"]) >= 160, race["name"]
        assert len(metadata["summary"]["zh"]) >= 60, race["name"]
        assert len(metadata["traits"]["en"]) >= 160, race["name"]
        assert len(metadata["traits"]["zh"]) >= 60, race["name"]
        mechanics = metadata["mechanics"]
        assert mechanics["ability_score"], race["name"]
        assert mechanics["size"], race["name"]
        assert mechanics["speed"], race["name"]
        assert mechanics["languages"], race["name"]
        assert mechanics["features"], race["name"]
