# html_reports/

Holds the final output of the HTML-report graph in `app.py`:

- `combined_newsletter.html` — a single self-contained HTML page with
  inline CSS that combines every `final_markdown/{site}/{site}_final.md`
  into one styled newsletter.

The page has:

- A header with run date and per-site article counts.
- The embedded LangGraph diagram (`langgraph_diagrams/html_report_graph.png`).
- One section per site (motortrend, autonews, ...), each containing the
  selected articles rendered from the per-site final markdown — title,
  source URL, bullet summary, and any image URLs preserved from the
  scraped article.

The HTML is large (a few hundred KB on a real run) so only this README is
checked in. Run `python app.py` to generate the actual file.
