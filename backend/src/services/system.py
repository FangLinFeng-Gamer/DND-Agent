CAPABILITIES = {
    "features": [
        "characters",
        "stories",
        "adventures",
        "dm_agent",
        "langgraph_multi_agent_dm",
        "react_subagents",
        "character_creation_agent",
        "llm_models",
        "streaming_dm",
        "context_summary",
        "world_events",
        "world_search",
        "combat",
        "image_prompt_stub",
        "offline_template_provider",
    ],
    "limitations": [
        "Image generation records prompts but is not connected to an image provider.",
        "MCP-compatible tools are internal services; a real MCP protocol server is not exposed yet.",
        "PHB PDF retrieval is reserved for a later version.",
    ],
}


class SystemService:
    def capabilities(self) -> dict[str, list[str]]:
        return CAPABILITIES
