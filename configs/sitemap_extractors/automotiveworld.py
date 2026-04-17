# extractor-meta: site=automotiveworld cutoff=2026-04-10 sample_hash=a53898f36d85 model=gpt-5.4-mini generated_at=2026-04-17T06:47:00+00:00
# notes: Tailored for a Yoast sitemapindex on automotiveworld: only opens child sitemaps that look like post/news sitemaps and are not ruled out by sitemap lastmod or URL date; then filters article URLs by path shape plus lastmod/path date cutoff.

def extract_recent_urls(top_xml_path: str, cutoff_date, fetch_xml) -> list:
    import xml.etree.ElementTree as ET
    import datetime
    import re
    from urllib.parse import urlparse

    NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'

    def parse_date(text):
        if not text:
            return None
        s = str(text).strip()
        if not s:
            return None
        if 'T' in s:
            s = s.split('T', 1)[0]
        elif ' ' in s:
            s = s.split(' ', 1)[0]
        try:
            return datetime.date.fromisoformat(s)
        except Exception:
            m = re.search(r'(\d{4})-(\d{2})-(\d{2})', s)
            if m:
                try:
                    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except Exception:
                    return None
        return None

    def path_date(url):
        if not url:
            return None
        m = re.search(r'/(\d{4})/(\d{2})/(\d{2})(?:/|$)', url)
        if m:
            try:
                return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except Exception:
                return None
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', url)
        if m:
            try:
                return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except Exception:
                return None
        return None

    def has_article_shape(url):
        if not url:
            return False
        p = urlparse(url)
        path = (p.path or '').rstrip('/')
        if not path or path == '/':
            return False
        segs = [s for s in path.split('/') if s]
        if len(segs) < 2:
            return False
        low = [s.lower() for s in segs]
        bad_first = {'news', 'reviews', 'review', 'about-us', 'about', 'topics', 'topic', 'author', 'authors', 'tag', 'tags', 'category', 'categories', 'section', 'sections', 'index', 'archives', 'archive'}
        if low[0] in bad_first:
            return False
        if any(s in bad_first for s in low):
            return False
        if any(s.isdigit() for s in segs[-1]):
            return True
        if len(segs[-1]) < 4:
            return False
        return True

    def nsfind(parent, name):
        return parent.find(NS + name) or parent.find(name)

    def nsfindall(parent, name):
        return parent.findall(NS + name) + parent.findall(name)

    results = []
    seen = set()

    tree = ET.parse(top_xml_path)
    root = tree.getroot()
    root_tag = root.tag

    if root_tag.endswith('sitemapindex'):
        for sm in nsfindall(root, 'sitemap'):
            loc_el = nsfind(sm, 'loc')
            if loc_el is None or not (loc_el.text or '').strip():
                continue
            child_url = loc_el.text.strip()
            lastmod_el = nsfind(sm, 'lastmod')
            lm_date = parse_date(lastmod_el.text if lastmod_el is not None else None)
            pd = path_date(child_url)
            if lm_date is not None and lm_date < cutoff_date:
                continue
            if lm_date is None and pd is not None and pd < cutoff_date:
                continue
            if lm_date is None and pd is None:
                if not re.search(r'(post-sitemap|news-sitemap)', child_url):
                    continue
            if child_url.endswith('.xml') or child_url.endswith('.xml.gz'):
                pass
            try:
                child_bytes = fetch_xml(child_url)
                child_root = ET.fromstring(child_bytes)
            except Exception:
                continue
            if not child_root.tag.endswith('urlset'):
                continue
            for url_el in nsfindall(child_root, 'url'):
                loc_el = nsfind(url_el, 'loc')
                if loc_el is None or not (loc_el.text or '').strip():
                    continue
                link = loc_el.text.strip()
                if not link.startswith('http://') and not link.startswith('https://'):
                    continue
                if not has_article_shape(link):
                    continue
                lm_el = nsfind(url_el, 'lastmod')
                eff = parse_date(lm_el.text if lm_el is not None else None)
                if eff is None:
                    eff = path_date(link)
                if eff is None or eff < cutoff_date:
                    continue
                if link in seen:
                    continue
                seen.add(link)
                results.append({'link': link, 'lastmod': eff.isoformat() if eff else ''})
    else:
        for url_el in nsfindall(root, 'url'):
            loc_el = nsfind(url_el, 'loc')
            if loc_el is None or not (loc_el.text or '').strip():
                continue
            link = loc_el.text.strip()
            if not link.startswith('http://') and not link.startswith('https://'):
                continue
            if not has_article_shape(link):
                continue
            lm_el = nsfind(url_el, 'lastmod')
            eff = parse_date(lm_el.text if lm_el is not None else None)
            if eff is None:
                eff = path_date(link)
            if eff is None or eff < cutoff_date:
                continue
            if link in seen:
                continue
            seen.add(link)
            results.append({'link': link, 'lastmod': eff.isoformat() if eff else ''})

    return results
