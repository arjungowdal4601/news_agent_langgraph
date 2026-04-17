# langgraph_diagrams/

PNG flow diagrams of the LangGraph pipelines, rendered from the compiled
`StateGraph` via Mermaid. Two kinds of files end up here:

- `{site}_langgraph_flow.png` — one per site, written by
  `pipeline_runner_service.run_all_sites()` after each site's run. Shows the
  per-site pipeline:

  ```
  START -> download_xml
        -> generate_sitemap_extractor
        -> extract_urls_to_excel
        -> download_markdown_from_excel
        -> semantic_router_from_excel
        -> compose_final_markdown
        -> END
  ```

- `html_report_graph.png` — written by `app.py`. Shows the (smaller) graph
  that assembles `final_markdown/*` into the combined HTML newsletter.

PNGs are not committed to this example folder to keep the repo light. Run
`python main.py` followed by `python app.py` to generate them.
