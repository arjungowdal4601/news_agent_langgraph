# scraped_markdown/

One markdown file per successfully scraped article, grouped by site:
`scraped_markdown/{site}/{article-slug}.md`.

Files are produced by Trafilatura via `download_markdown_from_excel`. Each
file has YAML frontmatter (title, author, url, date, categories, ...)
followed by the article body and an optional `Source:` attribution line at
the end.

A real run produces hundreds of these per site. See
[motortrend/example-article.md](motortrend/example-article.md) for one
representative file.
