import re
from datetime import date
from pathlib import Path

import requests
from trafilatura import extract, fetch_url

from constants import DATE_RE, HEADERS


PUBLISHED_DATE_PATTERNS = [
    re.compile(
        r'<meta[^>]+(?:property|name)=["\']article:published_time["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']article:published_time["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+(?:property|name)=["\']datePublished["\'][^>]+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    ),
    re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']datePublished["\']',
        re.IGNORECASE,
    ),
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r"'datePublished'\s*:\s*'([^']+)'", re.IGNORECASE),
]


def fetch_webpage(link: str):
    """Download the raw webpage content with Trafilatura."""
    return fetch_url(link)


def should_enforce_published_date_cutoff(site_name: str) -> bool:
    """Return True when the site requires a page-level published-date cutoff."""
    return site_name == "motortrend"


def parse_html_date(value: str) -> date | None:
    """Extract the first ISO-like date from HTML metadata text."""
    text = str(value or "").strip()
    if not text:
        return None

    match = DATE_RE.search(text)
    if not match:
        return None

    return date.fromisoformat(match.group(1))


def extract_published_date_from_html(html_text: str) -> date | None:
    """Extract a page published date from common HTML meta and JSON-LD fields."""
    for pattern in PUBLISHED_DATE_PATTERNS:
        match = pattern.search(html_text)
        if not match:
            continue

        parsed_date = parse_html_date(match.group(1))
        if parsed_date is not None:
            return parsed_date

    return None


def fetch_html_for_metadata(link: str) -> str:
    """Fetch raw HTML with requests as a metadata fallback."""
    response = requests.get(link, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def extract_page_published_date(downloaded, link: str) -> date | None:
    """Extract a published date from the already-downloaded page, with HTTP fallback."""
    html_text = ""
    if isinstance(downloaded, bytes):
        html_text = downloaded.decode("utf-8", errors="replace")
    elif downloaded:
        html_text = str(downloaded)

    parsed_from_download = extract_published_date_from_html(html_text)
    if parsed_from_download is not None:
        return parsed_from_download

    try:
        fallback_html = fetch_html_for_metadata(link)
    except Exception:
        return None

    return extract_published_date_from_html(fallback_html)


def is_on_or_after_cutoff(candidate_date: date, cutoff_text: str) -> bool:
    """Return True when a date is on or after the inclusive cutoff date."""
    cutoff = date.fromisoformat(str(cutoff_text).strip()[:10])
    return candidate_date >= cutoff


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
