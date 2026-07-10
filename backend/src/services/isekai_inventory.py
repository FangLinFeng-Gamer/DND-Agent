from __future__ import annotations

import re


def normalize_waterskins(inventory: list[str]) -> list[str]:
    result: list[str] = []
    first_index: int | None = None
    total_current = 0
    total_maximum = 0

    for item in inventory:
        text = str(item or "").strip()
        if "水囊" not in text:
            result.append(text)
            continue
        if first_index is None:
            first_index = len(result)
        current, maximum = waterskin_charges(text)
        total_current += current
        total_maximum += maximum

    if first_index is None:
        return result

    result.insert(first_index, format_waterskin(total_current, total_maximum))
    return result


def consume_waterskin_charge(inventory: list[str]) -> tuple[list[str], str]:
    result = normalize_waterskins(inventory)
    for index, item in enumerate(result):
        if "水囊" not in item:
            continue
        current, maximum = waterskin_charges(item)
        if current <= 0:
            return result, "水囊已经空了"
        result[index] = format_waterskin(current - 1, maximum)
        return result, "饮用水囊 1 份"
    return result, "没有可用饮水"


def refill_waterskins(inventory: list[str]) -> tuple[list[str], str]:
    result = normalize_waterskins(inventory)
    for index, item in enumerate(result):
        if "水囊" not in item:
            continue
        current, maximum = waterskin_charges(item)
        if current >= maximum:
            return result, "水囊已经是满的"
        result[index] = format_waterskin(maximum, maximum)
        return result, "装满水囊"
    return result, "没有可装水的水囊"


def waterskin_charges(item: str) -> tuple[int, int]:
    match = re.search(r"\((\d+)\s*/\s*(\d+)\)", item)
    if not match:
        return 3, 3
    maximum = max(1, int(match.group(2)))
    current = max(0, min(maximum, int(match.group(1))))
    return current, maximum


def format_waterskin(current: int, maximum: int) -> str:
    return f"水囊({max(0, current)}/{max(1, maximum)})"
