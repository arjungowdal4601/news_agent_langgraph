from pathlib import Path

from trafilatura import extract, fetch_url


def fetch_webpage(link: str):
    """Download the raw webpage content with Trafilatura."""
    return fetch_url(link)


def extract_markdown(downloaded, link: str) -> str | None:
    """Extract markdown from downloaded webpage content."""
    return extract(
        downloaded,
        url=link,
        output_format="markdown",
        with_metadata=True,
        include_tables=True,
        include_images=True,
        include_links=True,
        favor_recall=True,
        deduplicate=True,
    )


def validate_markdown_result(downloaded, markdown: str | None) -> str:
    """Convert Trafilatura results into the pipeline status values."""
    if not downloaded:
        return "failed"

    if not markdown or not markdown.strip():
        return "empty"

    return "success"


def save_markdown_file(
    markdown: str,
    site_markdown_dir: Path,
    article_slug: str,
    row_number: int,
) -> Path:
    """Save markdown text to a unique file path inside the site folder."""
    markdown_file_path = site_markdown_dir / f"{article_slug}.md"

    # If the same slug appears multiple times, add row number to keep files unique.
    if markdown_file_path.exists():
        markdown_file_path = site_markdown_dir / f"{article_slug}_{row_number}.md"

    markdown_file_path.write_text(markdown, encoding="utf-8")
    return markdown_file_path
