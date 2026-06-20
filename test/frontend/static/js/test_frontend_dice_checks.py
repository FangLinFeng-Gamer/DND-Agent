from pathlib import Path


FRONTEND_DIR = Path(__file__).resolve().parents[4] / "frontend" / "static"


def read_frontend_file(name):
    return (FRONTEND_DIR / name).read_text(encoding="utf-8")


def test_dice_module_exposes_promise_roll_api_for_checks():
    dice = read_frontend_file("js/dice.js")

    assert "export function rollDie" in dice
    assert "return new Promise" in dice
    assert "export function rollD20ForCheck" in dice


def test_game_renders_pending_check_and_resolves_through_dice_tray():
    api = read_frontend_file("js/api.js")
    game = read_frontend_file("js/game.js")

    assert "export async function resolvePendingCheck" in api
    assert "renderPendingCheck" in game
    assert "rollD20ForCheck" in game
    assert "resolvePendingCheck" in game
    assert "pending_check" in game


def test_check_labels_are_localized():
    zh = read_frontend_file("js/locales/zh-CN.js")
    en = read_frontend_file("js/locales/en.js")

    assert '"rollCheck": "掷 d20"' in zh
    assert '"rollCheck": "Roll d20"' in en
    assert '"pendingCheckTitle": "能力检定"' in zh
    assert '"pendingCheckTitle": "Ability Check"' in en
