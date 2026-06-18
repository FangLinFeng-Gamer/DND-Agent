from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def frontend_js_text():
    files = [FRONTEND_DIR / "app.js", *sorted((FRONTEND_DIR / "js").rglob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_frontend_has_race_browser_and_character_creation_views():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="races-view"' in html
    assert 'id="race-list"' in html
    assert 'id="race-detail"' in html
    assert 'data-view-target="races"' in html
    assert 'id="character-create-view"' in html
    assert 'data-view-target="character-create"' in html


def test_character_creation_uses_wizard_instead_of_legacy_race_select():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    assert 'id="character-wizard"' in html
    assert '<select id="character-race"' not in html
    assert '<input id="character-race"' not in html
    assert 'id="character-form"' in html


def test_frontend_loads_races_from_world_api():
    app_js = frontend_js_text()

    assert "function loadRaces" in app_js
    assert '"/api/world/search?category=race"' in app_js
    assert "renderRaceList" in app_js
    assert "renderRaceOptions" in app_js


def test_frontend_renders_localized_race_metadata():
    app_js = frontend_js_text()

    assert "localizedRaceText" in app_js
    assert "localizeRaceMechanicLabel" in app_js
    assert "localizeRaceName" in app_js
    assert "localizeRaceTag" in app_js
    assert "race.metadata?.summary" in app_js
    assert "race.metadata?.traits" in app_js
    assert "race.metadata?.mechanics" in app_js
    assert "state.locale" in app_js
    assert "renderRaceMechanics" in app_js


def test_frontend_race_copy_is_available_in_both_languages():
    app_js = frontend_js_text()

    assert '"races": "Races"' in app_js
    assert '"characterCreation": "Character Creation"' in app_js
    assert '"races": "种族"' in app_js
    assert '"characterCreation": "创建角色"' in app_js
    assert '"raceMechanicAbilityScore": "Ability Score"' in app_js
    assert '"raceMechanicAbilityScore": "属性调整"' in app_js
    assert '"raceName.Human": "人类"' in app_js
    assert '"raceName.Tiefling": "提夫林"' in app_js
    assert '"raceTag.ancestry": "族裔"' in app_js
    assert '"raceTag.fire resistance": "火焰抗性"' in app_js
