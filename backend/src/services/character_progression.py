XP_THRESHOLDS_BY_LEVEL: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def level_for_experience(experience_points: int) -> int:
    xp = max(0, int(experience_points))
    level = 1
    for candidate, threshold in XP_THRESHOLDS_BY_LEVEL.items():
        if xp >= threshold:
            level = candidate
    return level


def next_level_experience(level: int) -> int | None:
    if level >= 20:
        return None
    return XP_THRESHOLDS_BY_LEVEL.get(level + 1)


def character_progression(level: int, experience_points: int) -> dict[str, int | float | None]:
    normalized_level = max(1, min(20, int(level)))
    xp = max(0, int(experience_points))
    current_threshold = XP_THRESHOLDS_BY_LEVEL.get(normalized_level, 0)
    next_threshold = next_level_experience(normalized_level)
    if next_threshold is None:
        return {
            "next_level_experience": None,
            "experience_to_next_level": 0,
            "level_progress": 1.0,
        }

    span = max(1, next_threshold - current_threshold)
    progress = (xp - current_threshold) / span
    return {
        "next_level_experience": next_threshold,
        "experience_to_next_level": max(0, next_threshold - xp),
        "level_progress": max(0.0, min(1.0, progress)),
    }
