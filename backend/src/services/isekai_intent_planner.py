from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.src.schemas.adventure import SceneState
from backend.src.services.isekai_action_parser import IsekaiActionParser, ParsedIsekaiAction


@dataclass(frozen=True)
class PlannedIsekaiStep:
    index: int
    text: str
    action: ParsedIsekaiAction


@dataclass(frozen=True)
class IsekaiIntentPlan:
    original_text: str
    steps: list[PlannedIsekaiStep] = field(default_factory=list)
    truncated: bool = False


class IsekaiIntentPlanner:
    def __init__(self, parser: IsekaiActionParser, max_steps: int = 3):
        self.parser = parser
        self.max_steps = max_steps

    def plan(self, content: str, scene: SceneState | None = None) -> IsekaiIntentPlan:
        original = str(content or "").strip()
        segments = self._segments(original)
        selected = segments[: self.max_steps]
        steps = [
            PlannedIsekaiStep(index=index + 1, text=segment, action=self.parser.parse(segment, scene))
            for index, segment in enumerate(selected)
        ]
        return IsekaiIntentPlan(original_text=original, steps=steps, truncated=len(segments) > len(selected))

    def _segments(self, content: str) -> list[str]:
        text = str(content or "").strip()
        if not text:
            return []
        text = re.sub(r"(然后|接着|随后|再|并且|同时)", "||", text)
        text = re.sub(r"[。；;！!？?]", "||", text)
        parts: list[str] = []
        for part in text.split("||"):
            parts.extend(self._split_action_commas(part))
        return [part for part in parts if part]

    def _clean_segment(self, segment: str) -> str:
        text = segment.strip()
        text = text.strip("，, ")
        text = re.sub(r"^(我|角色|玩家)\s*", "", text)
        return text.strip("，, ")

    def _split_action_commas(self, segment: str) -> list[str]:
        chunks = [chunk for chunk in (self._clean_segment(part) for part in re.split(r"[，,]", segment)) if chunk]
        if not chunks:
            return []
        result = [chunks[0]]
        for chunk in chunks[1:]:
            if self._starts_new_action(chunk):
                result.append(chunk)
            else:
                result[-1] = f"{result[-1]}，{chunk}"
        return result

    def _starts_new_action(self, text: str) -> bool:
        return text.startswith(
            (
                "进入",
                "进到",
                "走进",
                "钻进",
                "回前厅",
                "回到前厅",
                "喝",
                "吃",
                "搜索",
                "强行",
                "听到",
                "躲",
                "小心靠近",
                "悄悄靠近",
                "快速靠近",
                "连夜",
                "支付",
                "去后厨修",
            )
        )
