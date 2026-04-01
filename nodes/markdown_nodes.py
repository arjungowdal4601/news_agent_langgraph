from pathlib import Path

from constants import MARKDOWN_DIR
from services.excel_service import (
    load_workbook,
    map_header_columns,
    save_workbook,
    update_markdown_path,
    update_markdown_status,
)
from services.markdown_service import (
    extract_markdown,
    fetch_webpage,
    save_markdown_file,
    validate_markdown_result,
)
from services.path_service import get_article_slug, get_site_name, to_relative_path
from state import PipelineState


# ---------------------------
# Node 3: Download article markdown and update Excel
# ---------------------------
def download_markdown_from_excel(state: PipelineState) -> dict:
    """Read URLs from Excel, extract markdown with Trafilatura, save files,
    and update the Excel workbook with markdown path + markdown status.

    Status values used:
    - success : markdown extracted and saved
    - failed  : fetch/extract raised an error
    - empty   : extraction completed but markdown was empty
    """
    excel_path = Path(state["excel_file_path"])
    site_name = get_site_name(state["base_url"])

    # Create site-specific markdown folder.
    site_markdown_dir = MARKDOWN_DIR / site_name
    site_markdown_dir.mkdir(parents=True, exist_ok=True)

    workbook = load_workbook(excel_path)
    worksheet = workbook.active

    # Map headers to column indexes.
    header_map = map_header_columns(worksheet)
    link_col = header_map["link"]
    markdown_path_col = header_map["markdown_path"]
    markdown_status_col = header_map["markdown_status"]

    for row_number in range(2, worksheet.max_row + 1):
        link = str(worksheet.cell(row=row_number, column=link_col).value or "").strip()

        if not link:
            update_markdown_status(worksheet, row_number, markdown_status_col, "empty")
            save_workbook(workbook, excel_path)
            continue

        try:
            downloaded = fetch_webpage(link)
            markdown = extract_markdown(downloaded, link) if downloaded else None
            status = validate_markdown_result(downloaded, markdown)

            if status == "failed":
                update_markdown_path(worksheet, row_number, markdown_path_col, "")
                update_markdown_status(worksheet, row_number, markdown_status_col, "failed")
                save_workbook(workbook, excel_path)
                continue

            if status == "empty":
                update_markdown_path(worksheet, row_number, markdown_path_col, "")
                update_markdown_status(worksheet, row_number, markdown_status_col, "empty")
                save_workbook(workbook, excel_path)
                continue

            # Use article name from the URL path as file name.
            article_slug = get_article_slug(link)
            markdown_file_path = save_markdown_file(
                markdown=markdown,
                site_markdown_dir=site_markdown_dir,
                article_slug=article_slug,
                row_number=row_number,
            )

            update_markdown_path(
                worksheet,
                row_number,
                markdown_path_col,
                to_relative_path(markdown_file_path),
            )
            update_markdown_status(worksheet, row_number, markdown_status_col, "success")

        except Exception:
            update_markdown_path(worksheet, row_number, markdown_path_col, "")
            update_markdown_status(worksheet, row_number, markdown_status_col, "failed")

        # Save after every row so partial progress is never lost.
        save_workbook(workbook, excel_path)

    workbook.close()
    return {"excel_file_path": str(excel_path.resolve())}
