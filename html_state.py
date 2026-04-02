from typing import Any

from typing_extensions import TypedDict


class HtmlReportState(TypedDict, total=False):
    markdown_file_paths: list[str]
    newsletters: list[dict[str, Any]]
    html_content: str
    html_file_path: str
