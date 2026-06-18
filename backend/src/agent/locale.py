SUPPORTED_LOCALES = {"en", "zh-CN"}


def normalize_locale(locale: str | None) -> str:
    return locale if locale in SUPPORTED_LOCALES else "en"


def language_instruction(locale: str | None) -> str:
    if normalize_locale(locale) == "zh-CN":
        return (
            "All player-visible prose must be written in natural Simplified Chinese. "
            "Keep JSON field names, tool names, and internal identifiers in English."
        )
    return (
        "All player-visible prose must be written in natural English. "
        "Keep JSON field names, tool names, and internal identifiers in English."
    )
