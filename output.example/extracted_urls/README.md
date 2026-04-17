# extracted_urls/

One Excel workbook per site at `extracted_urls/{site}/{site}_urls.xlsx`.

The workbook is the **tracking table** for the whole pipeline. Each row is
one URL discovered from the sitemap. Stages later in the pipeline fill in
additional columns as they go, so this file is updated repeatedly.

## Schema

| Column | Filled by | Meaning |
|---|---|---|
| `link` | `extract_urls_to_excel` | Article URL discovered from the sitemap |
| `lastmod` | `extract_urls_to_excel` | `<lastmod>` from the sitemap (ISO timestamp), or empty |
| `markdown_path` | `download_markdown_from_excel` | Relative path to the saved markdown file (or blank if scraping failed) |
| `markdown_status` | `download_markdown_from_excel` | `success` / `failed` / `empty` / `published_before_cutoff` / `published_date_missing` |
| `similarity_score` | `semantic_router_from_excel` | LLM relevance score 0–100 |
| `semantic_status` | `semantic_router_from_excel` | `selected` / `not_selected` |
| `semantic_reason` | `semantic_router_from_excel` | One short sentence explaining the decision |
| `final_markdown_path` | `compose_final_markdown` | Path to the per-site final markdown if the article was included |
| `final_markdown_status` | `compose_final_markdown` | `included` / `skipped_not_selected` / `error` |

See [motortrend/sample_rows.csv](motortrend/sample_rows.csv) for two real example rows
in CSV form (the actual file on disk is .xlsx).
