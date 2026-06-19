# DND-Agent MVP Handoff

## Current Branch and Workspace

- Feature worktree: `F:\project\DND-Agent\.worktrees\dnd-agent-mvp`
- Feature branch: `dnd-agent-mvp`
- Base branch: `main`
- Main branch has pre-existing uncommitted user/draft changes. Do not merge into `main` without first protecting those changes.

## User-Approved Design Decisions

- MVP scope: playable Web MVP, not backend-only and not full complete system.
- DM text generation: pluggable `LLMProvider`; default offline template provider.
- Rules/world data: built-in structured MVP data first; reserve PDF retrieval interface for later.
- Frontend: FastAPI-served static HTML/CSS/JavaScript, no frontend build chain.
- MCP: implement MCP-compatible internal tool/service layer first, not a real MCP server.
- DND mechanics: include basic combat prototype with initiative, turn order, HP, AC, d20 attack/checks, damage, advantage, and disadvantage.

## Reference Documents

- Design spec: `docs/superpowers/specs/2026-05-22-dnd-agent-mvp-design.md`
- Implementation plan: `docs/superpowers/plans/2026-05-22-dnd-agent-mvp.md`
- This handoff: `docs/superpowers/progress/2026-05-22-dnd-agent-mvp-handoff.md`

## Completed Commits on `dnd-agent-mvp`

- `562e5e0 feat: add app foundation and sqlite schema`
- `f5bf26e fix: keep app startup database isolated`
- `ff90819 feat: add character management`
- `3d88e78 fix: validate character updates`
- `9bffdb9 fix: harden character update validation`
- `1300902 fix: handle invalid character patch json`
- `050eea6 feat: add world and rules search`
- `e68a380 feat: add basic combat rules`
- `e19ca84 fix: harden combat turn handling`
- `7ec8062 fix: enforce combat active state`
- `7d6cd30 feat: add adventure sessions and dm loop`
- `e218935 fix: validate adventure message lookup`
- `ee29973 fix: enforce adventure combat state`
- `ffc908f test: assert combat start preserves active state`
- `2c4b5ee feat: add capabilities and image stub`
- `a5a0392 feat: add static web ui`
- `9b5023d fix: harden static ui state handling`
- `f531ee5 docs: add mvp run instructions`
- `6015e1a chore: ignore runtime artifacts`
- `4451dbb fix: send chat message on enter`
- `b223622 chore: ignore uv and server logs`
- `0b9e747 feat: add frontend language switcher`

## 2026-05-23 Update

Current status:

- MVP implementation is complete on the feature branch.
- Frontend now has an English/Chinese language selector in the top bar.
- Language choice is stored in `localStorage` under `dnd-agent.locale`.
- The language switch localizes frontend labels, placeholders, buttons, status messages, empty states, capability labels, role/side labels, and common world-search status messages.
- Backend API field names, routes, error codes, DM template output, and seeded world data remain unchanged.
- The attempted direct Chinese-only localization was reverted before the language switch implementation.

Latest verified result:

- `uv run pytest -q` returned `44 passed`.
- `node --check frontend/static/app.js` returned exit code `0`.
- `Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/ | Select-Object -ExpandProperty StatusCode` returned `200`.
- `git status --short` returned no changes after commit `0b9e747`.

## Task Progress

### Task 1: Test Tooling and App Foundation

Status: complete.

Implemented:

- `pyproject.toml`
- `backend/src/main.py`
- `backend/src/core/settings.py`
- `backend/src/core/errors.py`
- `backend/src/db/sqlite.py`
- `test/conftest.py`
- `test/test_foundation.py`

Review status:

- Spec compliance review: passed.
- Code quality review: initially requested changes for import-time DB creation and missing smoke test.
- Fix committed in `f5bf26e`; final code quality review approved.

Last verified result:

- `uv run pytest -q` returned `2 passed` after Task 1.

### Task 2: Character Models, Service, and API

Status: complete.

Implemented:

- `backend/src/schemas/character.py`
- `backend/src/services/characters.py`
- `backend/src/api/characters.py`
- router registration in `backend/src/main.py`
- `test/test_characters.py`

Review status:

- Spec compliance review initially failed on weak update validation.
- Fixes added for HP invariants, explicit null values, unknown fields, row guards, missing character behavior, and invalid JSON PATCH bodies.
- Final spec compliance review passed.
- Final code quality review approved.

Last verified result:

- `uv run pytest test/test_characters.py` returned `10 passed`.
- `uv run pytest` returned `12 passed`.

### Task 3: World and Rules Search

Status: implementation complete; spec compliance review passed; code quality review pending.

Implemented:

