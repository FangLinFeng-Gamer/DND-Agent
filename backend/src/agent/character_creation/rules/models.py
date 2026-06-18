from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


RuleType = Literal[
    "ability",
    "race",
    "subrace",
    "race_option",
    "class",
    "class_option",
    "background",
    "skill",
    "language",
    "tool",
    "armor",
    "weapon",
    "equipment",
    "equipment_option",
    "feat",
    "feat_option",
    "spell",
]


class LocalizedText(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    en: str = Field(min_length=1)
    zh_cn: str = Field(alias="zh-CN", min_length=1)

    def for_locale(self, locale: str) -> str:
        return self.zh_cn if locale == "zh-CN" else self.en


class RulePrerequisite(BaseModel):
    kind: str = Field(min_length=1)
    values: list[str | int] = Field(default_factory=list)
    minimum: int | None = None


class RuleGrant(BaseModel):
    kind: str = Field(min_length=1)
    target: str = Field(min_length=1)
    value: Any = None
    source: str = ""


class RuleChoice(BaseModel):
    id: str = Field(min_length=1)
    name: LocalizedText
    minimum: int = 1
    maximum: int = 1
    option_ids: list[str] = Field(default_factory=list)


class PHBRuleRecord(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    rule_type: RuleType
    name: LocalizedText
    description: LocalizedText
    source: str = Field(min_length=1)
    parent_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    prerequisites: list[RulePrerequisite] = Field(default_factory=list)
    choices: list[RuleChoice] = Field(default_factory=list)
    grants: list[RuleGrant] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def reference_ids(self) -> set[str]:
        references = {self.parent_id} if self.parent_id else set()
        for choice in self.choices:
            references.update(choice.option_ids)
        return references


class PHBRuleManifest(BaseModel):
    version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    files: list[str] = Field(min_length=1)
