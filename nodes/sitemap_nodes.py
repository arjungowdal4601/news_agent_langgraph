from datetime import date

import requests

from constants import DOWNLOAD_DIR, EXCEL_DIR, HEADERS
from services.excel_service import append_extracted_rows, create_workbook, write_headers
from services.path_service import get_site_name
from services.sitemap_service import build_sitemap_url, read_xml_root_from_file, walk_sitemap
from state import PipelineState


# ---------------------------
# Node 1: Download top sitemap XML
# ---------------------------
def download_xml(state: PipelineState) -> dict:
    """Download top sitemap.xml and save it locally."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    base_url = state["base_url"]
    sitemap_url = build_sitemap_url(base_url)

    site_name = get_site_name(base_url)
    file_path = DOWNLOAD_DIR / f"{site_name}.xml"

    response = requests.get(sitemap_url, headers=HEADERS, timeout=30)

    if response.status_code == 403:
        server_name = response.headers.get("server", "unknown")
        raise requests.HTTPError(
            "403 Forbidden while downloading sitemap. "
            f"The site blocked this machine at {sitemap_url} "
            f"(server: {server_name}). "
            "This is typically an anti-bot or IP-level block, not a sitemap path issue.",
            response=response,
        )

    response.raise_for_status()

    file_path.write_bytes(response.content)

    return {"xml_file_path": str(file_path.resolve())}


# ---------------------------
# Node 2: Extract URLs and save them to Excel
# ---------------------------
def extract_urls_to_excel(state: PipelineState) -> dict:
    """Recursively extract final article URLs and save them to an Excel file.

    The Excel file starts with these columns:
    - link
    - lastmod
    - markdown_path
    - markdown_status
    """
    cutoff = date.fromisoformat(state["cutoff_date"])
    top_root = read_xml_root_from_file(state["xml_file_path"])
    site_name = get_site_name(state["base_url"])

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

    # Create site-specific Excel folder and file.
    site_excel_dir = EXCEL_DIR / site_name
    site_excel_dir.mkdir(parents=True, exist_ok=True)
    excel_path = site_excel_dir / f"{site_name}_urls.xlsx"

    workbook = create_workbook()
    worksheet = workbook.active
    worksheet.title = site_name[:31]

    # Write header row.
    write_headers(worksheet)

    # Write extracted sitemap rows.
    append_extracted_rows(worksheet, final_rows)

    workbook.save(excel_path)
    workbook.close()

    return {"excel_file_path": str(excel_path.resolve())}
