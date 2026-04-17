"""Single source of truth for chat model construction.

To switch the entire pipeline to a different LLM provider (Azure OpenAI,
Anthropic, a local model, etc.) edit ONLY this file. All services call
`get_chat_model()` and never construct provider clients directly.

The `purpose` argument is informational ("router", "extractor", "composer")
so different jobs can later be routed to different models or tiers without
changing any caller.
"""

from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from constants import DEFAULT_OPENAI_MODEL


def get_chat_model(purpose: str = "default", temperature: float = 0) -> BaseChatModel:
    """Return the chat model used by the pipeline.

    Default implementation: OpenAI via langchain-openai.
    Swap the body of this function to use a different provider; the rest of
    the codebase does not need any changes.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Add it to a .env file in the project root "
            "or set it in your environment before running the pipeline."
        )

    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return ChatOpenAI(model=model_name, temperature=temperature, api_key=api_key)


# ---------------------------------------------------------------------------
# Provider-swap recipes (uncomment and replace the body of get_chat_model
# above with one of these to migrate the whole pipeline).
# ---------------------------------------------------------------------------
#
# Azure OpenAI:
#
#   from langchain_openai import AzureChatOpenAI
#
#   return AzureChatOpenAI(
#       azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
#       api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
#       azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
#       api_key=os.getenv("AZURE_OPENAI_API_KEY"),
#       temperature=temperature,
#   )
#
# Anthropic:
#
#   from langchain_anthropic import ChatAnthropic
#
#   return ChatAnthropic(
#       model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6"),
#       api_key=os.getenv("ANTHROPIC_API_KEY"),
#       temperature=temperature,
#   )
#
# Different model per purpose:
#
#   if purpose == "router":
#       return ChatOpenAI(model="gpt-4o-mini", temperature=temperature, api_key=api_key)
#   return ChatOpenAI(model="gpt-4o", temperature=temperature, api_key=api_key)
