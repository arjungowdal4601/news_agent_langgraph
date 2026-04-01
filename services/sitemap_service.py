from datetime import date
import gzip
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from constants import DATE_RE, HEADERS


def build_sitemap_url(base_url: str) -> str:
    """Always download the top sitemap from the website root."""
    return base_url.rstrip("/") + "/sitemap.xml"


def to_date(text: str) -> date | None:
    """Convert sitemap lastmod text into a Python date.

    Most sitemap lastmod values are ISO-like strings, so taking the first
    10 characters is enough for values like:
    2026-03-25
    2026-03-25T10:30:00Z
    """
    text = str(text or "").strip()
    if not text:
        return None
    return date.fromisoformat(text[:10])


def date_in_url(url: str) -> date | None:
    """Fallback date extractor from child sitemap URLs."""
    match = DATE_RE.search(url)
    if not match:
        return None
    return date.fromisoformat(match.group(1))


def xml_root_from_bytes(content: bytes, source: str = "") -> ET.Element:
    """Read sitemap XML bytes, including .gz child sitemaps."""
    is_gzip = source.lower().endswith(".gz") or content[:2] == b"\x1f\x8b"
    if is_gzip:
        content = gzip.decompress(content)

    text = content.decode("utf-8-sig", errors="replace").strip()
    return ET.fromstring(text)


def read_xml_root_from_file(xml_file_path: str) -> ET.Element:
    """Read the already-downloaded top sitemap file."""
    content = Path(xml_file_path).read_bytes()
    return xml_root_from_bytes(content, xml_file_path)


def get_namespace(root: ET.Element) -> dict[str, str]:
    """Handle namespace-aware sitemap parsing."""
    if root.tag.startswith("{"):
        return {"sm": root.tag.split("}", 1)[0][1:]}
    return {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def get_root_tag_name(root: ET.Element) -> str:
    """Return root tag without namespace.

    Examples:
    {namespace}urlset -> urlset
    {namespace}sitemapindex -> sitemapindex
    """
    if "}" in root.tag:
        return root.tag.split("}", 1)[1]
    return root.tag


def get_child_text(node: ET.Element, tag: str, namespace: dict[str, str]) -> str:
    """Read text from a child XML tag safely."""
    child = node.find(f"sm:{tag}", namespace)
    return child.text.strip() if child is not None and child.text else ""


def keep_url(lastmod: str, cutoff: date) -> bool:
    """Keep only final URLs whose lastmod is on/after cutoff date."""
    parsed = to_date(lastmod)
    return parsed is not None and parsed >= cutoff


def expand_child(child_url: str, parent_lastmod: str, cutoff: date) -> bool:
    """Decide whether to open a child sitemap.

    The child sitemap is opened only if:
    - parent lastmod exists and is recent enough, or
    - the child sitemap URL itself contains a recent enough date.
    """
    parsed_parent = to_date(parent_lastmod)
    parsed_from_url = date_in_url(child_url)
    effective_date = parsed_parent or parsed_from_url
    return effective_date is not None and effective_date >= cutoff


def walk_sitemap(
    root: ET.Element,
    session: requests.Session,
    cutoff: date,
    final_rows: list[dict],
    seen_sitemaps: set[str],
    seen_links: set[str],
) -> None:
    """Recursively walk sitemaps until final article URLs are reached.

    - If root is urlset: collect final article URLs.
    - If root is sitemapindex: open child sitemap files and recurse.
    """
    namespace = get_namespace(root)
    root_tag = get_root_tag_name(root)

    if root_tag == "urlset":
        for node in root.findall("./sm:url", namespace):
            link = get_child_text(node, "loc", namespace)
            lastmod = get_child_text(node, "lastmod", namespace)

            if link and keep_url(lastmod, cutoff) and link not in seen_links:
                seen_links.add(link)
                final_rows.append(
                    {
                        "link": link,
                        "lastmod": lastmod,
                    }
                )
        return

    if root_tag == "sitemapindex":
        for node in root.findall("./sm:sitemap", namespace):
            child_url = get_child_text(node, "loc", namespace)
            parent_lastmod = get_child_text(node, "lastmod", namespace)

            if not child_url:
                continue

            if child_url in seen_sitemaps:
                continue

            if not expand_child(child_url, parent_lastmod, cutoff):
                continue

            seen_sitemaps.add(child_url)

            response = session.get(child_url, headers=HEADERS, timeout=30)
            response.raise_for_status()

            child_root = xml_root_from_bytes(response.content, child_url)
            walk_sitemap(child_root, session, cutoff, final_rows, seen_sitemaps, seen_links)
