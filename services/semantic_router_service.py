import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from constants import DEFAULT_OPENAI_MODEL
from prompts.semantic_router_prompts import SEMANTIC_ROUTER_PROMPT


MONTH_NAME_PATTERN = (
    r"January|February|March|April|May|June|July|August|September|October|November|December"
)
DATE_ONLY_LINE_RE = re.compile(
    rf"^(?:{MONTH_NAME_PATTERN}\s+\d{{1,2}},\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)\s+"
    rf"(?:{MONTH_NAME_PATTERN})|\d{{4}}-\d{{2}}-\d{{2}})$",
    re.IGNORECASE,
)
SCHEDULE_LINE_RE = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.IGNORECASE)


@dataclass
class RoutingMarkdownContext:
    """Normalized markdown input used for semantic routing decisions."""

    title: str
    description: str
    cleaned_body: str
    substantive_lines: list[str]
    total_body_lines: int
    low_information_lines: int


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
    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return ChatOpenAI(model=model_name, temperature=0, api_key=api_key)


def normalize_similarity_score(score: int) -> int:
    """Clamp the model score into the required 0 to 100 range."""
    try:
        numeric_score = int(score)
    except (TypeError, ValueError):
        numeric_score = 0

    return max(0, min(100, numeric_score))


def split_markdown_frontmatter(markdown_content: str) -> tuple[dict[str, str], str]:
    """Split markdown into simple frontmatter metadata and body text."""
    lines = markdown_content.splitlines()
    metadata: dict[str, str] = {}

    if not lines or lines[0].strip() != "---":
        return metadata, markdown_content.strip()

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break

        line = lines[index].strip()
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip("\"'")

    if end_index is None:
        return metadata, markdown_content.strip()

    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def is_image_line(line: str) -> bool:
    """Return True for markdown image lines."""
    return line.strip().startswith("![")


def is_source_line(line: str) -> bool:
    """Return True for markdown source attribution lines."""
    return line.strip().lower().startswith("source:")


def is_boilerplate_line(line: str) -> bool:
    """Return True for known low-information boilerplate lines."""
    normalized = line.strip().lower()
    if not normalized:
        return True

    boilerplate_markers = {
        "latest:",
        '"*" indicates required fields',
        '"*" indicates required fields',
        '"*" indicates required fields.',
    }

    return normalized in boilerplate_markers


def is_date_only_line(line: str) -> bool:
    """Return True for lines that contain only a date-like label."""
    return bool(DATE_ONLY_LINE_RE.fullmatch(line.strip()))


def is_schedule_line(line: str) -> bool:
    """Return True for webinar/event schedule lines."""
    stripped = line.strip()
    if "|" in stripped and SCHEDULE_LINE_RE.search(stripped):
        return True

    return bool(SCHEDULE_LINE_RE.fullmatch(stripped))


def is_promo_line(line: str) -> bool:
    """Return True for event-promo or marketing call-to-action lines."""
    normalized = line.strip().lower()
    return normalized.startswith(("join ", "register ", "sign up ", "learn how "))


def is_low_information_line(line: str) -> bool:
    """Return True for lines that should not drive the relevance decision."""
    stripped = line.strip()
    if not stripped:
        return True

    return any(
        checker(stripped)
        for checker in (
            is_image_line,
            is_source_line,
            is_boilerplate_line,
            is_date_only_line,
            is_schedule_line,
            is_promo_line,
        )
    )


def build_routing_markdown_context(markdown_content: str) -> RoutingMarkdownContext:
    """Prepare cleaned markdown content for semantic routing and heuristics."""
    metadata, body = split_markdown_frontmatter(markdown_content)
    body_lines = [line.strip() for line in body.splitlines() if line.strip()]
    substantive_lines = [line for line in body_lines if not is_low_information_line(line)]
    cleaned_body = "\n\n".join(substantive_lines).strip()

    return RoutingMarkdownContext(
        title=metadata.get("title", ""),
        description=metadata.get("description", ""),
        cleaned_body=cleaned_body,
        substantive_lines=substantive_lines,
        total_body_lines=len(body_lines),
        low_information_lines=max(0, len(body_lines) - len(substantive_lines)),
    )


def has_substantive_article_body(context: RoutingMarkdownContext) -> bool:
    """Return True when the cleaned body looks like a real article narrative."""
    narrative_lines = [
        line
        for line in context.substantive_lines
        if len(line.split()) >= 12 and any(char in line for char in ".:,;")
    ]
    word_count = sum(len(line.split()) for line in context.substantive_lines)
    return len(narrative_lines) >= 2 and word_count >= 80


def looks_like_listing_path(source_url: str) -> bool:
    """Return True for URL shapes that often represent listing or topic pages."""
    path = urlparse(source_url).path.rstrip("/").lower()
    if not path:
        return False

    if path.startswith("/topics/"):
        return True

    path_segments = [segment for segment in path.split("/") if segment]
    return len(path_segments) == 1


def detect_non_article_reason(
    source_url: str,
    context: RoutingMarkdownContext,
) -> str | None:
    """Return a deterministic rejection reason for obvious non-article pages."""
    if not context.cleaned_body:
        if urlparse(source_url).path.rstrip("/").lower().startswith("/topics/"):
            return "Topic page contains metadata and listings but no substantive article body."
        if looks_like_listing_path(source_url):
            return "Listing/index page contains dates or teasers rather than an article narrative."
        return "Markdown does not contain a substantive article body after cleanup."

    low_information_dominates = context.low_information_lines >= max(4, context.total_body_lines // 2)

    if looks_like_listing_path(source_url) and not has_substantive_article_body(context):
        if urlparse(source_url).path.rstrip("/").lower().startswith("/topics/"):
            return "Topic page is dominated by listing content and lacks substantive article narrative."
        return "Section landing page is dominated by listing content rather than a full article."

    if low_information_dominates and not has_substantive_article_body(context):
        return "Page is dominated by dates, schedule blocks, or promotional/listing content."

    return None


def prefilter_markdown(
    source_url: str,
    markdown_content: str,
) -> tuple[RoutingMarkdownContext, SemanticRouterResult | None]:
    """Apply deterministic hard-negative filtering before the LLM call."""
    context = build_routing_markdown_context(markdown_content)
    rejection_reason = detect_non_article_reason(source_url, context)

    if rejection_reason is None:
        return context, None

    return (
        context,
        SemanticRouterResult(
            similarity_score=10,
            selected=False,
            reason=rejection_reason,
        ),
    )


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
    context, prefiltered_result = prefilter_markdown(source_url, markdown_content)
    if prefiltered_result is not None:
        return prefiltered_result

    model = get_semantic_router_model()
    structured_model = model.with_structured_output(SemanticRouterResult)
    chain = SEMANTIC_ROUTER_PROMPT | structured_model

    result = chain.invoke(
        {
            "user_need": user_need,
            "source_url": source_url,
            "article_title": context.title,
            "article_description": context.description,
            "article_body": context.cleaned_body,
        }
    )

    result.similarity_score = normalize_similarity_score(result.similarity_score)
    result.reason = result.reason.strip()
    return result
