from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

from html_state import HtmlReportState
from services.html_report_service import (
    collect_final_markdowns,
    parse_newsletters,
    render_html_report,
    save_html_app_graph_diagram,
    save_html_report,
)

builder = StateGraph(HtmlReportState)

builder.add_node("collect_final_markdowns", collect_final_markdowns)
builder.add_node("parse_newsletters", parse_newsletters)
builder.add_node("render_html_report", render_html_report)
builder.add_node("save_html_report", save_html_report)

builder.add_edge(START, "collect_final_markdowns")
builder.add_edge("collect_final_markdowns", "parse_newsletters")
builder.add_edge("parse_newsletters", "render_html_report")
builder.add_edge("render_html_report", "save_html_report")
builder.add_edge("save_html_report", END)

graph = builder.compile()


if __name__ == "__main__":
    result = graph.invoke({})
    diagram_file_path = save_html_app_graph_diagram(graph)

    print("HTML report:", result["html_file_path"])
    print("Graph diagram:", diagram_file_path)
