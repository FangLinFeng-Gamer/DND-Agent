from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def test_dm_agent_harness_modules_live_under_agent_package():
    from backend.src.agent.dm.locks import AdventureLockService
    from backend.src.agent.dm.memory import AgentMemoryManager
    from backend.src.agent.dm.output import extract_narration_text
    from backend.src.agent.dm.prompts import build_dm_messages
    from backend.src.agent.dm.service import DMService, TemplateDMProvider
    from backend.src.agent.dm.subagents import SubAgentContext
    from backend.src.agent.dm.tools import DMAgentTools
    from backend.src.agent.llm.client import OpenAICompatibleClient

    assert DMService
    assert TemplateDMProvider
    assert build_dm_messages
    assert AgentMemoryManager
    assert DMAgentTools
    assert extract_narration_text
    assert AdventureLockService
    assert SubAgentContext
    assert OpenAICompatibleClient


def test_legacy_service_imports_remain_compatible():
    from backend.src.agent.dm.service import DMService as AgentDMService
    from backend.src.agent.llm.client import OpenAICompatibleClient as AgentClient
    from backend.src.services.dm import DMService as LegacyDMService
    from backend.src.services.llm_client import OpenAICompatibleClient as LegacyClient

    assert LegacyDMService is AgentDMService
    assert LegacyClient is AgentClient


def test_adventure_api_uses_agent_dm_service_entrypoint():
    source = (ROOT / "backend" / "src" / "api" / "adventures.py").read_text(encoding="utf-8")

    assert "from backend.src.agent.dm.service import DMService" in source
    assert "from backend.src.services.dm import DMService" not in source
