# Backlog

Curated follow-up work for the portfolio platform.

## Now

- _None_

## Next

## Later

- [ ] Recalibrate the analytics cost estimate in `README.md` against the post-Lane-C write pattern
  - Why: Lane C dropped the third `SITE#ALL` write per collect event, which both made the README's "two uniqueness writes and performs two counter updates" description accurate and shifted the actual DynamoDB cost per 1M requests downward by roughly a third. The "Cost Estimate" dollar figures were order-of-magnitude placeholders that predate Lane C and have not been recomputed.
  - Scope: compute the real DynamoDB on-demand cost per 1M collect events under the new 2 unique-claim + 2 counter-update pattern at Free-tier pricing, update the per-1M-request line, and propagate into the Small/Medium/Large scenario rows.
  - Done when: the cost table in `README.md` reflects the post-Lane-C write count, and the backend variable cost line in the Variable backend cost section is consistent with it.

- [ ] Emit a per-article canonical URL from `article.html`
  - Why: Lane D added `<link rel="canonical">` to every non-article page, but `site/article.html` and `site-eng/article.html` can't have a static canonical because the displayed article is chosen by the `?id=` query string. Without a per-article canonical, search engines see every distinct article URL as the same base page.
  - Scope: when `articles.js` loads an article, inject or update a `<link rel="canonical" href="https://www.formoseaniap.com/article.html?id=<id>&lang=<lang>" />` into the document head. Consider also emitting a per-article sitemap entry from `scripts/build_articles.py` into `site/sitemap.xml` / `site-eng/sitemap.xml` at build time, so crawlers can discover articles without relying on JS.
  - Done when: every article detail URL reports a canonical URL that matches its own `?id=` query, and the sitemap lists each article.

- [ ] Emit per-article Open Graph and Twitter Card metadata from `article.html`
  - Why: Lane B added static `og:*` and `twitter:*` metadata to every page, including the two `article.html` templates. The article detail page currently advertises the generic "Article detail page." description to every social-share crawl, regardless of which article is being viewed. Once the canonical-URL follow-up above is done, the same injection path should also update the `og:title`, `og:description`, `og:url`, `twitter:title`, and `twitter:description` tags.
  - Scope: in `articles.js`, after the article payload is loaded, call `document.querySelector('meta[property="og:title"]')` etc. and rewrite the `content` attribute to match the article's title and excerpt. Add a per-article `og:image` once a social-card image story exists (see the next item).
  - Done when: viewing `/article.html?id=<any-id>` produces OG tags that describe that specific article, not the generic detail template.

- [ ] Create a default Open Graph share image for the site
  - Why: Lane B added OG metadata but not an `og:image`, so social platforms fall back to a plain-text preview. An opinionated 1200×630 PNG showing the site's name + tagline + accent colours would give every shared link a recognisable visual.
  - Scope: design a dark-theme and/or light-theme variant, drop the PNG(s) under `site/assets/og/`, add `<meta property="og:image" content="https://www.formoseaniap.com/assets/og/default.png" />` and the matching `twitter:image` to every HTML page's head, switch `twitter:card` from `summary` to `summary_large_image` to take advantage of the wider preview, and include the image in the engineering tree too (static file, no sync mechanism needed if it lives under `site-eng/assets/og/` with its own copy — or reference the main-site absolute URL).
  - Done when: sharing any page on LinkedIn/Twitter/Discord/Slack/Teams produces a preview card with a rendered image, not a plain text fallback.

- [ ] Add a favicon, apple-touch-icon, and web-app manifest icon
  - Why: production review against `https://www.formoseaniap.com/` on 2026-04-21 found that `/favicon.ico`, `/favicon.svg`, `/icon.svg`, and `/apple-touch-icon.png` all return 403. Browsers silently request these on every page load, so each visit produces a failed CloudFront request and the browser tab shows a generic globe icon instead of a site-specific mark.
  - Scope: design an icon that matches the "Sêng-Gān Ia̍p" brand (the serif-forward wordmark already used in the site header is a natural starting point), export as `favicon.ico` (multi-resolution), `favicon.svg`, and `apple-touch-icon.png` (180×180), drop them under `site/` at the web root, add matching `<link rel="icon">` and `<link rel="apple-touch-icon">` tags to every HTML head, and mirror the three files into `site-eng/` (the engineering section serves its own copies because it lives under its own S3 origin prefix and the favicon URL is site-root relative inside the `<head>`).
  - Done when: every HTML page declares a favicon link, the live URLs return 200 for `/favicon.ico`, `/favicon.svg`, `/apple-touch-icon.png` (and the `/engineer/` equivalents), and the browser tab shows the site icon instead of the default globe.

