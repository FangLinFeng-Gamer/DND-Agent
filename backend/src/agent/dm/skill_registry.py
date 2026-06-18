from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FORBIDDEN_FRONTMATTER_KEYS = {
    "tool",
    "tools",
    "write_tool",
    "write_tools",
    "permissions",
}

FORBIDDEN_BODY_PATTERNS = (
    re.compile(r"\b(call|invoke|use)\s+commit_agent\b", re.IGNORECASE),
    re.compile(r"\b(write|update|delete|insert)\s+(the\s+)?database\b", re.IGNORECASE),
    re.compile(r"\bpersist\s+the\s+result\b", re.IGNORECASE),
)

STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "into",
    "that",
    "the",
    "this",
    "with",
    "your",
}


@dataclass(frozen=True)
class DMSkill:
    name: str
    description: str
    when_to_use: list[str]
    tags: list[str]
    agent: str
    body: str
    path: Path

    def to_prompt_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "when_to_use": list(self.when_to_use),
            "tags": list(self.tags),
            "agent": self.agent,
            "guidance": self.body,
        }


class DMSkillRegistry:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root) if root else Path(__file__).with_name("skills")
        self.skills: list[DMSkill] = []

    @classmethod
    def load_builtin(cls) -> "DMSkillRegistry":
        return cls().load()

    def load(self) -> "DMSkillRegistry":
        self.skills = []
        if not self.root.exists():
            return self
        for path in sorted(self.root.glob("*/SKILL.md")):
            self.skills.append(self._load_skill(path))
        return self

    def match(
        self,
        player_input: str,
        locale: str = "en",
        agent: str | None = None,
        limit: int = 3,
    ) -> list[DMSkill]:
        if not self.skills:
            self.load()
        query = player_input.casefold()
        if not query.strip():
            return []
        query_terms = _terms(query)
        scored = []
        for skill in self.skills:
            if agent and skill.agent != agent:
                continue
            score = self._score(skill, query, query_terms)
            if score > 0:
                scored.append((score, skill.name, skill))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [skill for _, _, skill in scored[:limit]]

    def _load_skill(self, path: Path) -> DMSkill:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text, path)
        forbidden_keys = FORBIDDEN_FRONTMATTER_KEYS & set(frontmatter)
        if forbidden_keys:
            raise ValueError(
                f"DM skill {path} must not declare tools or permissions: "
                + ", ".join(sorted(forbidden_keys))
            )
        if any(pattern.search(body) for pattern in FORBIDDEN_BODY_PATTERNS):
            raise ValueError(
                f"DM skill {path} contains direct state-changing instructions."
            )
        name = str(frontmatter.get("name") or path.parent.name).strip()
        description = str(frontmatter.get("description") or "").strip()
        agent = str(frontmatter.get("agent") or "exploration_agent").strip()
        when_to_use = _string_list(frontmatter.get("when_to_use"))
        tags = _string_list(frontmatter.get("tags"))
        if not name:
            raise ValueError(f"DM skill {path} must declare a name.")
        return DMSkill(
            name=name,
            description=description,
            when_to_use=when_to_use,
            tags=tags,
            agent=agent,
            body=body.strip(),
            path=path,
        )

    def _score(self, skill: DMSkill, query: str, query_terms: set[str]) -> int:
        score = 0
        for tag in skill.tags:
            normalized = tag.casefold()
            if normalized and normalized in query:
                score += 6
        for phrase in skill.when_to_use:
            phrase_terms = _terms(phrase)
            overlap = phrase_terms & query_terms
            score += len(overlap)
            if phrase.casefold() in query:
                score += 8
        haystack_terms = _terms(
            " ".join([skill.name, skill.description, *skill.tags, *skill.when_to_use])
        )
        score += len(haystack_terms & query_terms)
        return score


def format_skill_prompt_context(skills: list[DMSkill] | None) -> str:
    if not skills:
        return ""
    sections = [
        "DM skills are read-only guidance. They are not tools, cannot roll dice, "
        "cannot persist state, and cannot bypass deterministic LangGraph workflows."
    ]
    for skill in skills:
        sections.append(
            "\n".join(
                [
                    f"Skill: {skill.name}",
                    f"Agent: {skill.agent}",
                    f"Description: {skill.description}",
                    "When to use: " + "; ".join(skill.when_to_use),
                    "Tags: " + ", ".join(skill.tags),
                    "Guidance:",
                    skill.body,
                ]
            )
        )
    return "\n\n".join(sections)


def skills_prompt_payload(skills: list[DMSkill] | None) -> list[dict[str, Any]]:
    return [skill.to_prompt_payload() for skill in skills or []]


def _split_frontmatter(text: str, path: Path) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        raise ValueError(f"DM skill {path} must start with frontmatter.")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"DM skill {path} has incomplete frontmatter.")
    return _parse_frontmatter(parts[1]), parts[2]


def _parse_frontmatter(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_list_key:
            data.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        current_list_key = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            data[key] = value
        else:
            data[key] = []
            current_list_key = key
    return data


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z-]{2,}", text.casefold())
        if token not in STOP_WORDS
    }
