import os
import re
from pathlib import Path
from urllib.parse import urlparse


def get_site_name(url: str) -> str:
    """Extract website name from a base URL.

    Example:
    https://www.motortrend.com/ -> motortrend
    """
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.split(".")[0]


def make_safe_slug(value: str, fallback: str) -> str:
    """Convert any text into a file-safe slug."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return (slug or fallback)[:180]


def get_article_slug(url: str) -> str:
    """Build an article-like file name from the URL path."""
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]

    if path_parts:
        candidate = path_parts[-1]
    else:
        candidate = parsed.netloc

    return make_safe_slug(candidate, "article")


def to_relative_path(file_path: Path) -> str:
    """Store relative paths in Excel instead of long absolute paths."""
    return os.path.relpath(file_path.resolve(), start=Path.cwd().resolve()).replace("\\", "/")
