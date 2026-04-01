from pathlib import Path

from constants import FINAL_MARKDOWN_BATCH_SIZE, FINAL_MARKDOWN_DIR
from services.excel_service import (
    ensure_columns,
    load_workbook,
    save_workbook,
    update_final_markdown_path,
    update_final_markdown_status,
)
from services.final_markdown_service import (
    append_article_sections,
    compose_final_markdown_batch,
    extract_frontmatter_value,
    format_final_article_section,
    initialize_final_markdown_file,
)
from services.path_service import get_site_name, to_relative_path
from services.semantic_router_service import read_markdown_file, resolve_markdown_path
from state import PipelineState


def _compose_batch_with_retry(batch_inputs: list[dict], attempts: int = 2):
    """Retry a batch-level composition call before falling back to single articles."""
    last_error = None

    for _ in range(attempts):
        try:
            return compose_final_markdown_batch(batch_inputs)
        except Exception as error:  # pragma: no cover - exercised through fallback tests
            last_error = error

    if last_error is not None:
        raise last_error

    raise RuntimeError("Batch composition failed without raising an error.")


def _append_successful_batch(
    worksheet,
    batch_rows: list[dict],
    batch_results,
    final_markdown_path: Path,
    final_markdown_relative_path: str,
    final_markdown_path_col: int,
    final_markdown_status_col: int,
) -> None:
    """Append one successful batch and update workbook rows."""
    sections = [format_final_article_section(result) for result in batch_results]
    append_article_sections(final_markdown_path, sections)

    for row_data in batch_rows:
        update_final_markdown_path(
            worksheet,
            row_data["row_number"],
            final_markdown_path_col,
            final_markdown_relative_path,
        )
        update_final_markdown_status(
            worksheet,
            row_data["row_number"],
            final_markdown_status_col,
            "appended",
        )


def _process_batch(
    worksheet,
    workbook,
    excel_path: Path,
    batch_rows: list[dict],
    final_markdown_path: Path,
    final_markdown_relative_path: str,
    final_markdown_path_col: int,
    final_markdown_status_col: int,
) -> None:
    """Compose a batch, then fall back to one-article calls if needed."""
    if not batch_rows:
        return

    batch_inputs = [
        {
            "source_url": row_data["source_url"],
            "title_hint": row_data["title_hint"],
            "markdown_content": row_data["markdown_content"],
        }
        for row_data in batch_rows
    ]

    try:
        batch_results = _compose_batch_with_retry(batch_inputs)
        _append_successful_batch(
            worksheet,
            batch_rows,
            batch_results,
            final_markdown_path,
            final_markdown_relative_path,
            final_markdown_path_col,
            final_markdown_status_col,
        )
        save_workbook(workbook, excel_path)
        return
    except Exception:
        pass

    for row_data in batch_rows:
        single_input = [
            {
                "source_url": row_data["source_url"],
                "title_hint": row_data["title_hint"],
                "markdown_content": row_data["markdown_content"],
            }
        ]

        try:
            single_result = compose_final_markdown_batch(single_input)
            _append_successful_batch(
                worksheet,
                [row_data],
                single_result,
                final_markdown_path,
                final_markdown_relative_path,
                final_markdown_path_col,
                final_markdown_status_col,
            )
        except Exception:
            update_final_markdown_path(
                worksheet,
                row_data["row_number"],
                final_markdown_path_col,
                "",
            )
            update_final_markdown_status(
                worksheet,
                row_data["row_number"],
                final_markdown_status_col,
                "error",
            )

        save_workbook(workbook, excel_path)


# ---------------------------
# Node 5: Compose final newsletter markdown from selected articles
# ---------------------------
def compose_final_markdown(state: PipelineState) -> dict:
    """Compose selected article markdown files into one final newsletter file."""
    excel_path = Path(state["excel_file_path"])
    site_name = get_site_name(state["base_url"])

    site_final_markdown_dir = FINAL_MARKDOWN_DIR / site_name
    final_markdown_path = site_final_markdown_dir / f"{site_name}_final.md"
    initialize_final_markdown_file(final_markdown_path, site_name)
    final_markdown_relative_path = to_relative_path(final_markdown_path)

    workbook = load_workbook(excel_path)
    worksheet = workbook.active

    header_map = ensure_columns(
        worksheet,
        ["final_markdown_path", "final_markdown_status"],
    )

    link_col = header_map["link"]
    markdown_path_col = header_map["markdown_path"]
    semantic_status_col = header_map["semantic_status"]
    final_markdown_path_col = header_map["final_markdown_path"]
    final_markdown_status_col = header_map["final_markdown_status"]

    batch_rows: list[dict] = []

    for row_number in range(2, worksheet.max_row + 1):
        source_url = str(worksheet.cell(row=row_number, column=link_col).value or "").strip()
        semantic_status = str(
            worksheet.cell(row=row_number, column=semantic_status_col).value or ""
        ).strip()

        if semantic_status != "selected":
            update_final_markdown_path(worksheet, row_number, final_markdown_path_col, "")
            update_final_markdown_status(
                worksheet,
                row_number,
                final_markdown_status_col,
                "skipped_not_selected",
            )
            save_workbook(workbook, excel_path)
            continue

        markdown_path = str(
            worksheet.cell(row=row_number, column=markdown_path_col).value or ""
        ).strip()

        if not markdown_path:
            update_final_markdown_path(worksheet, row_number, final_markdown_path_col, "")
            update_final_markdown_status(
                worksheet,
                row_number,
                final_markdown_status_col,
                "source_missing",
            )
            save_workbook(workbook, excel_path)
            continue

        markdown_file_path = resolve_markdown_path(markdown_path)

        if not markdown_file_path.exists():
            update_final_markdown_path(worksheet, row_number, final_markdown_path_col, "")
            update_final_markdown_status(
                worksheet,
                row_number,
                final_markdown_status_col,
                "source_missing",
            )
            save_workbook(workbook, excel_path)
            continue

        markdown_content = read_markdown_file(markdown_file_path)
        if not markdown_content.strip():
            update_final_markdown_path(worksheet, row_number, final_markdown_path_col, "")
            update_final_markdown_status(worksheet, row_number, final_markdown_status_col, "error")
            save_workbook(workbook, excel_path)
            continue

        batch_rows.append(
            {
                "row_number": row_number,
                "source_url": source_url,
                "title_hint": extract_frontmatter_value(markdown_content, "title"),
                "markdown_content": markdown_content,
            }
        )

        if len(batch_rows) == FINAL_MARKDOWN_BATCH_SIZE:
            _process_batch(
                worksheet,
                workbook,
                excel_path,
                batch_rows,
                final_markdown_path,
                final_markdown_relative_path,
                final_markdown_path_col,
                final_markdown_status_col,
            )
            batch_rows = []

    if batch_rows:
        _process_batch(
            worksheet,
            workbook,
            excel_path,
            batch_rows,
            final_markdown_path,
            final_markdown_relative_path,
            final_markdown_path_col,
            final_markdown_status_col,
        )

    workbook.close()
    return {
        "excel_file_path": str(excel_path.resolve()),
        "final_markdown_file_path": str(final_markdown_path.resolve()),
    }
