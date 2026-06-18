from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_combat_panel_exposes_page_actions():
    html = (PROJECT_ROOT / "frontend/static/index.html").read_text(encoding="utf-8")
    game_js = (PROJECT_ROOT / "frontend/static/js/game.js").read_text(encoding="utf-8")
    i18n_js = (
        (PROJECT_ROOT / "frontend/static/js/locales/en.js").read_text(encoding="utf-8")
        + (PROJECT_ROOT / "frontend/static/js/locales/zh-CN.js").read_text(encoding="utf-8")
    )

    for element_id in [
        "combat-action-attack",
        "combat-action-dodge",
        "combat-action-dash",
        "combat-action-disengage",
        "end-combat",
        "combat-result",
    ]:
        assert f'id="{element_id}"' in html

    assert "performCombatAction" in game_js
    assert "loadCombatState" in game_js
    assert "resolveNpcTurns" in game_js
    assert "/combat/action" in game_js
    assert "/combat/npc-turn" in game_js
    assert "/combat/end" in game_js
    assert "/combat`" in game_js
    assert "isPlayerCombatTurn" in game_js
    assert "canCombatantAct" in game_js
    assert "combatActorCannotAct" in game_js

    for key in [
        "combatActionAttack",
        "combatActionDodge",
        "combatActionDash",
        "combatActionDisengage",
        "combatNpcThinking",
        "combatNpcResolved",
        "combatPlayerTurnOnly",
        "combatActorCannotAct",
        "currentCombatant",
        "combatPairing",
    ]:
        assert f'"{key}"' in i18n_js
