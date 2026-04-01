from pathlib import Path
from urllib.parse import urlparse
from datetime import date
from typing_extensions import TypedDict
import gzip
import json
import re
import requests
import xml.etree.ElementTree as ET

from langgraph.graph import StateGraph, START, END


DOWNLOAD_DIR = Path("download_xml")
OUTPUT_DIR = Path("extracted_urls")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    )
}


class XmlState(TypedDict, total=False):
    base_url: str
    cutoff_date: str
    xml_file_path: str
    filtered_urls_file_path: str


def get_site_name(url: str) -> str:
    netloc = urlparse(url).netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    return netloc.split(".")[0]


def build_sitemap_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/sitemap.xml"


def download_xml(state: XmlState) -> dict:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    base_url = state["base_url"]
    sitemap_url = build_sitemap_url(base_url)

    site_name = get_site_name(base_url)
    file_path = DOWNLOAD_DIR / f"{site_name}.xml"

    response = requests.get(sitemap_url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    file_path.write_bytes(response.content)

    return {"xml_file_path": str(file_path)}


def to_date(text: str) -> date | None:
    text = str(text or "").strip()

    if not text:
        return None

    return date.fromisoformat(text[:10])


def date_in_url(url: str) -> date | None:
    match = DATE_RE.search(url)
    if not match:
        return None

    return date.fromisoformat(match.group(1))


def xml_root_from_bytes(content: bytes, source: str = "") -> ET.Element:
    is_gzip = source.lower().endswith(".gz") or content[:2] == b"\x1f\x8b"

    if is_gzip:
        content = gzip.decompress(content)

    text = content.decode("utf-8-sig", errors="replace").strip()
    return ET.fromstring(text)


def read_xml_root_from_file(xml_file_path: str) -> ET.Element:
    content = Path(xml_file_path).read_bytes()
    return xml_root_from_bytes(content, xml_file_path)


def get_namespace(root: ET.Element) -> dict[str, str]:
    if root.tag.startswith("{"):
        return {"sm": root.tag.split("}", 1)[0][1:]}
    return {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def get_root_tag_name(root: ET.Element) -> str:
    if "}" in root.tag:
        return root.tag.split("}", 1)[1]
    return root.tag


def get_child_text(node: ET.Element, tag: str, namespace: dict[str, str]) -> str:
    child = node.find(f"sm:{tag}", namespace)
    return child.text.strip() if child is not None and child.text else ""


def keep_url(lastmod: str, cutoff: date) -> bool:
    parsed = to_date(lastmod)
    return parsed is not None and parsed >= cutoff


def expand_child(child_url: str, parent_lastmod: str, cutoff: date) -> bool:
    parsed_parent = to_date(parent_lastmod)
    parsed_from_url = date_in_url(child_url)
    effective_date = parsed_parent or parsed_from_url
    return effective_date is not None and effective_date >= cutoff


def build_output_file_path(base_url: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    site_name = get_site_name(base_url)
    return OUTPUT_DIR / f"{site_name}_filtered_urls.json"


def walk_sitemap(
    root: ET.Element,
    session: requests.Session,
    cutoff: date,
    final_rows: list[dict],
    seen_sitemaps: set[str],
    seen_links: set[str],
) -> None:
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

            response = session.get(child_url, timeout=30)
            response.raise_for_status()

            child_root = xml_root_from_bytes(response.content, child_url)
            walk_sitemap(child_root, session, cutoff, final_rows, seen_sitemaps, seen_links)

        return


def extract_urls_recursive(state: XmlState) -> dict:
    cutoff = date.fromisoformat(state["cutoff_date"])
    top_root = read_xml_root_from_file(state["xml_file_path"])

    final_rows: list[dict] = []
    seen_sitemaps: set[str] = set()
    seen_links: set[str] = set()

    with requests.Session() as session:
        session.headers.update(HEADERS)
        walk_sitemap(
            root=top_root,
            session=session,
            cutoff=cutoff,
            final_rows=final_rows,
            seen_sitemaps=seen_sitemaps,
            seen_links=seen_links,
        )

    output_path = build_output_file_path(state["base_url"])
    output_path.write_text(
        json.dumps(final_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {"filtered_urls_file_path": str(output_path)}


builder = StateGraph(XmlState)

builder.add_node("download_xml", download_xml)
builder.add_node("extract_urls_recursive", extract_urls_recursive)

builder.add_edge(START, "download_xml")
builder.add_edge("download_xml", "extract_urls_recursive")
builder.add_edge("extract_urls_recursive", END)

graph = builder.compile()


if __name__ == "__main__":
    result = graph.invoke(
        {
            "base_url": "https://www.automotiveworld.com/",
            "cutoff_date": "2026-03-25",
        }
    )

    print("Downloaded XML:", result["xml_file_path"])
    print("Filtered URLs file:", result["filtered_urls_file_path"])