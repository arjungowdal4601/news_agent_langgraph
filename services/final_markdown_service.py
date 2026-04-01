import json
import os
import re
from datetime import date
from pathlib import Path

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from constants import DEFAULT_OPENAI_MODEL
from prompts.final_markdown_prompts import FINAL_MARKDOWN_PROMPT

MARKDOWN_BULLET_RE = re.compile(r"^(?:[-*]\s+\S|\d+\.\s+\S)")


class FinalMarkdownArticleResult(BaseModel):
    """Structured output returned for one composed newsletter article."""

    source_url: str = Field(description="Source article URL.")
    title: str = Field(description="Clean article title without markdown heading markers.")
    final_markdown_body: str = Field(
        description="Final polished markdown body without YAML frontmatter."
    )


class FinalMarkdownBatchResult(BaseModel):
    """Structured output returned for a batch of composed articles."""

    articles: list[FinalMarkdownArticleResult] = Field(
        description="Final composed article results in the same order as the input batch."
    )


def get_final_markdown_model() -> ChatOpenAI:
    """Create the chat model used for final newsletter composition."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Add it to a .env file in the project root "
            "or set it in your environment before running the pipeline."
        )

    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return ChatOpenAI(model=model_name, temperature=0, api_key=api_key)


def extract_frontmatter_value(markdown_content: str, key: str) -> str:
    """Read a single YAML-like frontmatter value if it exists."""
    lines = markdown_content.splitlines()

    if not lines or lines[0].strip() != "---":
        return ""

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":
            break
        if stripped.startswith(f"{key}:"):
            return stripped.split(":", 1)[1].strip().strip("\"'")

    return ""


def clean_article_title(title: str, fallback: str = "Untitled Article") -> str:
    """Normalize model-returned titles for section headings."""
    cleaned = re.sub(r"^#{1,6}\s+", "", str(title or "").strip()).strip()
    return cleaned or fallback


def strip_yaml_frontmatter(markdown_content: str) -> str:
    """Remove YAML frontmatter from markdown text if present."""
    lines = markdown_content.splitlines()
    if not lines or lines[0].strip() != "---":
        return markdown_content.strip()

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :]).strip()

    return markdown_content.strip()


def clean_final_markdown_body(markdown_body: str) -> str:
    """Normalize model output before it is appended to the newsletter file."""
    cleaned = strip_yaml_frontmatter(markdown_body).strip()
    lines = cleaned.splitlines()

    while lines and not lines[0].strip():
        lines.pop(0)

    if lines and re.match(r"^#{1,2}\s+", lines[0].strip()):
        lines.pop(0)

    return "\n".join(lines).strip()


def extract_markdown_lines(
    markdown_content: str,
    predicate,
) -> list[str]:
    """Extract stripped markdown lines that match the provided predicate."""
    body = strip_yaml_frontmatter(markdown_content)
    return [line.strip() for line in body.splitlines() if predicate(line.strip())]


def extract_image_lines(markdown_content: str) -> list[str]:
    """Extract markdown image lines that must be preserved."""
    return extract_markdown_lines(markdown_content, lambda line: line.startswith("!["))


def extract_source_lines(markdown_content: str) -> list[str]:
    """Extract markdown source-attribution lines that must be preserved."""
    return extract_markdown_lines(markdown_content, lambda line: line.lower().startswith("source:"))


def normalize_markdown_line(line: str) -> str:
    """Normalize markdown lines for preservation checks."""
    return re.sub(r"\s+", " ", line.strip())


def has_markdown_bullets(markdown_body: str) -> bool:
    """Return True when the markdown body contains list bullets."""
    return any(MARKDOWN_BULLET_RE.match(line.strip()) for line in markdown_body.splitlines())


def build_article_payload(article: dict) -> dict:
    """Build one prompt payload item with preservation requirements."""
    markdown_content = article["markdown_content"]
    return {
        "source_url": article["source_url"],
        "title_hint": article.get("title_hint", ""),
        "article_markdown": strip_yaml_frontmatter(markdown_content),
        "required_image_lines": extract_image_lines(markdown_content),
        "required_source_lines": extract_source_lines(markdown_content),
    }


def validate_final_markdown_body(article_input: dict, markdown_body: str) -> str:
    """Validate the composed markdown body before it is accepted."""
    cleaned_body = clean_final_markdown_body(markdown_body)
    if not has_markdown_bullets(cleaned_body):
        raise ValueError("The composed article body did not contain Markdown bullet points.")

    normalized_output_lines = {
        normalize_markdown_line(line)
        for line in cleaned_body.splitlines()
        if normalize_markdown_line(line)
    }

    for image_line in article_input.get("required_image_lines", []):
        if normalize_markdown_line(image_line) not in normalized_output_lines:
            raise ValueError("The composed article body dropped a required image line.")

    for source_line in article_input.get("required_source_lines", []):
        if normalize_markdown_line(source_line) not in normalized_output_lines:
            raise ValueError("The composed article body dropped a required source line.")

    return cleaned_body


def compose_final_markdown_batch(article_inputs: list[dict]) -> list[FinalMarkdownArticleResult]:
    """Compose one batch of article markdown files into newsletter-ready markdown."""
    model = get_final_markdown_model()
    structured_model = model.with_structured_output(FinalMarkdownBatchResult)
    chain = FINAL_MARKDOWN_PROMPT | structured_model

    prepared_inputs = [{**article, **build_article_payload(article)} for article in article_inputs]
    payload = [
        {
            "source_url": article["source_url"],
            "title_hint": article["title_hint"],
            "article_markdown": article["article_markdown"],
            "required_image_lines": article["required_image_lines"],
            "required_source_lines": article["required_source_lines"],
        }
        for article in prepared_inputs
    ]

    result = chain.invoke({"articles_payload": json.dumps(payload, ensure_ascii=False, indent=2)})
    return validate_batch_result(prepared_inputs, result)


def validate_batch_result(
    article_inputs: list[dict],
    result: FinalMarkdownBatchResult,
) -> list[FinalMarkdownArticleResult]:
    """Ensure the structured output matches the input batch exactly."""
    expected_by_url = {article["source_url"]: article for article in article_inputs}
    seen_urls: set[str] = set()
    normalized_by_url: dict[str, FinalMarkdownArticleResult] = {}

    for article in result.articles:
        source_url = str(article.source_url or "").strip()
        if not source_url or source_url not in expected_by_url:
            raise ValueError("The composed batch returned an unexpected source_url.")
        if source_url in seen_urls:
            raise ValueError("The composed batch returned duplicate source_url values.")

        seen_urls.add(source_url)
        fallback_title = expected_by_url[source_url].get("title_hint") or "Untitled Article"
        normalized_by_url[source_url] = FinalMarkdownArticleResult(
            source_url=source_url,
            title=clean_article_title(article.title, fallback=fallback_title),
            final_markdown_body=validate_final_markdown_body(
                expected_by_url[source_url],
                article.final_markdown_body,
            ),
        )

    if len(normalized_by_url) != len(article_inputs):
        raise ValueError("The composed batch did not return every requested article.")

    return [normalized_by_url[article["source_url"]] for article in article_inputs]


def build_newsletter_header(site_name: str) -> str:
    """Build the top section for a final combined newsletter markdown file."""
    display_name = site_name.replace("-", " ").replace("_", " ").strip().title() or site_name
    return f"# {display_name} Final Newsletter\n\nGenerated: {date.today().isoformat()}\n"


def initialize_final_markdown_file(final_markdown_path: Path, site_name: str) -> None:
    """Create or overwrite the final newsletter file for the current run."""
    final_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    final_markdown_path.write_text(build_newsletter_header(site_name), encoding="utf-8")


def format_final_article_section(article: FinalMarkdownArticleResult) -> str:
    """Format one composed article as a section inside the combined newsletter file."""
    body = clean_final_markdown_body(article.final_markdown_body)
    return f"## {article.title}\n\nSource URL: <{article.source_url}>\n\n{body}".strip()


def append_article_sections(final_markdown_path: Path, sections: list[str]) -> None:
    """Append composed article sections to the combined newsletter file."""
    cleaned_sections = [section.strip() for section in sections if section.strip()]
    if not cleaned_sections:
        return

    with final_markdown_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write("\n\n")
        file_handle.write("\n\n".join(cleaned_sections))
        file_handle.write("\n")
