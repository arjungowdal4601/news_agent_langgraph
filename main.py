from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from prompts.semantic_router_prompts import USER_NEED

# Load variables from a .env file in the project root before importing the
# rest of the project. This keeps local API keys and model settings out of code.
load_dotenv()

from nodes.markdown_nodes import download_markdown_from_excel
from nodes.semantic_router_nodes import semantic_router_from_excel
from nodes.sitemap_nodes import download_xml, extract_urls_to_excel
from state import PipelineState

builder = StateGraph(PipelineState)

# Add nodes.
builder.add_node("download_xml", download_xml)
builder.add_node("extract_urls_to_excel", extract_urls_to_excel)
builder.add_node("download_markdown_from_excel", download_markdown_from_excel)
builder.add_node("semantic_router_from_excel", semantic_router_from_excel)

# Run everything sequentially.
builder.add_edge(START, "download_xml")
builder.add_edge("download_xml", "extract_urls_to_excel")
builder.add_edge("extract_urls_to_excel", "download_markdown_from_excel")
builder.add_edge("download_markdown_from_excel", "semantic_router_from_excel")
builder.add_edge("semantic_router_from_excel", END)

graph = builder.compile()

if __name__ == "__main__":
    result = graph.invoke(
        {
            "base_url": "https://www.automotiveworld.com/",
            "cutoff_date": "2026-03-28",
            "user_need": USER_NEED,
        }
    )

    print("Downloaded XML:", result["xml_file_path"])
    print("Excel file:", result["excel_file_path"])