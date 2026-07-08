from __future__ import annotations


class IsekaiActionPolicyService:
    CHANGE_PERMISSIONS = {
        "purchase": {"money", "items", "entitlements"},
        "repair": {"relationship", "discount", "quest_flags", "clues"},
        "negotiate": {"quote", "relationship"},
        "quest_resolution": {"quest_stage", "items", "money", "relationship", "clues"},
        "search": {"items", "clues"},
        "gather": {"items"},
        "manage_inventory": {"items"},
        "short_dialogue": {"relationship", "clues"},
    }

    FORBIDDEN_ACTIONS = {"table_talk", "status_check", "clarification", "condition_failed"}

    def allowed_changes(self, action_type: str) -> set[str]:
        if action_type in self.FORBIDDEN_ACTIONS:
            return set()
        return set(self.CHANGE_PERMISSIONS.get(action_type, set()))

    def allows(self, action_type: str, change_kind: str) -> bool:
        return change_kind in self.allowed_changes(action_type)

    def blocked_reason(self, action_type: str, change_kind: str) -> str:
        if self.allows(action_type, change_kind):
            return ""
        return f"{action_type}_cannot_apply_{change_kind}"
