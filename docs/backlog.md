# Backlog

Curated follow-up work for the portfolio platform.

## Now

- _None_

## Next

- [ ] Deploy the podcast proxy and set `proxy_url`
  - Why: SoundOn RSS feeds are reachable by `curl` but not directly by browser `fetch()` because the feed responses do not expose permissive CORS headers.
  - Scope: apply `infra/`, capture the Lambda Function URL output, set `site/data/podcasts.shows.json.proxy_url`, and verify both localhost and deployed-site refresh behavior.
  - Done when: `podcasts.html` and the home teaser load live episodes through the proxy on refresh without direct browser-to-SoundOn fetches.

- [ ] Populate podcast platform links
  - Why: SoundOn links are configured, but Spotify, Apple Podcasts, and KKBOX URLs are still blank.
  - Scope: update `site/data/podcasts.shows.json` for each show and verify the buttons render on `podcasts.html`.
  - Done when: each show card exposes the intended listening destinations.

## Later

- [ ] Add theme toggle and light mode support
  - Why: the site currently feels dark-mode-first, and there is no user-facing theme choice.
  - Scope: `site/assets/css/**`, `site/assets/js/**`, shared page templates, theme persistence or system-preference handling.
  - Done when: the site supports both dark and light mode, and the user can switch themes without breaking page readability or layout.
