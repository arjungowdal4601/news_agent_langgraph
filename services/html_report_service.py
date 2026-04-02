from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.runnables.graph import MermaidDrawMethod
from langchain_core.runnables.graph_mermaid import draw_mermaid_png

from constants import FINAL_MARKDOWN_DIR, GRAPH_OUTPUT_DIR, HTML_OUTPUT_DIR, HTML_REPORT_FILE, SITE_URLS
from services.path_service import get_site_name, make_safe_slug

MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MARKDOWN_IMAGE_RE = re.compile(r"!\[(.*?)\]\(([^)]+)\)")
SOURCE_URL_RE = re.compile(r"^Source URL:\s*<([^>]+)>\s*$", re.IGNORECASE)
SOURCE_LINE_RE = re.compile(r"^Source:\s*(.+)$", re.IGNORECASE)
MARKDOWN_BOLD_STAR_RE = re.compile(r"\*\*(.+?)\*\*")
MARKDOWN_BOLD_UNDERSCORE_RE = re.compile(r"__(.+?)__")
MARKDOWN_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?![\s*])(.+?)(?<![\s*])\*(?!\*)")
MARKDOWN_ITALIC_UNDERSCORE_RE = re.compile(r"(?<![\w_])_(?![\s_])(.+?)(?<![\s_])_(?![\w_])")

DEFAULT_HTML_GRAPH_MERMAID = """flowchart TD
    START([START]) --> collect_final_markdowns([collect_final_markdowns])
    collect_final_markdowns --> parse_newsletters([parse_newsletters])
    parse_newsletters --> render_html_report([render_html_report])
    render_html_report --> save_html_report([save_html_report])
    save_html_report --> END([END])
"""


def _render_inline_markdown(text: str) -> str:
    """Render supported inline markdown into safe HTML."""

    def apply_emphasis(value: str) -> str:
        rendered = value

        patterns = [
            (MARKDOWN_BOLD_STAR_RE, "strong"),
            (MARKDOWN_BOLD_UNDERSCORE_RE, "strong"),
            (MARKDOWN_ITALIC_STAR_RE, "em"),
            (MARKDOWN_ITALIC_UNDERSCORE_RE, "em"),
        ]

        changed = True
        while changed:
            changed = False
            for pattern, tag in patterns:
                def replacement(match) -> str:
                    inner = apply_emphasis(match.group(1))
                    return f"<{tag}>{inner}</{tag}>"

                rendered, count = pattern.subn(replacement, rendered)
                if count:
                    changed = True

        return rendered

    placeholders: dict[str, str] = {}

    def replace_link(match: re.Match[str]) -> str:
        token = f"@@CODXLINK{len(placeholders)}@@"
        label_html = apply_emphasis(html.escape(match.group(1).strip()))
        href = html.escape(match.group(2).strip(), quote=True)
        placeholders[token] = (
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label_html}</a>'
        )
        return token

    tokenized_text = MARKDOWN_LINK_RE.sub(replace_link, text)
    rendered = apply_emphasis(html.escape(tokenized_text))

    for token, link_html in placeholders.items():
        rendered = rendered.replace(token, link_html)

    return rendered


def _site_order_map() -> dict[str, int]:
    """Map configured site names to their desired output order."""
    return {get_site_name(url): index for index, url in enumerate(SITE_URLS)}


def _newsletter_sort_key(path: Path) -> tuple[int, str]:
    """Sort final markdown files by configured site order, then by folder name."""
    site_name = path.parent.name
    order_map = _site_order_map()
    return (order_map.get(site_name, len(order_map)), site_name)


def collect_final_markdowns(_: dict | None = None) -> dict:
    """Discover generated final markdown files to include in the HTML report."""
    markdown_paths = sorted(
        FINAL_MARKDOWN_DIR.glob("*/*_final.md"),
        key=_newsletter_sort_key,
    )

    if not markdown_paths:
        raise ValueError(
            "No final markdown files were found under final_markdown/. "
            "Run the content pipeline first before rendering the HTML report."
        )

    return {"markdown_file_paths": [str(path.resolve()) for path in markdown_paths]}


