# final_markdown/

The curated newsletter for each site, at `final_markdown/{site}/{site}_final.md`.

Only articles that the semantic router selected (similarity_score > 70) are
included. The `compose_final_markdown` node turns each long article into a
**3–5 bullet summary** preserving facts, figures, and image URLs.

The shape per article is:

```markdown
## <Article title>

Source URL: <https://...>

- Bullet 1
- Bullet 2
- ...

![](https://image-url-if-any.jpg)
```

A real run typically produces 5–20 articles per site. See
[motortrend/motortrend_final.md](motortrend/motortrend_final.md) for an
example showing the header + the first two articles.