- [ ] Map 403/404 errors to a custom HTML not-found page on CloudFront
  - Why: production review found that requesting a non-existent URL (e.g. `https://www.formoseaniap.com/definitely-not-a-real-page.html`) returns HTTP 403 with an S3 `AccessDenied` XML body, because the S3 origin behind CloudFront's OAC cannot distinguish "key does not exist" from "key exists but access denied" and always returns 403. The user-visible response is an XML blob that reads "forbidden," not an HTML page that reads "not found."
  - Scope: add `custom_error_response` blocks to `aws_cloudfront_distribution.site` that map 403 and 404 from the S3 origin to a `/404.html` (served from the same S3 bucket, HTTP 200 at the object level but rewritten to status 404 at the CloudFront layer) or to a small inline response. Keep the engineering section covered by the same mapping. Verify this does not break the `/analytics-api/*` and `/podcasts/*` behaviors, which should still pass through origin errors rather than being remapped.
  - Done when: visiting an arbitrary bogus URL on either the main site or the engineering section returns an HTML page styled consistently with the site, and the paired-URL collision smoke test still passes.

- [ ] Fingerprint CSS and JS asset filenames to unlock long-lived immutable caching
  - Why: production review found that `/assets/css/*.css` and `/assets/js/*.js` serve with `Cache-Control: max-age=14400` (4 hours). That's already short enough that deploys propagate without a full invalidation, but readers still re-download unchanged CSS and JS four times a day. Fingerprinted filenames like `components.<hash>.css` referenced from HTML that CloudFront serves with a short TTL would unlock `max-age=31536000, immutable` on the asset itself — browsers and CDN nodes could cache the asset forever because the filename changes on every content change.
  - Scope: teach `scripts/build_articles.py` (or a new small build step) to hash each shared CSS/JS file, rename the output to `<name>.<hash>.css` / `<name>.<hash>.js`, rewrite the `<link rel="stylesheet">` and `<script src>` references in every HTML file to point at the fingerprinted name, wire this through the `scripts/sync_shared_assets.py` path so the engineering tree stays consistent, add CloudFront response headers that stamp `Cache-Control: public, max-age=31536000, immutable` on the `/assets/*` paths, and confirm the CI `Ensure generated outputs are committed` step still passes.
  - Done when: every CSS/JS response on production carries `Cache-Control: immutable`, HTML responses stay on a short TTL so they pick up the new fingerprinted filenames on every deploy, and the build remains reproducible (same input produces the same fingerprinted filenames).

- [ ] Handle the OPTIONS preflight on `/analytics-api/collect` defensively
  - Why: production review confirmed that `OPTIONS /analytics-api/collect` returns 404 because the API Gateway HTTP API only has a `POST` route configured. This does not affect the live site today because every call to the collector is same-origin (from HTML pages served under `www.formoseaniap.com`) and `sendBeacon` / `fetch` with a JSON body do not trigger a preflight in that context. If the collector is ever called from a different origin (for instance, an offline-first article reader or a third-party embed), the missing preflight handler would silently drop those events.
  - Scope: either add an `OPTIONS /analytics-api/collect` route on the API Gateway HTTP API that returns 204 with the right `Access-Control-*` headers, or attach a CloudFront Function on viewer-request for the `/analytics-api/collect` path that synthesises the preflight response at the edge. The CloudFront-function option avoids an extra API Gateway route entry.
  - Done when: `curl -i -X OPTIONS https://www.formoseaniap.com/analytics-api/collect -H 'origin: https://example.com' -H 'access-control-request-method: POST'` returns 204 with the expected CORS headers.

- [ ] Complete the `formoseaniap.com` cutover while Cloudflare remains authoritative
  - Why: the infrastructure now supports the branded production hostname, but Cloudflare must stay as the live DNS provider until the new-domain transfer lock expires.
  - Scope: run a plain `terraform apply`, create the ACM validation records manually in Cloudflare from the Terraform manual-DNS outputs if the first apply stops at validation, rerun the same plain apply, then add the final cutover records in Cloudflare, verifying `www` as the canonical host plus apex and legacy CloudFront redirects.
  - Done when: `https://www.formoseaniap.com` is the canonical public site, `https://formoseaniap.com` and the old CloudFront hostname redirect there, and the dedicated analytics auth subdomain is serving Cognito managed login while Cloudflare remains the live DNS authority.

- [ ] Transfer `formoseaniap.com` DNS authority to Route 53 and then enable DNSSEC
  - Why: the current Cloudflare-authoritative setup requires manual DNS mirroring; after the transfer hold expires, Route 53 should become the single source of truth and DNSSEC can be enabled there cleanly.
  - Scope: once the registrar lock window allows it (probably 6/13, from 4/14 + 60 days), move nameserver control or the registrar itself so Route 53 becomes authoritative, remove the need to mirror records into Cloudflare, then design and implement DNSSEC as a follow-up in the now-authoritative Route 53 setup.
  - Done when: Route 53 is authoritative for `formoseaniap.com`, the live DNS records are served directly from the Terraform-managed hosted zone, and DNSSEC validates publicly without depending on manual Cloudflare DNS mirroring.