def _parse_article_section(title: str, lines: list[str]) -> dict[str, Any]:
    """Parse one article section from the controlled newsletter markdown format."""
    source_url = ""
    bullets: list[str] = []
    images: list[dict[str, str]] = []
    source_lines: list[str] = []
    current_bullet_index: int | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not stripped:
            continue

        source_url_match = SOURCE_URL_RE.match(stripped)
        if source_url_match:
            source_url = source_url_match.group(1).strip()
            continue

        image_match = MARKDOWN_IMAGE_RE.match(stripped)
        if image_match:
            images.append(
                {
                    "alt": image_match.group(1).strip(),
                    "url": image_match.group(2).strip(),
                }
            )
            continue

        source_line_match = SOURCE_LINE_RE.match(stripped)
        if source_line_match:
            source_lines.append(source_line_match.group(1).strip())
            continue

        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
            current_bullet_index = len(bullets) - 1
            continue

        if line.startswith("  ") and current_bullet_index is not None:
            bullets[current_bullet_index] = (
                f"{bullets[current_bullet_index]} {stripped}".strip()
            )

    return {
        "title": title.strip(),
        "source_url": source_url,
        "bullets": bullets,
        "images": images,
        "source_lines": source_lines,
    }


def _parse_newsletter_file(markdown_path: Path) -> dict[str, Any]:
    """Parse one final newsletter markdown file into structured data."""
    content = markdown_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    title = markdown_path.stem.replace("_", " ").strip().title()
    generated_date = ""
    sections: list[dict[str, Any]] = []

    current_title = ""
    current_lines: list[str] = []

    for raw_line in lines:
        stripped = raw_line.strip()

        if raw_line.startswith("# ") and not title:
            title = raw_line[2:].strip()
            continue
        if raw_line.startswith("# "):
            title = raw_line[2:].strip()
            continue

        if stripped.startswith("Generated:"):
            generated_date = stripped.split(":", 1)[1].strip()
            continue

        if raw_line.startswith("## "):
            if current_title:
                sections.append(_parse_article_section(current_title, current_lines))
            current_title = raw_line[3:].strip()
            current_lines = []
            continue

        if current_title:
            current_lines.append(raw_line)

    if current_title:
        sections.append(_parse_article_section(current_title, current_lines))

    site_name = markdown_path.parent.name
    site_anchor = make_safe_slug(site_name, "site")

    return {
        "site_name": site_name,
        "site_title": title,
        "site_anchor": site_anchor,
        "generated_date": generated_date,
        "markdown_file_path": str(markdown_path.resolve()),
        "articles": sections,
    }


def parse_newsletters(state: dict) -> dict:
    """Parse discovered final markdown newsletters into structured data."""
    markdown_paths = [Path(path) for path in state.get("markdown_file_paths", [])]
    newsletters = [_parse_newsletter_file(path) for path in markdown_paths]

    if not newsletters:
        raise ValueError("No newsletters could be parsed from the collected markdown files.")

    return {"newsletters": newsletters}


def _render_site_nav(newsletters: list[dict[str, Any]]) -> str:
    """Render the top navigation links for all site sections."""
    links = []
    for newsletter in newsletters:
        label = html.escape(newsletter["site_name"].replace("-", " ").title())
        anchor = html.escape(newsletter["site_anchor"], quote=True)
        links.append(f'<a class="site-pill" href="#{anchor}">{label}</a>')
    return "\n".join(links)


def _render_article_card(article: dict[str, Any]) -> str:
    """Render a single article card into HTML."""
    title = _render_inline_markdown(article["title"])
    source_url = html.escape(article["source_url"], quote=True)
    bullet_items = "\n".join(
        f"<li>{_render_inline_markdown(bullet)}</li>" for bullet in article["bullets"]
    )
    gallery_items: list[str] = []
    images = article["images"]

    for index, image in enumerate(images):
        figure_classes = ["article-gallery-item"]
        if len(images) == 1 or (len(images) % 2 == 1 and index == len(images) - 1):
            figure_classes.append("article-gallery-item--full")

        gallery_items.append(
            (
                f'<figure class="{" ".join(figure_classes)}">'
                f'<img src="{html.escape(image["url"], quote=True)}" '
                f'alt="{html.escape(image["alt"], quote=True)}" loading="lazy">'
                "</figure>"
            )
        )

    gallery_block = ""
    if gallery_items:
        gallery_classes = ["article-gallery"]
        if len(images) == 1:
            gallery_classes.append("article-gallery--single")
        gallery_block = (
            f'<div class="{" ".join(gallery_classes)}">'
            + "".join(gallery_items)
            + "</div>"
        )

    source_lines = "\n".join(
        f'<p class="article-source-meta">Source: {_render_inline_markdown(line)}</p>'
        for line in article["source_lines"]
    )

    source_button = ""
    if source_url:
        source_button = (
            f'<a class="source-button" href="{source_url}" '
            'target="_blank" rel="noopener noreferrer">Open Source</a>'
        )

    return f"""
<article class="article-card">
  <div class="article-header">
    <h3>{title}</h3>
    {source_button}
  </div>
  {gallery_block}
  <div class="article-copy">
    <ul class="article-bullets">
      {bullet_items}
    </ul>
    {source_lines}
  </div>
</article>
""".strip()


