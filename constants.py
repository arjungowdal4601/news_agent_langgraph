import os
from pathlib import Path
import re


# ---------------------------
# Project folders
# ---------------------------
DOWNLOAD_DIR = Path("download_xml")
EXCEL_DIR = Path("extracted_urls")
MARKDOWN_DIR = Path("scraped_markdown")
FINAL_MARKDOWN_DIR = Path("final_markdown")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
FINAL_MARKDOWN_BATCH_SIZE = 5

# The semantic router model name is configured from environment variables so it
# can be changed in a local .env file without editing Python code.
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    )
}
