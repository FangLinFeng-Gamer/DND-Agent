from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def read_frontend_file(name):
    return (FRONTEND_DIR / name).read_text(encoding="utf-8")


def i18n_resource_text():
    return read_frontend_file("js/locales/en.js") + read_frontend_file("js/locales/zh-CN.js")


def css_block(css, selector):
    start = css.index(selector)
    open_brace = css.index("{", start)
    depth = 0
    for index in range(open_brace, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[open_brace + 1:index]
    raise AssertionError(f"CSS block not closed for {selector}")


def test_homepage_prioritizes_starting_a_game_over_character_creation():
    html = read_frontend_file("index.html")

    assert 'class="home-hero"' in html
    assert 'class="home-bento"' in html
    assert 'class="topbar floating-nav"' in html
    assert 'class="nav-primary"' in html
    assert 'data-view-target="game" data-i18n="homePrimaryCta"' in html
    assert 'data-home-card="start-game"' in html
    assert 'data-home-card="create-hero"' in html
    assert html.index('data-home-card="start-game"') < html.index('data-home-card="create-hero"')
    assert 'data-i18n="homeStartGameTitle"' in html
    assert 'data-i18n="homeCreateHeroTitle"' in html
    assert 'data-i18n="homeCreateHeroBody"' in html


def test_topbar_uses_clean_reference_nav_without_capabilities_copy():
    html = read_frontend_file("index.html")
    css = read_frontend_file("styles.css")
    topbar_block = css_block(css, ".topbar")
    status_block = css_block(css, ".status")

    assert 'id="capabilities"' not in html
    assert html.index('class="brand"') < html.index('class="view-nav"')
    assert html.index('class="view-nav"') < html.index('class="topbar-actions"')
    assert "position: fixed" in topbar_block
    assert "grid-template-columns: auto minmax(0, 1fr) auto" in topbar_block
    assert "height: 64px" in topbar_block
    assert "clip-path: inset(50%)" in status_block


def test_homepage_adds_dnd_visual_elements_without_svg_or_partial_hero_crop():
    html = read_frontend_file("index.html")
    css = read_frontend_file("styles.css")
    hero_board = css_block(css, ".home-hero-board")

    assert 'class="home-dnd-cluster"' in html
    assert 'class="home-die-card"' in html
    assert 'class="home-character-sheet"' in html
    assert 'class="home-campaign-map"' in html
    assert 'class="home-dice-strip"' in html
    assert 'data-i18n="homeCharacterSheetLabel"' in html
    assert 'data-i18n="homeCampaignMapLabel"' in html
    for die in ("d4", "d6", "d8", "d10", "d12", "d20"):
        assert f"<span>{die}</span>" in html

    assert "clip-path" not in hero_board
    assert "linear-gradient" not in hero_board
    assert "radial-gradient" not in hero_board


def test_homepage_cards_use_parchment_bento_layout():
    css = read_frontend_file("styles.css")
    chinese_title_block = css_block(css, ":lang(zh-CN) .home-card > strong")

    assert ".home-bento" in css
    assert ".home-card" in css
    assert ".home-card.main" in css
    assert ".topbar.floating-nav" in css
    assert ":lang(zh-CN) .home-card > strong" in css
    assert "line-height: 1.24" in chinese_title_block
    assert "padding: 3px 0 4px" in chinese_title_block
    assert "var(--parchment-hi)" in css
    assert "var(--parchment-lo)" in css
    assert "repeating-linear-gradient" in css


def test_homepage_card_tags_are_localized_instead_of_hardcoded_english():
    html = read_frontend_file("index.html")
    i18n = i18n_resource_text()

    for key in (
        "homeTagStory",
        "homeTagCharacter",
        "homeTagSession",
        "homeTagAttributes",
        "homeTagClass",
        "homeTagBackground",
        "homeTagScene",
        "homeTagNpc",
        "homeTagRulings",
        "homeTagSpells",
        "homeTagItems",
        "homeTagRaces",
    ):
        assert f'data-i18n="{key}"' in html
        assert f'"{key}"' in i18n

    for hardcoded in ("<span>Story</span>", "<span>Character</span>", "<span>Rolls</span>"):
        assert hardcoded not in html


def test_homepage_start_game_and_dm_cards_have_distinct_copy():
    i18n = i18n_resource_text()

    assert '"homeStartGameBody": "Choose a story, choose a hero, and open a playable session."' in i18n
    assert '"homeDmBody": "Review narration, NPCs, rulings, and dice outcomes once the session is underway."' in i18n
    assert '"homeStartGameBody": "选择剧本与角色，开启一局可游玩的冒险。"' in i18n
    assert '"homeDmBody": "游戏开始后查看叙事、NPC、裁决与骰子结果。"' in i18n


def test_homepage_story_card_is_entry_only_without_default_story_preview():
    html = read_frontend_file("index.html")
    stories = read_frontend_file("js/stories.js")

    assert 'id="home-story-summary"' not in html
    assert 'class="story-summary home-story-summary"' not in html
    assert "renderHomeStorySummary()" in stories


def test_default_story_text_can_be_localized_for_story_views():
    i18n = i18n_resource_text()
    stories = read_frontend_file("js/stories.js")

    assert '"defaultStoryTitle.mistbell_tower": "The Stolen Silver Bell of Moonwell Festival"' in i18n
    assert '"defaultStoryTitle.mistbell_tower": "月井节的失窃银铃"' in i18n
    assert '"defaultStoryDescription.mistbell_tower"' in i18n
    assert '"defaultStoryBackground.mistbell_tower"' in i18n
    assert '"defaultStoryQuest.mistbell_tower"' in i18n
    assert "localizedStoryText" in stories
    assert "defaultStoryTitle.${story.id}" in stories


def test_story_library_cards_can_shrink_inside_narrow_create_view():
    css = read_frontend_file("styles.css")
    story_list_block = css_block(css, ".story-list")
    list_item_block = css_block(css, ".list-item")
    summary_block = css_block(css, ".model-summary,\n.item-summary")

    assert "grid-template-columns: minmax(0, 1fr)" in story_list_block
    assert "min-width: 0" in list_item_block
    assert "min-width: 0" in summary_block


def test_homepage_new_copy_is_available_in_english_and_chinese():
    i18n = i18n_resource_text()

    assert '"homePrimaryCta": "Start Game"' in i18n
    assert '"homeSubtitle": "Choose a story, bring a hero, and start a living tabletop session."' in i18n
    assert '"homeStartGameTitle": "Start Game"' in i18n
    assert '"homeCreateHeroBody": "Prepare a legal DND character before entering the game."' in i18n
    assert '"homePrimaryCta": "开始游戏"' in i18n
    assert '"homeSubtitle": "选择剧本，带上角色，开始一局会被 DM 记住的桌面冒险。"' in i18n
    assert '"homeStartGameTitle": "开始游戏"' in i18n
    assert '"homeCreateHeroBody": "在进入游戏前准备一名符合规则的 DND 角色。"' in i18n