def _render_site_section(newsletter: dict[str, Any]) -> str:
    """Render one site newsletter section."""
    site_title = html.escape(newsletter["site_title"])
    site_anchor = html.escape(newsletter["site_anchor"], quote=True)
    generated_date = html.escape(newsletter["generated_date"] or "Unknown")
    article_count = len(newsletter["articles"])
    article_cards = "\n".join(_render_article_card(article) for article in newsletter["articles"])

    return f"""
<section class="site-section" id="{site_anchor}">
  <div class="site-header">
    <div>
      <p class="site-kicker">{html.escape(newsletter["site_name"].replace("-", " ").title())}</p>
      <h2>{site_title}</h2>
    </div>
    <div class="site-meta">
      <span>{article_count} articles</span>
      <span>Generated {generated_date}</span>
    </div>
  </div>
  <div class="article-stack">
    {article_cards}
  </div>
</section>
""".strip()


def render_html_report(state: dict) -> dict:
    """Render the combined HTML newsletter page from parsed newsletters."""
    newsletters = state.get("newsletters", [])
    if not newsletters:
        raise ValueError("No parsed newsletters were available for HTML rendering.")

    rendered_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_articles = sum(len(newsletter["articles"]) for newsletter in newsletters)
    site_nav = _render_site_nav(newsletters)
    site_sections = "\n".join(_render_site_section(newsletter) for newsletter in newsletters)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Combined Newsletter Report</title>
  <style>
    :root {{
      --bg: #f4efe7;
      --surface: #fffdfa;
      --surface-alt: #f7f2ea;
      --line: #d9cfc3;
      --text: #1e1c19;
      --muted: #655d53;
      --accent: #0a5c5a;
      --accent-strong: #0a3f3e;
      --shadow: 0 18px 50px rgba(18, 20, 18, 0.08);
      --radius-lg: 28px;
      --radius-md: 20px;
      --radius-sm: 14px;
      --max-width: 1120px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(10, 92, 90, 0.12), transparent 28%),
        linear-gradient(180deg, #f7f2ea 0%, #f4efe7 45%, #efe8df 100%);
    }}
    a {{ color: var(--accent-strong); }}
    .page-shell {{
      width: min(var(--max-width), calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(10, 92, 90, 0.94), rgba(10, 63, 62, 0.96));
      color: #f5f4ef;
      border-radius: 32px;
      padding: 32px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }}
    .hero-eyebrow {{
      margin: 0 0 12px;
      font-size: 0.85rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      opacity: 0.78;
    }}
    .hero h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.4rem);
      line-height: 1.02;
      max-width: 12ch;
    }}
    .hero-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
      color: rgba(245, 244, 239, 0.88);
      font-size: 0.96rem;
    }}
    .hero-meta span {{
      padding: 10px 14px;
      background: rgba(255, 255, 255, 0.12);
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
    }}
    .site-nav {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      padding: 16px 0 18px;
      backdrop-filter: blur(14px);
    }}
    .site-pill {{
      text-decoration: none;
      padding: 10px 16px;
      border-radius: 999px;
      background: rgba(255, 253, 250, 0.92);
      border: 1px solid rgba(217, 207, 195, 0.92);
      color: var(--accent-strong);
      font-weight: 600;
      box-shadow: 0 8px 24px rgba(18, 20, 18, 0.06);
    }}
    .content-stack {{
      display: grid;
      gap: 24px;
      margin-top: 8px;
    }}
    .site-section {{
      background: rgba(255, 253, 250, 0.94);
      border: 1px solid rgba(217, 207, 195, 0.9);
      border-radius: var(--radius-lg);
      padding: 26px;
      box-shadow: var(--shadow);
    }}
    .site-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 18px;
      margin-bottom: 22px;
      flex-wrap: wrap;
    }}
    .site-kicker {{
      margin: 0 0 8px;
      color: var(--accent);
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }}
    .site-header h2 {{
      margin: 0;
      font-size: clamp(1.5rem, 3vw, 2.2rem);
      line-height: 1.1;
    }}
    .site-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .site-meta span {{
      background: var(--surface-alt);
      border-radius: 999px;
      padding: 8px 12px;
    }}
    .article-stack {{
      display: grid;
      gap: 20px;
    }}
    .article-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-md);
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 18px;
      min-height: 100%;
    }}
    .article-header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 14px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(217, 207, 195, 0.72);
    }}
    .article-header h3 {{
      margin: 0;
      font-size: clamp(1.28rem, 2.2vw, 1.6rem);
      line-height: 1.14;
      max-width: 32ch;
    }}
    .article-copy {{
      min-width: 0;
    }}
    .source-button {{
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      background: var(--accent);
      color: #ffffff;
      padding: 10px 14px;
      border-radius: 999px;
      font-size: 0.88rem;
      font-weight: 700;
      min-width: 112px;
    }}
    .article-gallery {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .article-gallery--single {{
      grid-template-columns: minmax(0, 1fr);
    }}
    .article-gallery-item {{
      margin: 0;
      border-radius: var(--radius-sm);
      overflow: hidden;
      background: var(--surface-alt);
      border: 1px solid var(--line);
    }}
    .article-gallery-item--full {{
      grid-column: 1 / -1;
    }}
    .article-gallery-item img {{
      display: block;
      width: 100%;
      height: auto;
      object-fit: cover;
      aspect-ratio: 16 / 9;
    }}
    .article-bullets {{
      margin: 0;
      padding-left: 20px;
      display: grid;
      gap: 12px;
      line-height: 1.66;
    }}
    .article-bullets li {{
      max-width: none;
    }}
    .article-bullets strong {{
      font-weight: 700;
      color: var(--accent-strong);
    }}
    .article-bullets em,
    .article-source-meta em {{
      font-style: italic;
    }}
    .article-source-meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.45;
      padding-top: 4px;
      border-top: 1px dashed var(--line);
    }}
    @media (max-width: 768px) {{
      .page-shell {{ width: min(var(--max-width), calc(100% - 20px)); }}
      .hero {{ padding: 24px; border-radius: 24px; }}
      .site-section {{ padding: 18px; border-radius: 24px; }}
      .article-card {{ padding: 16px; }}
      .article-gallery {{
        grid-template-columns: 1fr;
      }}
      .article-header {{
        flex-direction: column;
        align-items: stretch;
      }}
      .source-button {{ width: 100%; }}
      .site-nav {{
        position: static;
        padding-top: 12px;
      }}
    }}
  </style>