- `backend/src/schemas/world.py`
- `backend/src/services/world.py`
- `backend/src/api/world.py`
- startup seeding and router registration in `backend/src/main.py`
- `test/test_world.py`

Review status:

- Spec compliance review passed.
- Code quality review subagent was started but the parent turn was interrupted before it returned. Re-run or resume code quality review before marking Task 3 complete.

Last verified result:

- Implementer reported `uv run pytest test/test_world.py -q` returned `2 passed`.
- Implementer reported `uv run pytest -q` returned `14 passed`.

## Remaining Tasks

MVP tasks from the implementation plan are complete. Suggested next tasks:

1. Add real LLM provider integration behind the existing `LLMProvider` protocol.
2. Add a real MCP server surface if external MCP clients are required.
3. Expand rules/world data ingestion from the PHB PDF into structured searchable entries.
4. Add richer character creation guidance and editing flows in the UI.
5. Add frontend interaction tests with a browser runner.

## Important Safety Notes

- The original `main` worktree at `F:\project\DND-Agent` has pre-existing uncommitted changes, including backend agent/memory drafts and untracked files. Do not run destructive commands or reset them.
- The feature work is isolated in `.worktrees/dnd-agent-mvp`.
- If merging completed tasks into `main`, first stash/commit/protect the main worktree changes or use `git merge --autostash` only with explicit user approval.
- Generated files such as `__pycache__` and untracked `uv.lock` were cleaned from the feature worktree before this handoff.

## Recommended Resume Prompt

Continue DND-Agent MVP from `F:\project\DND-Agent\.worktrees\dnd-agent-mvp` on branch `dnd-agent-mvp`. Read `docs/superpowers/progress/2026-05-22-dnd-agent-mvp-handoff.md` and `docs/superpowers/plans/2026-05-22-dnd-agent-mvp.md`. The MVP code is complete through the static UI, Enter-to-send fix, and frontend English/Chinese language switch. Latest verification: `uv run pytest -q` -> `44 passed`; `node --check frontend/static/app.js` -> exit code `0`; local service root -> HTTP `200`.

## 2026-06-06 LangGraph Multi-Agent Update

- Added a constrained ReAct DM supervisor using LangChain `create_agent`.
- Added ReAct exploration, social, story, NPC, and rules-research subagent tools.
- Added a separate narration agent; the supervisor does not generate final prose.
- Added compiled LangGraph workflows for ability checks, saving throws, combat, scene updates, memory, and commits.
- Added an OpenAI-compatible `BaseChatModel` adapter with tool-call conversion.
- Routed DM model planning through the compiled graph while preserving template fallback.
- Added resumable character-creation sessions with ReAct guidance, fixed validation, and explicit confirmation before persistence.
- Added `/api/character-creation/sessions` endpoints.
- Implementation plan: `docs/superpowers/plans/2026-06-06-langgraph-multi-agent-dm.md`.

## 2026-06-07 Multilingual Agent Interaction Update

- Replaced direct frontend character creation with a guided Character Creation
  Agent session, visible conversation, structured draft, validation messages,
  and explicit confirmation.
- Added the shared `en` / `zh-CN` locale contract and passed locale through
  adventure creation, DM synchronous and streaming messages, the supervisor,
  open subagents, character creation, narration, and template fallback.
- Added explicit model prompt requirements for Simplified Chinese or English.
- Added locale-aware adventure opening and offline DM fallback text.
- Preserved English defaults for clients that omit locale.
- Added `scripts/verify_multilingual_agent_flow.py`.
- Live verification completed Chinese character creation, Chinese streaming DM
  narration, and an English DM reply after switching locale.
- Browser automation could not attach because the local Windows browser-control
  process was blocked by the sandbox. HTTP, static frontend, syntax, and full
  backend verification were used instead.

## 2026-06-07 PHB Character Creation Phase 1

- Added an authoritative typed PHB rule repository separate from display-oriented
  world search.
- Added bilingual canonical rule records, reference validation, and localized
  search.
- Added version 2 character creation drafts with 12 steps, revision tracking,
  canonical selections, layered ability values, derived sheet placeholders, and
  pending Agent suggestions.
- Added additive SQLite revision migration and legacy draft compatibility.
- Added deterministic 27-point buy, ability modifiers, fixed race/subrace
  bonuses, half-elf choices, and variant-human choices.
- Added revision-safe `PATCH /api/character-creation/sessions/{id}/draft` for
  identity, race, and ability mutations.
- Runtime verification script:
  `scripts/verify_character_creation_phase1.py`.
- The bundled phase-one rules are intentionally a foundation subset. Full PHB
  race, class, background, feat, spell, and equipment coverage is scheduled in
  later roadmap phases.
