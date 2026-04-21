# Backlog

Curated follow-up work for the portfolio platform.

## Now

- _None_

## Next

## Later

- [ ] Emit a per-article canonical URL from `article.html`
  - Why: Lane D added `<link rel="canonical">` to every non-article page, but `site/article.html` and `site-eng/article.html` can't have a static canonical because the displayed article is chosen by the `?id=` query string. Without a per-article canonical, search engines see every distinct article URL as the same base page.
  - Scope: when `articles.js` loads an article, inject or update a `<link rel="canonical" href="https://www.formoseaniap.com/article.html?id=<id>&lang=<lang>" />` into the document head. Consider also emitting a per-article sitemap entry from `scripts/build_articles.py` into `site/sitemap.xml` / `site-eng/sitemap.xml` at build time, so crawlers can discover articles without relying on JS.
  - Done when: every article detail URL reports a canonical URL that matches its own `?id=` query, and the sitemap lists each article.

- [ ] Complete the `formoseaniap.com` cutover while Cloudflare remains authoritative
  - Why: the infrastructure now supports the branded production hostname, but Cloudflare must stay as the live DNS provider until the new-domain transfer lock expires.
  - Scope: run a plain `terraform apply`, create the ACM validation records manually in Cloudflare from the Terraform manual-DNS outputs if the first apply stops at validation, rerun the same plain apply, then add the final cutover records in Cloudflare, verifying `www` as the canonical host plus apex and legacy CloudFront redirects.
  - Done when: `https://www.formoseaniap.com` is the canonical public site, `https://formoseaniap.com` and the old CloudFront hostname redirect there, and the dedicated analytics auth subdomain is serving Cognito managed login while Cloudflare remains the live DNS authority.

- [ ] Transfer `formoseaniap.com` DNS authority to Route 53 and then enable DNSSEC
  - Why: the current Cloudflare-authoritative setup requires manual DNS mirroring; after the transfer hold expires, Route 53 should become the single source of truth and DNSSEC can be enabled there cleanly.
  - Scope: once the registrar lock window allows it (probably 6/13, from 4/14 + 60 days), move nameserver control or the registrar itself so Route 53 becomes authoritative, remove the need to mirror records into Cloudflare, then design and implement DNSSEC as a follow-up in the now-authoritative Route 53 setup.
  - Done when: Route 53 is authoritative for `formoseaniap.com`, the live DNS records are served directly from the Terraform-managed hosted zone, and DNSSEC validates publicly without depending on manual Cloudflare DNS mirroring.
