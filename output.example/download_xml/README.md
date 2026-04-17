# download_xml/

Raw top-level sitemap.xml, one file per site. The pipeline downloads
`{base_url}/sitemap.xml` and saves it byte-for-byte. These files are the
input to the per-site extractor agent and the recursive walker.

Two real shapes show up in practice:

## 1. Multi-line `sitemapindex` with `<lastmod>` (e.g. motortrend)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://www.motortrend.com/en/sitemaps/content.2025-09-18T08:05:12.xml.gz</loc>
        <lastmod>2026-04-16T23:40:10Z</lastmod>
    </sitemap>
    <sitemap>
        <loc>https://www.motortrend.com/en/sitemaps/vehicle-category.2025-09-23T20:50:05.xml.gz</loc>
        <lastmod>2026-04-16T19:50:10Z</lastmod>
    </sitemap>
    <!-- ... typically 5-15 child sitemaps, all .xml.gz ... -->
</sitemapindex>
```

The walker filters child sitemaps by `<lastmod>`, opens those at/after the
cutoff (gzip handled transparently), and walks the resulting `<urlset>`.

## 2. Minified single-line `sitemapindex` with NO `<lastmod>` (e.g. autonews)

```xml
<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://www.autonews.com/arc/outboundfeeds/sitemap/latest/?outputType=xml</loc></sitemap><sitemap><loc>https://www.autonews.com/arc/outboundfeeds/sitemap/2026-04-04/?outputType=xml</loc></sitemap><sitemap><loc>https://www.autonews.com/arc/outboundfeeds/sitemap2/2026-04-03/?outputType=xml</loc></sitemap><!-- ... ~10,000 child sitemaps ... --></sitemapindex>
```

Here there's no `<lastmod>` at all — the date is encoded in the child URL
path (`/sitemap2/2026-04-03/`). This is the case the **generated
per-site extractor** (configs/sitemap_extractors/) is designed for.
