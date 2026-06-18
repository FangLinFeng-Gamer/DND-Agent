def chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


def extract_narration_text(partial_json: str) -> str:
    key_index = partial_json.find('"narration"')
    if key_index < 0:
        return ""
    colon_index = partial_json.find(":", key_index)
    if colon_index < 0:
        return ""
    quote_index = partial_json.find('"', colon_index + 1)
    if quote_index < 0:
        return ""

    chars: list[str] = []
    escaped = False
    for char in partial_json[quote_index + 1 :]:
        if escaped:
            chars.append("\n" if char == "n" else char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            break
        chars.append(char)
    return "".join(chars)
