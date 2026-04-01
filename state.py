from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    # Input values
    base_url: str
    cutoff_date: str
    user_need: str

    # File paths created by nodes
    xml_file_path: str
    excel_file_path: str
