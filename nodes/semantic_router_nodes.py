from pathlib import Path

from services.excel_service import (
    ensure_columns,
    load_workbook,
    save_workbook,
    update_semantic_reason,
    update_semantic_status,
    update_similarity_score,
)
from services.semantic_router_service import read_markdown_file, resolve_markdown_path, route_markdown
from state import PipelineState


# ---------------------------
# Node 4: Route markdown rows with an LLM and update Excel
# ---------------------------
def semantic_router_from_excel(state: PipelineState) -> dict:
    """Read markdown files from Excel, judge their relevance, and save the result.

    This node reads the markdown_path for each row, opens the markdown file,
    compares it with the user need, and writes similarity score, status,
    and short reason back into the Excel workbook.
    """
    excel_path = Path(state["excel_file_path"])
    user_need = state["user_need"]

    workbook = load_workbook(excel_path)
    worksheet = workbook.active

    # Make sure semantic routing columns exist before row processing starts.
    header_map = ensure_columns(
        worksheet,
        ["similarity_score", "semantic_status", "semantic_reason"],
    )

    link_col = header_map["link"]
    markdown_path_col = header_map["markdown_path"]
    similarity_score_col = header_map["similarity_score"]
    semantic_status_col = header_map["semantic_status"]
    semantic_reason_col = header_map["semantic_reason"]

    for row_number in range(2, worksheet.max_row + 1):
        try:
            source_url = str(worksheet.cell(row=row_number, column=link_col).value or "").strip()
            markdown_path = str(
                worksheet.cell(row=row_number, column=markdown_path_col).value or ""
            ).strip()

            if not markdown_path:
                update_similarity_score(worksheet, row_number, similarity_score_col, "")
                update_semantic_status(worksheet, row_number, semantic_status_col, "source_missing")
                update_semantic_reason(
                    worksheet,
                    row_number,
                    semantic_reason_col,
                    "Markdown path is missing.",
                )
                save_workbook(workbook, excel_path)
                continue

            markdown_file_path = resolve_markdown_path(markdown_path)

            if not markdown_file_path.exists():
                update_similarity_score(worksheet, row_number, similarity_score_col, "")
                update_semantic_status(worksheet, row_number, semantic_status_col, "source_missing")
                update_semantic_reason(
                    worksheet,
                    row_number,
                    semantic_reason_col,
                    "Markdown file was not found.",
                )
                save_workbook(workbook, excel_path)
                continue

            markdown_content = read_markdown_file(markdown_file_path)

            if not markdown_content.strip():
                update_similarity_score(worksheet, row_number, similarity_score_col, "")
                update_semantic_status(worksheet, row_number, semantic_status_col, "empty_markdown")
                update_semantic_reason(
                    worksheet,
                    row_number,
                    semantic_reason_col,
                    "Markdown file is empty.",
                )
                save_workbook(workbook, excel_path)
                continue

            router_result = route_markdown(
                user_need=user_need,
                source_url=source_url,
                markdown_content=markdown_content,
            )

            semantic_status = "selected" if router_result.selected else "not_selected"

            update_similarity_score(
                worksheet,
                row_number,
                similarity_score_col,
                router_result.similarity_score,
            )
            update_semantic_status(worksheet, row_number, semantic_status_col, semantic_status)
            update_semantic_reason(
                worksheet,
                row_number,
                semantic_reason_col,
                router_result.reason,
            )

        except Exception:
            update_similarity_score(worksheet, row_number, similarity_score_col, "")
            update_semantic_status(worksheet, row_number, semantic_status_col, "error")
            update_semantic_reason(
                worksheet,
                row_number,
                semantic_reason_col,
                "Semantic routing failed.",
            )

        # Save after every row so partial progress is never lost.
        save_workbook(workbook, excel_path)

    workbook.close()
    return {"excel_file_path": str(excel_path.resolve())}
