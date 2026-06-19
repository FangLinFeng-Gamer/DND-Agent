from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_combat_panel_exposes_page_actions():
    html = (PROJECT_ROOT / "frontend/static/index.html").read_text(encoding="utf-8")
    app_js = (PROJECT_ROOT / "frontend/static/app.js").read_text(encoding="utf-8")
    game_js = (PROJECT_ROOT / "frontend/static/js/game.js").read_text(encoding="utf-8")
    state_js = (PROJECT_ROOT / "frontend/static/js/state.js").read_text(encoding="utf-8")
    styles = (PROJECT_ROOT / "frontend/static/styles.css").read_text(encoding="utf-8")
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
        "combat-trigger-note",
        "combat-result",
        "combat-log",
    ]:
        assert f'id="{element_id}"' in html

    for removed_markup in [
        'id="combat-form"',
        'id="start-combat"',
        'id="enemy-name"',
        'id="enemy-hp"',
        'id="enemy-ac"',
    ]:
        assert removed_markup not in html

    assert "performCombatAction" in game_js
    assert "loadCombatState" in game_js
    assert "resolveNpcTurns" in game_js
    assert "startCombat" not in app_js
    assert "startCombat" not in game_js
    assert "/combat/start" not in game_js
    assert "enemyName" not in state_js
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
        "combatTriggerNote",
        "combatLog",
        "combatLogEmpty",
        "combatLogAttackHit",
        "combatLogAttackMiss",
    ]:
        assert f'"{key}"' in i18n_js

    combat_log_block = styles.split(".combat-log {", 1)[1].split("}", 1)[0]
    assert "max-height:" in combat_log_block
    assert "overflow-y: auto" in combat_log_block