</head>
<body>
  <main class="page-shell">
    <section class="hero">
      <p class="hero-eyebrow">Newsletter Report</p>
      <h1>Combined Engineering News Brief</h1>
      <div class="hero-meta">
        <span>Rendered {html.escape(rendered_at)}</span>
        <span>{len(newsletters)} site newsletters</span>
        <span>{total_articles} total articles</span>
      </div>
    </section>
    <nav class="site-nav" aria-label="Site navigation">
      {site_nav}
    </nav>
    <div class="content-stack">
      {site_sections}
    </div>
  </main>
</body>
</html>
"""

    return {"html_content": html_content}


def save_html_report(state: dict) -> dict:
    """Persist the rendered combined HTML report to disk."""
    html_content = state.get("html_content", "")
    if not html_content.strip():
        raise ValueError("HTML content was empty, so the report file was not written.")

    HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_REPORT_FILE.write_text(html_content, encoding="utf-8")
    return {"html_file_path": str(HTML_REPORT_FILE.resolve())}


def get_html_graph_mermaid_text(graph: Any) -> str:
    """Return Mermaid text for the HTML app graph, or a deterministic fallback."""
    try:
        graph_view = graph.get_graph()
        draw_mermaid = getattr(graph_view, "draw_mermaid", None)
        if callable(draw_mermaid):
            mermaid_text = draw_mermaid()
            if isinstance(mermaid_text, str) and mermaid_text.strip():
                return mermaid_text
    except Exception:
        pass

    return DEFAULT_HTML_GRAPH_MERMAID


def save_html_app_graph_diagram(graph: Any) -> str:
    """Save the HTML app LangGraph diagram as a PNG file."""
    GRAPH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    diagram_path = GRAPH_OUTPUT_DIR / "html_report_graph.png"

    try:
        graph.get_graph().draw_mermaid_png(
            output_file_path=str(diagram_path),
            draw_method=MermaidDrawMethod.API,
            background_color="white",
        )
    except Exception:
        draw_mermaid_png(
            get_html_graph_mermaid_text(graph),
            output_file_path=str(diagram_path),
            draw_method=MermaidDrawMethod.API,
            background_color="white",
        )

    return str(diagram_path.resolve())
