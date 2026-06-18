from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from backend.src.agent.dm.react import build_react_agent
from backend.src.agent.dm.skill_registry import DMSkillRegistry
from backend.src.agent.dm.subagents import NarrationAgent
from backend.src.agent.dm.supervisor import DMSupervisor
from backend.src.agent.dm.subagents import ReactSubAgentRegistry
import backend.src.agent.dm.subagents as subagents_module
import backend.src.agent.dm.supervisor as supervisor_module


def test_react_agent_factory_builds_langgraph_agent():
    model = FakeMessagesListChatModel(responses=[AIMessage(content='{"intent":"exploration","steps":[]}')])

    agent = build_react_agent(model, [], "Plan the DM action.")

    assert isinstance(agent, CompiledStateGraph)


def test_supervisor_uses_react_model_when_available(client):
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content=(
                    '{"intent":"social","steps":['
                    '{"agent":"social_agent","instruction":"Talk to the guard."}]}'
                )
            )
        ]
    )
    supervisor = DMSupervisor(client.app.state.store, model=model)

    plan = supervisor.plan("I talk to the guard.")

    assert plan.intent == "social"
    assert plan.steps[0].agent == "social_agent"


def test_narration_agent_is_separate_from_supervisor_tools():
    model = FakeMessagesListChatModel(
        responses=[AIMessage(content='{"narration":"The gate opens."}')]
    )
    narration = NarrationAgent(model).narrate({"facts": ["The gate opened."]})

    assert narration == "The gate opens."


def test_supervisor_prompt_requires_selected_language(client, monkeypatch):
    captured = {}

    class FakeAgent:
        def invoke(self, _payload):
            return {"messages": [AIMessage(content='{"intent":"exploration","steps":[]}')]}

    def fake_build(_model, _tools, system_prompt, name):
        captured["prompt"] = system_prompt
        captured["name"] = name
        return FakeAgent()

    monkeypatch.setattr(supervisor_module, "build_react_agent", fake_build)
    supervisor = DMSupervisor(
        client.app.state.store,
        model=FakeMessagesListChatModel(responses=[]),
    )

    supervisor.plan("查看房间", locale="zh-CN")

    assert "Simplified Chinese" in captured["prompt"]


def test_open_subagent_and_narration_prompts_require_selected_language(client, monkeypatch):
    prompts = []

    class FakeAgent:
        def invoke(self, _payload):
            return {"messages": [AIMessage(content='{"narration":"门打开了。"}')]}

    def fake_build(_model, _tools, system_prompt, name):
        prompts.append((name, system_prompt))
        return FakeAgent()

    monkeypatch.setattr(subagents_module, "build_react_agent", fake_build)
    model = FakeMessagesListChatModel(responses=[])
    registry = ReactSubAgentRegistry(model, client.app.state.store, locale="zh-CN")

    registry.tools()[0].invoke({"instruction": "查看房间"})
    NarrationAgent(model, locale="zh-CN").narrate({"facts": ["The gate opened."]})

    assert all("Simplified Chinese" in prompt for _, prompt in prompts)


def test_supervisor_and_open_subagents_receive_read_only_skills(client, monkeypatch):
    prompts = []

    class FakeAgent:
        def invoke(self, _payload):
            return {"messages": [AIMessage(content='{"intent":"exploration","steps":[]}')]}

    def fake_build(_model, _tools, system_prompt, name):
        prompts.append((name, system_prompt))
        return FakeAgent()

    monkeypatch.setattr(supervisor_module, "build_react_agent", fake_build)
    monkeypatch.setattr(subagents_module, "build_react_agent", fake_build)
    skill = DMSkillRegistry.load_builtin().match("I pick the lock.")[0]
    model = FakeMessagesListChatModel(responses=[])
    supervisor = DMSupervisor(client.app.state.store, model=model)

    supervisor.plan("I pick the lock.", skills=[skill])
    ReactSubAgentRegistry(
        model,
        client.app.state.store,
        skill_context=[skill],
    ).tools()[0].invoke({"instruction": "I pick the lock."})

    assert any(
        name == "dm_supervisor" and "lockpicking" in prompt
        for name, prompt in prompts
    )
    assert any(
        name == "exploration_agent" and "lockpicking" in prompt
        for name, prompt in prompts
    )
    assert all("DM skills are read-only" in prompt for _, prompt in prompts)
    assert all("commit_agent" not in prompt for _, prompt in prompts)
