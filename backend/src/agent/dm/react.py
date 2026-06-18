from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool


def build_react_agent(
    model: BaseChatModel,
    tools: Sequence[BaseTool | Any],
    system_prompt: str,
    name: str = "react_agent",
):
    return create_agent(
        model=model,
        tools=list(tools),
        system_prompt=system_prompt,
        name=name,
    )
