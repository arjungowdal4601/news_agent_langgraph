import os
from pathlib import Path
import re


# ---------------------------
# Project folders
# ---------------------------
OUTPUT_DIR = Path("output")
DOWNLOAD_DIR = OUTPUT_DIR / "download_xml"
EXCEL_DIR = OUTPUT_DIR / "extracted_urls"
MARKDOWN_DIR = OUTPUT_DIR / "scraped_markdown"
FINAL_MARKDOWN_DIR = OUTPUT_DIR / "final_markdown"
GRAPH_OUTPUT_DIR = OUTPUT_DIR / "langgraph_diagrams"
HTML_OUTPUT_DIR = OUTPUT_DIR / "html_reports"
HTML_REPORT_FILE = HTML_OUTPUT_DIR / "combined_newsletter.html"
SITEMAP_AUDIT_DIR = OUTPUT_DIR / "sitemap_audit"
SITEMAP_EXTRACTOR_DIR = Path("configs/sitemap_extractors")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
FINAL_MARKDOWN_BATCH_SIZE = 5
DEFAULT_CUTOFF_DATE = "2026-04-10"

# Imports allowed inside generated sitemap extractor scripts. Any other import
# is rejected by the AST scan in services/sitemap_extractor_agent_service.py.
SITEMAP_EXTRACTOR_WHITELIST = (
    "xml.etree.ElementTree",
    "gzip",
    "re",
    "datetime",
    "urllib.parse",
)

# When set to a truthy value the extractor agent regenerates the cached script
# even if the inspection sample hash matches.
SITEMAP_EXTRACTOR_FORCE_REGENERATE = bool(os.getenv("REGENERATE_EXTRACTORS", ""))

# Hard time bound for executing a generated extractor (seconds).
SITEMAP_EXTRACTOR_TIMEOUT_SECONDS = 120
SITE_URLS = [
    "https://www.motortrend.com/",
    "https://www.autonews.com/",
    "https://www.spglobal.com/automotive-insights/en",
    "https://www.automotiveworld.com/",
]


# The semantic router model name is configured from environment variables so it
# can be changed in a local .env file without editing Python code.
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
