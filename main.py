from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# Load variables from a .env file in the project root before importing the
# rest of the project. This keeps local API keys and model settings out of code.
load_dotenv()

from constants import DEFAULT_CUTOFF_DATE, SITE_URLS
from nodes.final_markdown_nodes import compose_final_markdown
from nodes.markdown_nodes import download_markdown_from_excel
from nodes.semantic_router_nodes import semantic_router_from_excel
from nodes.sitemap_nodes import download_xml, extract_urls_to_excel
from prompts.semantic_router_prompts import USER_NEED
from services.pipeline_runner_service import run_all_sites
from state import PipelineState

builder = StateGraph(PipelineState)

builder.add_node("download_xml", download_xml)
builder.add_node("extract_urls_to_excel", extract_urls_to_excel)
builder.add_node("download_markdown_from_excel", download_markdown_from_excel)
builder.add_node("semantic_router_from_excel", semantic_router_from_excel)
builder.add_node("compose_final_markdown", compose_final_markdown)

builder.add_edge(START, "download_xml")
builder.add_edge("download_xml", "extract_urls_to_excel")
builder.add_edge("extract_urls_to_excel", "download_markdown_from_excel")
builder.add_edge("download_markdown_from_excel", "semantic_router_from_excel")
builder.add_edge("semantic_router_from_excel", "compose_final_markdown")
builder.add_edge("compose_final_markdown", END)

graph = builder.compile()


if __name__ == "__main__":
    run_all_sites(graph, SITE_URLS, DEFAULT_CUTOFF_DATE, USER_NEED)
