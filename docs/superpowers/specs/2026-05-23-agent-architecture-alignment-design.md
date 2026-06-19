# Agent Architecture Alignment Design

## Goal

Align the implementation with the original design document by making `backend/src/agent` the home of DM Agent harness code, while keeping domain services in `backend/src/services`.

## Scope

This work combines two confirmed design corrections:

- Preserve the original Chinese design document in the active worktree as `docs/设计文档.md`.
- Move DM Agent orchestration, prompt construction, memory/context orchestration, model client access, output parsing, tool adapters, subagent context scaffolding, and adventure busy locks under `backend/src/agent`.

## Architecture Boundary

`backend/src/agent` owns agent engineering:

- Conversation handling.
- DM prompt construction.
- Agent memory/context assembly.
- Model output parsing.
- LLM client calls.
- Agent tool adapters over domain services.
- Subagent context scaffolding.
- Adventure-level concurrency locks.

`backend/src/services` continues to own domain operations:

- Characters.
- Adventures and messages.
- Stories.
- World/rule search.
- Combat.
- World events persistence.
- LLM model configuration.
- Assets and system capabilities.

The API layer remains thin and imports the DM Agent from `backend.src.agent.dm.service`.

## Target File Structure

```text
backend/src/agent/
  __init__.py
  dm/
    __init__.py
    service.py
    conversation.py
    prompts.py
    memory.py
    tools.py
    output.py
    locks.py
    subagents.py
  llm/
    __init__.py
    client.py
```

Compatibility shims remain temporarily:

- `backend/src/services/dm.py` re-exports `DMService` and `TemplateDMProvider`.
- `backend/src/services/llm_client.py` re-exports `OpenAICompatibleClient`.
- `backend/src/services/context.py` re-exports context classes if context implementation moves.
- `backend/src/services/adventure_locks.py` re-exports `AdventureLockService`.

## Design Document Alignment

`docs/设计文档.md` becomes the canonical Chinese design checkpoint for the MVP. It clarifies:

- The first version uses a lightweight self-owned FastAPI/service/agent architecture instead of deerflow or hermes.
- MCP is implemented as MCP-compatible internal services first, not as a protocol server.
- Real image generation, full PHB retrieval, and complex multi-agent orchestration remain later-stage work.

## System Capabilities Alignment

`/api/system/capabilities` must describe current capabilities accurately:

- characters
- stories
- adventures
- dm_agent
- llm_models
- streaming_dm
- context_summary
- world_events
- world_search
- combat
- image_prompt_stub
- offline_template_provider

Limitations should no longer claim that all DM responses use only the offline template provider.

## Non-Goals

- Do not introduce deerflow, hermes, LangGraph, or a new orchestration runtime.
- Do not change API response schemas.
- Do not change frontend behavior in this refactor.
- Do not move domain services into `agent`.
- Do not implement real MCP protocol server in this step.

## Testing

Add architecture tests that verify:

- DM Agent entrypoint is importable from `backend.src.agent.dm.service`.
- API routes import `DMService` from the agent package.
- Compatibility imports still work from `backend.src.services.dm`.
- Prompt, memory, tools, output, locks, subagents, and LLM client modules exist under `backend/src/agent`.
- System capabilities include the current model/streaming/context features.

Run full regression:

- `uv run pytest -q`
- `node --check frontend/static/app.js`
