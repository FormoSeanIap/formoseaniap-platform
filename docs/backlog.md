# Backlog

Curated follow-up work for the portfolio platform.

## Now

- _None_

## Next

- [ ] Deploy the podcast feed route
  - Why: SoundOn RSS feeds are reachable by `curl` but not directly by browser `fetch()` because the feed responses do not expose permissive CORS headers.
  - Scope: configure CloudFront to route `site/data/podcasts.shows.json.feed_proxy_path` requests to the SoundOn RSS origin, keep the local `proxy_url` path for preview/Lambda-compatible testing, and verify both localhost and deployed-site refresh behavior.
  - Done when: `podcasts.html` and the home teaser load live episodes through same-origin CloudFront feed paths in production without direct browser-to-SoundOn fetches.

- [ ] Populate podcast platform links
  - Why: SoundOn links are configured, but Spotify, Apple Podcasts, and KKBOX URLs are still blank.
  - Scope: update `site/data/podcasts.shows.json` for each show and verify the buttons render on `podcasts.html`.
  - Done when: each show card exposes the intended listening destinations.

## Later

- [ ] Add custom domain for the production site
  - Why: the site will eventually need a branded public hostname instead of the default CloudFront domain.
  - Scope: buy the domain, request the viewer certificate in ACM `us-east-1`, add the Route 53 hosted zone and alias records, attach the certificate and aliases to the CloudFront distribution, and update any deploy/runtime configuration that currently assumes provider-generated URLs.
  - Done when: the production site is reachable on the purchased domain over HTTPS and the old CloudFront hostname is no longer the primary public entrypoint.
