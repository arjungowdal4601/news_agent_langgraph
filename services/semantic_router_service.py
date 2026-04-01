import os
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from prompts.semantic_router_prompts import SEMANTIC_ROUTER_PROMPT


class SemanticRouterResult(BaseModel):
    """Structured output returned by the semantic router model."""

    similarity_score: int = Field(description="Similarity score from 0 to 100.")
    selected: bool = Field(description="Whether the markdown matches the user need.")
    reason: str = Field(description="One short reason for the routing decision.")


def get_semantic_router_model() -> ChatOpenAI:
    """Create the chat model used for semantic routing."""
    # The OpenAI API key is loaded from environment variables so secrets are not
    # hardcoded in the source code or committed into the project.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Add it to a .env file in the project root "
            "or set it in your environment before running the pipeline."
        )

    # The model name can be configured with OPENAI_MODEL in .env.
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    return ChatOpenAI(model=model_name, temperature=0, api_key=api_key)


def normalize_similarity_score(score: int) -> int:
    """Clamp the model score into the required 0 to 100 range."""
    try:
        numeric_score = int(score)
    except (TypeError, ValueError):
        numeric_score = 0

    return max(0, min(100, numeric_score))


def resolve_markdown_path(markdown_path: str) -> Path:
    """Resolve Excel markdown paths against the current project folder."""
    path = Path(markdown_path)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def read_markdown_file(markdown_file_path: Path) -> str:
    """Read a markdown file from disk."""
    return markdown_file_path.read_text(encoding="utf-8")


def route_markdown(
    user_need: str,
    source_url: str,
    markdown_content: str,
) -> SemanticRouterResult:
    """Ask the LLM to judge whether the markdown is relevant to the user need."""
    model = get_semantic_router_model()
    structured_model = model.with_structured_output(SemanticRouterResult)
    chain = SEMANTIC_ROUTER_PROMPT | structured_model

    result = chain.invoke(
        {
            "user_need": user_need,
            "source_url": source_url,
            "markdown_content": markdown_content,
        }
    )

    result.similarity_score = normalize_similarity_score(result.similarity_score)
    result.reason = result.reason.strip()
    return result
