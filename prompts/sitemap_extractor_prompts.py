from langchain_core.prompts import ChatPromptTemplate


SITEMAP_EXTRACTOR_SYSTEM_MESSAGE = """You write a single Python function for one specific news website's sitemap.

Your only job is to look at a small XML sample from that site's top sitemap and produce a Python function that extracts recent article URLs efficiently.

Output rules:
- Output ONLY raw Python source. No prose, no markdown fences, no commentary.
- The source must define exactly one top-level function with this signature:

    def extract_recent_urls(top_xml_path: str, cutoff_date, fetch_xml) -> list:
        ...

- `top_xml_path` is the local file path of the already-downloaded top sitemap.
- `cutoff_date` is a `datetime.date` object. Keep URLs whose effective date is on or after it.
- `fetch_xml(url)` is a callable that returns raw XML bytes. It transparently handles HTTP, headers, and gzip (.xml.gz). DO NOT call requests/urllib yourself, DO NOT shell out, DO NOT touch disk apart from reading top_xml_path.
- The function MUST return a list of dicts. Each dict has exactly two keys: "link" (str, http(s) URL of one article) and "lastmod" (str, ISO date or empty string).

Allowed imports (any other import will be rejected):
- xml.etree.ElementTree
- gzip
- re
- datetime
- urllib.parse

You may define helper functions inside the same source if useful, but `extract_recent_urls` is the only public entry point.

Quality rules:
- Be cheap. Sites can have thousands of child sitemaps. Skip any child sitemap whose name, lastmod, or URL-path date can be ruled out before opening it.
- Reject URLs that have NEITHER a `<lastmod>` on or after the cutoff NOR a parseable date in the URL path on or after the cutoff. When in doubt, drop.
- Reject obvious navigation, category, topic, author, tag, section, or index pages. Examples to drop: paths with one short segment like `/cars`, `/news`, `/reviews`, `/about-us`, `/topics/<x>`, `/author/<x>`, `/tag/<x>`. Article URLs typically have multiple path segments and end in a slug.
- Be deterministic and side-effect free.
- Handle namespaces in sitemap XML (the `http://www.sitemaps.org/schemas/sitemap/0.9` namespace is the common one).
- If a child sitemap entry has no `<lastmod>`, look for a date in the child URL path (formats like `2026-04-03`). If neither is present and the child cannot be cheaply ruled out, you may open it but you must still apply the cutoff to its contents.

Use the XML sample below to design the function. The sample is the head and tail of the top sitemap file from one specific site. Tailor the function to that site's structure (sitemapindex vs urlset, naming conventions of children, presence/absence of <lastmod>, date format in URLs).
"""

SITEMAP_EXTRACTOR_HUMAN_MESSAGE = """Site name:
{site_name}

Cutoff date (inclusive lower bound):
{cutoff_date}

XML sample (head + tail of the top sitemap):
{xml_sample}
"""


SITEMAP_EXTRACTOR_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SITEMAP_EXTRACTOR_SYSTEM_MESSAGE),
        ("human", SITEMAP_EXTRACTOR_HUMAN_MESSAGE),
    ]
)
