from datetime import date
import gzip
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from constants import DATE_RE, HEADERS, SITEMAP_AUDIT_DIR


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


def create_sitemap_audit(
    site_name: str,
    cutoff: date,
    top_sitemap_path: str,
) -> dict:
    """Create the mutable sitemap audit structure used during recursion."""
    return {
        "site_name": site_name,
        "cutoff_date": cutoff.isoformat(),
        "top_sitemap_path": top_sitemap_path,
        "sitemapindex_nodes_traversed": 0,
        "urlset_nodes_traversed": 0,
        "child_sitemaps_seen": 0,
        "child_sitemaps_opened": 0,
        "child_sitemaps_skipped_before_cutoff": 0,
        "child_sitemap_samples_opened_recent_lastmod": [],
        "child_sitemap_samples_skipped_before_cutoff": [],
        "final_urls_seen": 0,
        "final_urls_kept": 0,
        "final_urls_skipped_before_cutoff": 0,
        "final_url_samples_skipped_before_cutoff": [],
        "guard_rows_removed_after_walk": 0,
        "guard_rows_removed_samples": [],
        "kept_min_lastmod": "",
        "kept_max_lastmod": "",
    }


def _append_audit_sample(audit: dict | None, key: str, value: dict, limit: int = 10) -> None:
    """Append one sample item to an audit list without letting it grow unbounded."""
    if audit is None:
        return
    samples = audit.setdefault(key, [])
    if len(samples) < limit:
        samples.append(value)


def finalize_sitemap_audit(audit: dict, final_rows: list[dict]) -> dict:
    """Update summary fields after all filtered rows are known."""
    kept_dates = [
        parsed.isoformat()
        for row in final_rows
        if (parsed := to_date(row.get("lastmod", ""))) is not None
    ]

    audit["final_urls_kept"] = len(final_rows)
    audit["kept_min_lastmod"] = min(kept_dates) if kept_dates else ""
    audit["kept_max_lastmod"] = max(kept_dates) if kept_dates else ""
    return audit


def write_sitemap_audit(site_name: str, audit: dict) -> str:
    """Persist one site-scoped sitemap audit artifact."""
    SITEMAP_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = SITEMAP_AUDIT_DIR / f"{site_name}_cutoff_audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(audit_path.resolve())


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
    """Keep only final URLs whose lastmod is on or after the cutoff date.

    The cutoff acts as an inclusive lower bound:
    - keep when lastmod == cutoff
    - keep when lastmod > cutoff
    - skip when lastmod < cutoff
    """
    parsed = to_date(lastmod)
    return parsed is not None and parsed >= cutoff


def expand_child(child_url: str, parent_lastmod: str, cutoff: date) -> bool:
    """Decide whether to open a child sitemap.

    The child sitemap is opened only if its effective date is on or after the
    cutoff date, using the same inclusive lower-bound rule as final URLs:
    - keep when effective_date == cutoff
    - keep when effective_date > cutoff
    - skip when effective_date < cutoff

    The effective date comes from:
    - parent lastmod when available, otherwise
    - a date embedded in the child sitemap URL
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
    audit: dict | None = None,
) -> None:
    """Recursively walk sitemaps until final article URLs are reached.

    - If root is urlset: collect final article URLs.
    - If root is sitemapindex: open child sitemap files and recurse.
    """
    namespace = get_namespace(root)
    root_tag = get_root_tag_name(root)

    if root_tag == "urlset":
        if audit is not None:
            audit["urlset_nodes_traversed"] += 1
        for node in root.findall("./sm:url", namespace):
            link = get_child_text(node, "loc", namespace)
            lastmod = get_child_text(node, "lastmod", namespace)
            if audit is not None and link:
                audit["final_urls_seen"] += 1

            if link and keep_url(lastmod, cutoff) and link not in seen_links:
                seen_links.add(link)
                final_rows.append(
                    {
                        "link": link,
                        "lastmod": lastmod,
                    }
                )
                if audit is not None:
                    audit["final_urls_kept"] += 1
            elif link and audit is not None and not keep_url(lastmod, cutoff):
                audit["final_urls_skipped_before_cutoff"] += 1
                _append_audit_sample(
                    audit,
                    "final_url_samples_skipped_before_cutoff",
                    {
                        "link": link,
                        "lastmod": lastmod,
                    },
                )
        return

    if root_tag == "sitemapindex":
        if audit is not None:
            audit["sitemapindex_nodes_traversed"] += 1
        for node in root.findall("./sm:sitemap", namespace):
            child_url = get_child_text(node, "loc", namespace)
            parent_lastmod = get_child_text(node, "lastmod", namespace)

            if not child_url:
                continue

            if audit is not None:
                audit["child_sitemaps_seen"] += 1

            if child_url in seen_sitemaps:
                continue

            parsed_parent = to_date(parent_lastmod)
            parsed_from_url = date_in_url(child_url)
            effective_date = parsed_parent or parsed_from_url

            if not expand_child(child_url, parent_lastmod, cutoff):
                if audit is not None:
                    audit["child_sitemaps_skipped_before_cutoff"] += 1
                    _append_audit_sample(
                        audit,
                        "child_sitemap_samples_skipped_before_cutoff",
                        {
                            "child_url": child_url,
                            "parent_lastmod": parent_lastmod,
                            "effective_date": effective_date.isoformat() if effective_date else "",
                        },
                    )
                continue

            seen_sitemaps.add(child_url)
            if audit is not None:
                audit["child_sitemaps_opened"] += 1
                if "2025" in child_url and effective_date is not None and effective_date >= cutoff:
                    _append_audit_sample(
                        audit,
                        "child_sitemap_samples_opened_recent_lastmod",
                        {
                            "child_url": child_url,
                            "parent_lastmod": parent_lastmod,
                            "effective_date": effective_date.isoformat(),
                        },
                    )

            response = session.get(child_url, headers=HEADERS, timeout=30)
            response.raise_for_status()

            child_root = xml_root_from_bytes(response.content, child_url)
            walk_sitemap(
                child_root,
                session,
                cutoff,
                final_rows,
                seen_sitemaps,
                seen_links,
                audit=audit,
            )
