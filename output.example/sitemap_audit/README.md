# sitemap_audit/

One JSON file per site at `sitemap_audit/{site}_cutoff_audit.json`.

Records what the URL extraction step (`extract_urls_to_excel`) saw and
filtered, plus metadata about the per-site extractor agent if one ran.

## Key fields

| Field | Meaning |
|---|---|
| `site_name`, `cutoff_date`, `top_sitemap_path` | Inputs to the run |
| `sitemapindex_nodes_traversed`, `urlset_nodes_traversed` | Walker counters |
| `child_sitemaps_seen`/`opened`/`skipped_before_cutoff` | Sitemap-index expansion stats |
| `child_sitemap_samples_opened_recent_lastmod` | Up to 10 child URLs that were opened |
| `child_sitemap_samples_skipped_before_cutoff` | Up to 10 child URLs that were skipped |
| `final_urls_seen`/`kept`/`skipped_before_cutoff` | Final-URL counts |
| `final_url_samples_skipped_before_cutoff` | Up to 10 example URLs that were dropped |
| `kept_min_lastmod`, `kept_max_lastmod` | Date range of URLs that survived |
| `extractor_source` | `cached` / `generated` / `regenerated` / `fallback` |
| `extractor_sample_hash`, `extractor_generation_model` | Provenance of the cached extractor |
| `extractor_runtime_ms`, `fetch_count` | Generated extractor performance |
| `extractor_failure_reason` | Empty when ok; non-empty when the agent path fell back to the walker |

See [motortrend_cutoff_audit.json](motortrend_cutoff_audit.json) for a real
example.
