from typing import Any, Iterable

from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables.graph_mermaid import draw_mermaid_png

from constants import GRAPH_OUTPUT_DIR
from services.path_service import get_site_name

DEFAULT_GRAPH_MERMAID = """flowchart TD
    START([START]) --> download_xml([download_xml])
    download_xml --> extract_urls_to_excel([extract_urls_to_excel])
    extract_urls_to_excel --> download_markdown_from_excel([download_markdown_from_excel])
    download_markdown_from_excel --> semantic_router_from_excel([semantic_router_from_excel])
    semantic_router_from_excel --> compose_final_markdown([compose_final_markdown])
    compose_final_markdown --> END([END])
"""


def get_graph_mermaid_text(graph: Any) -> str:
    """Return Mermaid text for the compiled LangGraph, or a deterministic fallback."""
    try:
        graph_view = graph.get_graph()
        draw_mermaid = getattr(graph_view, "draw_mermaid", None)
        if callable(draw_mermaid):
            mermaid_text = draw_mermaid()
            if isinstance(mermaid_text, str) and mermaid_text.strip():
                return mermaid_text
    except Exception:
        pass

    return DEFAULT_GRAPH_MERMAID


def save_langgraph_diagram(graph: Any, site_name: str) -> str:
    """Save a PNG flow diagram for the current LangGraph pipeline."""
    GRAPH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    diagram_path = GRAPH_OUTPUT_DIR / f"{site_name}_langgraph_flow.png"

    try:
        graph.get_graph().draw_mermaid_png(
            output_file_path=str(diagram_path),
            draw_method=MermaidDrawMethod.API,
            background_color="white",
        )
    except Exception:
        draw_mermaid_png(
            get_graph_mermaid_text(graph),
            output_file_path=str(diagram_path),
            draw_method=MermaidDrawMethod.API,
            background_color="white",
        )

    return str(diagram_path.resolve())


def run_site(graph: Any, base_url: str, cutoff_date: str, user_need: str) -> dict:
    """Run the single-site graph once and save the flow diagram artifact."""
    result = graph.invoke(
        {
            "base_url": base_url,
            "cutoff_date": cutoff_date,
            "user_need": user_need,
        }
    )

    site_name = get_site_name(base_url)
    diagram_file_path = save_langgraph_diagram(graph, site_name)
    result["diagram_file_path"] = diagram_file_path
    return result


def run_all_sites(
    graph: Any, site_urls: Iterable[str], cutoff_date: str, user_need: str
) -> None:
    """Run the site pipeline sequentially for every configured site."""
    completed_sites: list[str] = []
    failed_sites: list[str] = []

    for base_url in site_urls:
        site_name = get_site_name(base_url)

        try:
            result = run_site(graph, base_url, cutoff_date, user_need)
            completed_sites.append(site_name)

            print(f"\nSite: {site_name}")
            print("Downloaded XML:", result["xml_file_path"])
            print("Excel file:", result["excel_file_path"])
            print("Final markdown:", result["final_markdown_file_path"])
            print("Graph diagram:", result["diagram_file_path"])
        except Exception as error:
            failed_sites.append(site_name)
            print(f"\nSite: {site_name}")
            print("Failed:", error)

    print("\nCompleted sites:")
    for site_name in completed_sites:
        print(f"- {site_name}")

    print("\nFailed sites:")
    for site_name in failed_sites:
        print(f"- {site_name}")
