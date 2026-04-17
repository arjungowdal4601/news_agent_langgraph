# Output layout (example)

The real `output/` folder is git-ignored. This `output.example/` folder is a
small, sanitized snapshot showing **what shape each artifact takes** so that
a new contributor can understand the pipeline without having to run it.

Every file in here is truncated to a representative sample — full runs are
much larger (tens of thousands of URLs per site, hundreds of scraped
articles, etc.).

## Folder map

```
output/
├── download_xml/                 # raw sitemap XML downloaded from each site
│   └── {site}.xml
├── extracted_urls/               # one Excel workbook per site (the "tracking table")
│   └── {site}/
│       └── {site}_urls.xlsx
├── scraped_markdown/             # per-article cleaned markdown (Trafilatura output)
│   └── {site}/
│       └── {article-slug}.md
├── final_markdown/               # curated newsletter (only "selected" articles, summarized)
│   └── {site}/
│       └── {site}_final.md
├── sitemap_audit/                # JSON stats for each site's URL extraction step
│   └── {site}_cutoff_audit.json
├── langgraph_diagrams/           # PNG flow diagrams of the LangGraph pipelines
│   ├── {site}_langgraph_flow.png
│   └── html_report_graph.png
└── html_reports/                 # final combined newsletter rendered as HTML
    └── combined_newsletter.html
```

## How the artifacts relate

The pipeline runs once per site (motortrend, autonews, spglobal, automotiveworld) and produces:

1. `download_xml/{site}.xml` — the top-level sitemap, fetched as-is.
2. `extracted_urls/{site}/{site}_urls.xlsx` — every recent URL discovered for that site, plus columns that the later stages fill in (markdown path, semantic score, final-markdown path).
3. `scraped_markdown/{site}/<slug>.md` — one cleaned markdown file per article that was successfully fetched.
4. `sitemap_audit/{site}_cutoff_audit.json` — counters and samples explaining what the URL extraction kept vs. skipped.
5. `final_markdown/{site}/{site}_final.md` — the curated newsletter for that site (only articles whose semantic score passed the threshold, rewritten as compact bullets).
6. `langgraph_diagrams/{site}_langgraph_flow.png` — the per-site graph; `html_report_graph.png` belongs to the separate HTML-report graph.
7. `html_reports/combined_newsletter.html` — built last by `app.py`, combining every `*_final.md` into one styled newsletter.

See the README inside each subfolder for a concrete example and field-by-field notes.
