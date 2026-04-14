# Personal Portfolio Platform

Long-term portfolio platform for identity, technical work, and writing.

This project is static-first and deploys to S3/CloudFront, with a same-origin podcast feed route for CORS-safe RSS reads.

## Vision

Build a portfolio that balances:
- Technical professionalism (cloud/platform engineering)
- Personal expression (writing, creative work, visual identity)
- Long-term maintainability (clear structure and reusable systems)

## Profile Focus

This platform introduces me as:
- Platform engineer
- Writer
- Creator

## Current State (April 12, 2026)

Implemented:
- Shared static pages and branding across Home / Projects / Podcasts / Articles / About.
- Consistent design system via `site/assets/css/*` and `site/assets/js/main.js`.
- Shared theme system across all top-level pages:
  - Visible `Auto` / `Light` / `Dark` header control
  - First-load system preference follow
  - Explicit theme persistence via `localStorage` (`theme-preference`)
- Runtime-loaded podcast section:
  - Dedicated `site/podcasts.html` page
  - Local show config in `site/data/podcasts.shows.json`
  - Same-origin RSS loading from configured public podcast feeds via `feed_proxy_path`
  - Local proxy fallback via `proxy_url` / `LOCAL_PROXY_URL` for preview and Lambda-compatible testing
  - Icon-first platform actions on show and episode cards
  - Per-show platform links and per-feed failure fallback states
  - Local Python proxy for localhost preview; production uses CloudFront direct feed routing instead of Lambda
- Terraform-managed production infrastructure:
  - S3 remote state backend in `ap-northeast-1`
  - Private S3 site origin with public access blocked
  - CloudFront Origin Access Control for S3 reads
  - AWS-managed CloudFront cache policies only, so the distribution can later be moved to a Free/Pro flat-rate plan from the AWS console
  - CloudFront `/podcasts/*` behavior routed to the SoundOn RSS origin for same-origin browser fetches
  - CloudFront `/analytics-api/*` behavior routed to an API Gateway HTTP API for same-origin analytics collection and admin reads
  - Lambda-backed analytics collector/admin handlers on Python 3.14 with DynamoDB daily counters + uniqueness state
  - CloudWatch success-rate alarms for the analytics Lambdas with SNS email notifications and a dedicated CloudWatch dashboard
  - Route 53 hosted zone foundation for `formoseaniap.com`, ready for a future registrar or DNS-authority transfer
  - Custom-domain infrastructure for `www.formoseaniap.com` with manual external-DNS validation/cutover outputs, apex redirect, and a CloudFront viewer-request redirect function
  - Cognito managed-login redirect flow for the private analytics admin page, with username-based sign-in, `ESSENTIALS` user-pool tier, and a separate full-name display attribute
- Private analytics admin surface:
  - Dedicated `site/admin/analytics.html` page with a branded sign-in shell
  - Production-only Cognito managed-login redirect with Authorization Code + PKCE
  - Admin users sign in with a Cognito `username`; the dashboard displays standard `name`, then falls back to `email`
  - `auth.formoseaniap.com` custom-domain infrastructure and managed-login branding assets for the Cognito sign-in experience
  - Same-origin browser analytics events for public page loads and article detail reads
  - Deploy-time runtime config written to `site/data/analytics.config.json` from Terraform outputs
- Python-based article build pipeline:
  - Markdown source in `content/articles/**`
  - Metadata index JSON
  - Lazy body-search JSON index
  - Per-article full body JSON
  - Legacy nested markdown support (metadata inference)
  - Auto series navigation for part-based articles
  - Series home view via query filter (`articles.html?series=<series_id>`)
  - Series context banner on series-filter pages (clear identity + quick actions)
  - Collection and article preview images via explicit cover metadata or inferred first local article image
  - Filter-aware search on `articles.html` across article titles, series titles, and article content keywords
  - Progressive loading on Articles and Projects pages
  - Multi-select article filters with bilingual collection merging on the list page
  - Article cards show part number next to series line (not in top meta line)
  - Article detail pages mirror navigation chips at the top and again below the article card, with `Back to top` at the bottom
  - RSS feeds (EN + ZH)
  - JSON-driven frontend pages (`site/articles.html`, `site/article.html`)
  - JSON-driven Projects page (`site/projects.html`)
  - Project case-study cards support featured entries, status badges, highlight lists, and optional private-repo notes via `site/data/projects.json`
  - GitHub Actions scaffolding for work-branch and long-lived branch push validation, push-time Terraform plan on infra changes, PR validation with previews, and `main`-gated production promotion for site and Terraform changes under `infra/`

## Architecture

Static-first runtime:
- S3 stores HTML/CSS/JS/JSON/XML files in a private bucket.
- CloudFront is the public entrypoint and reads S3 through Origin Access Control.
- Core public pages remain static-first with no application backend for content rendering.
- A same-origin analytics backend is available only for private admin reads and public write-only event collection.
- `podcasts.html` reads configured public RSS feeds through same-origin `feed_proxy_path` routes, or through the local/Lambda-compatible proxy when `proxy_url` is configured, so newly published episodes can appear after refresh without rebuilding the repo.
- Public pages send client-side analytics events to `/analytics-api/collect` after successful render; the private dashboard reads aggregated data from `/analytics-api/admin/*`.

Build-time flow:
1. Author Markdown in `content/articles/**`
2. Run Python build script
3. Script writes generated artifacts into `site/data/` and `site/rss.xml`
4. Deploy `site/` to S3

## Repository Structure

```text
/
- .github/
  - dependabot.yml             Dependabot config for GitHub Actions + Terraform updates
  - actions/
    - site-validate/action.yml   shared site validation steps for PR/push/main workflows
    - terraform-plan/action.yml  shared Terraform plan steps for push/PR/main workflows
  - workflows/
    - aws-oidc-smoke.yml        manual GitHub OIDC -> AWS trust smoke test
    - _terraform-validate-shared.yml reusable Terraform change detection + validation
    - push-others.yml           `Push Others`: push validation for work branches and `develop`
    - pr-validate.yml           `PR Validate`: PR validation, preview, and optional Terraform plan
    - push-main.yml             `Push Main`: main-branch validation + gated full Terraform plan/apply + production deploy
    - version-audit.yml         weekly + manual runtime/tool version audit
- .codex/
  - config.toml                 repo-local Codex sandbox/approval defaults
  - skills/
    - static-site-ui-review/     repo-local Codex skill for frontend UI review
    - terraform-hygiene/         repo-local Codex skill for Terraform doc lookup and deprecation-safe validation
- content/
  - articles/
  - tags.json
  - site.json
- docs/
  - aws-oidc-github-actions.md  GitHub Actions -> AWS OIDC setup notes
  - github-branching.md         develop/main branch + environment workflow
  - examples/
    - aws-oidc-trust-policy-branch.json
    - aws-oidc-trust-policy-environment.json
    - aws-oidc-trust-policy-plan-and-output.json
    - aws-oidc-trust-policy-pull-request.json
  - inbox.md                quick todo capture
  - backlog.md              curated implementation backlog
- infra/
  - README.md                  Terraform home and workflow convention
  - analytics.tf               analytics API, Cognito, Lambda, and DynamoDB resources
  - analytics_outputs.tf       analytics runtime outputs consumed by production deploy
  - analytics_variables.tf     analytics-related Terraform variables
  - backend.tf                 S3 remote backend config
  - cloudfront/                CloudFront Function templates for canonical-host redirects
  - cognito_branding/          managed-login branding JSON + SVG assets for Cognito
  - domain.tf                  Route 53 hosted zone, ACM staging, aliases, and auth custom-domain resources
  - domain_outputs.tf          Route 53, manual DNS, and public URL outputs
  - domain_variables.tf        domain naming variables
  - main.tf                    private S3 + CloudFront OAC production site stack
  - variables.tf               production infrastructure variables
  - outputs.tf                 site bucket and CloudFront outputs
- analytics_backend/
  - collector.py               analytics event validation + DynamoDB write logic
  - admin.py                   analytics range aggregation + admin API responses
  - collector_lambda.py        Lambda entrypoint for public collector writes
  - admin_lambda.py            Lambda entrypoint for private admin reads
- scripts/
  - audit_versions.py         offline + optional network version audit for repo tooling
  - build_articles.py
  - dedupe_bilingual_images.py
  - podcast_proxy.py          local + Lambda-compatible podcast RSS proxy
  - terraform_validate_strict.py strict Terraform fmt/init/validate wrapper that fails on deprecations
- site/
  - assets/
    - css/admin.css          analytics admin page styles
    - css/podcasts.css       podcast-specific page styling
    - js/admin-analytics.js  Cognito login flow + private analytics dashboard UI
    - js/analytics.js        client-side page/article analytics event emitter
    - js/podcasts.js         runtime RSS loading + podcast rendering for `podcasts.html`
  - data/                    generated article JSON + podcast runtime config
    - analytics.config.json  tracked placeholder; production deploy writes live runtime values
    - articles.search.json   lazy-loaded article search index
    - projects.json          project case-study data
    - podcasts.shows.json    upstream podcast feeds, same-origin feed paths, and platform links
  - admin/
    - analytics.html         private analytics admin page shell
  - articles.html            list/filter page
  - article.html             detail page
  - podcasts.html            runtime-loaded podcast landing page
  - projects.html            project list page
- tooling/
  - version-policy.yml       repo version policy for Python, Terraform, and tracked GitHub Actions
  - rss.xml                  generated EN feed
  - zh/rss.xml               generated ZH feed
- README.md
```

## Repo-Local Codex Skills

- `./.codex/skills/static-site-ui-review` provides a repo-specific frontend review workflow for this static site.
- Use it when reviewing or finalizing changes to `site/*.html`, `site/assets/css/**`, `site/assets/js/**`, or article list/detail rendering behavior.
- `./.codex/skills/terraform-hygiene` provides a repo-specific Terraform workflow for current-doc lookup, provider-schema fallback, and strict deprecation-free validation.
- Use it when reviewing or changing `infra/*.tf`, `infra/.terraform.lock.hcl`, or shared Terraform validation workflows.

## Repo-Local Codex Config

- `./.codex/config.toml` sets this repository to `workspace-write` with `approval_policy = "on-request"`.
- In a trusted project, that means Codex can read, edit, and run routine local commands inside this repo, while sandbox-escalated commands can ask for approval when needed.
- If Codex is launched in a broader machine-level mode such as `danger-full-access`, that already-active session is not retroactively narrowed by `./.codex/config.toml`; the repo file only sets defaults for sessions that honor repo-local config at startup.
- This repo-local file is ignored unless the project is trusted. If prompts persist, mark this repo as trusted in Codex or add a user-level entry such as `[projects."/home/ubuntu/non_work/formoseaniap-platform"] trust_level = "trusted"` in `~/.codex/config.toml`.
- This configuration does not grant network access and does not expand access outside the workspace. If you want broader machine-level access, that must be enabled from your user-level Codex config or launch flags instead of this repo file.

## AWS OIDC Bootstrap

- `./.github/workflows/aws-oidc-smoke.yml` is a manual GitHub Actions workflow that validates GitHub OIDC -> AWS role assumption with `aws sts get-caller-identity`.
- `./docs/aws-oidc-github-actions.md` explains the role split, trust-policy expectations, and the bootstrap sequence for moving this repo onto AWS via GitHub Actions.
- `./docs/examples/aws-oidc-trust-policy-branch.json`, `./docs/examples/aws-oidc-trust-policy-environment.json`, `./docs/examples/aws-oidc-trust-policy-plan-and-output.json`, and `./docs/examples/aws-oidc-trust-policy-pull-request.json` provide branch-scoped, environment-scoped, main/PR plan, and PR-scoped IAM trust policy templates.

## Git Workflow

- `main` is the default branch, the production deployment source, and the only branch that should trigger production deploys.
- `develop` is the long-lived integration branch for day-to-day work, validation, and preview testing before release.
- Open `feature/*`, `fix/*`, `chore/*`, and `docs/*` branches from the latest `develop`.
- Open `hotfix/*` branches from the latest `main`, merge them to `main`, then merge or cherry-pick them back into `develop`.
- Merge feature work into `develop` through pull requests; prefer squash merges there.
- Release by opening a pull request from `develop` to `main`; prefer a normal merge commit for release PRs so release boundaries stay visible.
- Push-time validation runs on work branches and `develop`; `main` validation runs inside `Push Main` before the protected production gate.
- GitHub-side branch protection, auto-delete, and merge-strategy settings are documented in `./docs/github-branching.md`.

## CI/CD Workflow

- `./.github/workflows/push-others.yml` runs unit tests, rebuilds generated site artifacts, fails on generated-artifact drift, and adds shared Terraform validation plus live-state Terraform plan when Terraform-related files changed on `feature/*`, `fix/*`, `chore/*`, `docs/*`, `hotfix/*`, and `develop`.
- `./.github/workflows/pr-validate.yml` runs unit tests, rebuilds generated site artifacts, fails if generated outputs are out of date, uploads a preview artifact, performs shared Terraform validation plus an optional OIDC-backed Terraform plan when infra files changed, and only proceeds to preview status/deploy after the Terraform PR checks are complete.
- `./.github/workflows/push-main.yml` re-runs the same validation path on `main`, can publish a pre-promotion Terraform plan artifact when the read-only plan role is configured, and waits at the protected `prod` environment before always running Terraform plan/apply against the production state, reading production outputs from remote state, and deploying the generated `site/` output.
- On successful production promotion, `Push Main` also writes the live analytics runtime config JSON into the built site artifact before syncing to S3 so the admin page gets the current Cognito/client settings without hard-coding them in the repo.
- `./.github/workflows/version-audit.yml` runs a weekly and manually triggered version audit for Python, Terraform, and tracked GitHub Actions, writing a summary plus a JSON artifact.
- `./.github/dependabot.yml` opens weekly update PRs for Terraform and GitHub Actions dependency drift.
- Shared Terraform CI runs `python3 scripts/terraform_validate_strict.py`, which fails on Terraform errors and deprecation diagnostics. Terraform MCP is used for current-doc lookup, but the CI gate is the actual enforcement layer.

## Terraform Validation

- Run `python3 scripts/terraform_validate_strict.py` from the repo root for the local Terraform validation path used by CI.
- The strict validator runs `terraform fmt -check -recursive`, backendless `terraform init -backend=false -reconfigure -input=false`, and `terraform validate -json` against `infra/`.
- The command fails on Terraform errors and on deprecation warnings, while leaving unrelated non-deprecation warnings advisory unless Terraform itself exits nonzero.

## Planning Workflow

- Use `docs/inbox.md` for quick idea capture.
- Use `docs/backlog.md` for structured follow-up work that is concrete enough to prioritize or implement.
- Promote items from inbox to backlog once they have enough scope and a clear definition of done.

## Article Data Model

Preferred source layout is semantic and work-first under `content/articles/**`.

Examples:

```text
content/articles/
- others/
  - <Work>/
    - Shared/*.png
    - en.md | zh.md
- technical/
  - Operation_Deep_Dive/
    - <Work>/
      - Shared/*.png
      - en.md | zh.md
- reviews/
  - Anime_Manga|Movie|TV_Drama|Book|Game|Novel/
    - <Work>/
      - Shared/*.png
      - en.md | zh.md
    - <Work>/
      - Shared/*.png
      - Part1/en.md | zh.md
    - <Work>/
      - Shared/*.png
      - English/Part1/*.md
      - Mandarin/Part1/*.md
```

Build support is broader than the preferred layout:
- Nested frontmatter-based files are fully supported.
- Legacy nested files without frontmatter are also supported.
- For frontmatter-free legacy files, metadata is inferred from path + content.
- Asset folder and file names under `content/articles/**` must avoid `:"<>|*?` so generated site assets can be uploaded through GitHub Actions artifacts on all supported filesystems.

Required frontmatter fields:
- `id`
- `lang` (`en` or `zh`)
- `title`
- `slug`
- `excerpt`
- `category` (`technical`, `review`, `other`; `others` is accepted and normalized to `other`)
- `tags` (list of tag keys)
- `published_at` (`YYYY-MM-DD`)
- `read_time` (minutes)

Optional fields:
- `updated_at`
- `external_url` (if set, cards/detail show external link mode; leave empty to keep reading on this site)
- `cover_image`
- `series_cover_image` (collection-level cover shown on article collection cards and series context cards; may be `/assets/...` or a relative path from the markdown file)
- `draft` (`true` to exclude from build output)
- `subcategory_id` (normally inferred from the folder path, for example `Anime_Manga` or `Operation_Deep_Dive`)
- `subcategory_label` (normally inferred and humanized from `subcategory_id`)
- `series_id`
- `series_title`
- `series_order` (optional explicit order within a shared series without implying visible part numbering)
- `part_number`

Image caption convention:
- Use explicit image titles on image-only lines: `![alt text](./image.png "Visible caption")`.
- The title becomes the centered image caption (`image-caption`) under the image block.
- Inline images inside paragraphs do not render visible captions.
- If the caption text itself contains double quotes, escape them as `\"` inside the title.
- If EN and ZH versions use the exact same image, store it once in a language-neutral `Shared/` folder under the common work/article parent and reference it relatively from both markdown files.
- Keep language-specific images inside `English/` or `Mandarin/` only when the binaries actually differ.

Embedded media convention:
- Use a standalone line like `[Embedded media](https://www.youtube.com/embed/<video-id>)` to render an in-page video player.
- Supported providers are YouTube (`youtube.com/embed`, `youtube.com/watch`, `youtu.be`) and Vimeo (`vimeo.com`, `player.vimeo.com/video/...`).
- Ordinary inline links to YouTube/Vimeo stay normal links; only the standalone `Embedded media` form is auto-embedded.

Article prose spacing convention:
- Standalone `\` line means a small pause between prose blocks.
- One blank line means a normal paragraph break.
- Two or more blank lines mean a larger pause.
- Do not use trailing `\` at the end of prose lines for spacing; keep command-continuation backslashes only inside code/examples.

Tag labels are defined in:
- `content/tags.json`

Site feed metadata is defined in:
- `content/site.json`

## Build Commands

Prerequisite:
- Python 3.14+ (stdlib only, no pip dependencies required)

Run unit tests:
```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Generate article data + feeds:
```bash
python3 scripts/build_articles.py
```

One-time legacy normalization (add inferred frontmatter to old markdown files):
```bash
python3 scripts/normalize_frontmatter.py
```

Localize Medium-hosted markdown images into local sibling assets:
```bash
python3 scripts/localize_medium_images.py content/articles/reviews/Attack_on_Titan
python3 scripts/localize_medium_images.py content/articles/reviews/Attack_on_Titan --write
```

Deduplicate identical EN/ZH images into `Shared/` folders:
```bash
python3 scripts/dedupe_bilingual_images.py
python3 scripts/dedupe_bilingual_images.py --write --verify
```

Run offline version audit:
```bash
python3 scripts/audit_versions.py
```

Run version audit with upstream latest-version checks:
```bash
python3 scripts/audit_versions.py --network
```

Generated outputs:
- `site/data/articles.index.json`
- `site/data/articles.search.json`
- `site/data/articles/en/*.json`
- `site/data/articles/zh/*.json`
- `site/assets/articles/**` (copied image assets referenced by markdown)
- `site/rss.xml`
- `site/zh/rss.xml`
- `content/site.json` sets the canonical site URL used in generated RSS item links and feed self links. It currently points at `https://www.formoseaniap.com`.

Tracked runtime placeholders:
- `site/data/analytics.config.json` is committed as a disabled placeholder for local work and PR previews.
- The production deploy workflow overwrites that file in the built artifact with live Cognito + analytics config from Terraform outputs before syncing to S3.

Podcast runtime config:
- `site/data/podcasts.shows.json` is source-of-truth for podcast show metadata, feed URLs, and platform links.
- Podcast episodes are not built into generated artifacts; the browser loads configured feeds live through same-origin CloudFront feed routes at page load in production.

## Local Preview

Use the dedicated preview server so the local web root matches production and `/admin/analytics.html` works directly:

```bash
python3 scripts/site_preview.py
```

If port `5500` is already in use, the preview server now probes the next free port and prints the exact URL to open.

For podcast preview on localhost, run the local proxy in a second terminal from the repo root:

```bash
python3 scripts/podcast_proxy.py
```

Then open:
- `http://127.0.0.1:5500/index.html`
- `http://127.0.0.1:5500/articles.html`
- `http://127.0.0.1:5500/articles.html?lang=en&lang=zh&category=review&subcategory=Anime_Manga`
- `http://127.0.0.1:5500/article.html?id=terraform-modules-small&lang=en`
- `http://127.0.0.1:5500/articles.html?series=<series_id>&lang=en&lang=zh`
- `http://127.0.0.1:5500/podcasts.html`
- `http://127.0.0.1:5500/projects.html`
- `http://127.0.0.1:5500/admin/analytics.html`

Analytics admin local behavior:
- The preview server serves `site/` as `/`, so `http://127.0.0.1:5500/admin/analytics.html` works locally without rewriting paths.
- On `127.0.0.1` or `localhost`, the committed `site/data/analytics.config.json` enables a mock dashboard mode.
- Mock mode uses generated article/site analytics data and a local preview sign-in button instead of Cognito, API Gateway, Lambda, or DynamoDB.
- Production deploy still overwrites `site/data/analytics.config.json` in the built artifact with the real Cognito + analytics runtime values.

## Podcast Runtime Config

The podcasts section is configured in `site/data/podcasts.shows.json`.

Expected shape:

```json
{
  "proxy_url": "",
  "shows": [
    {
      "id": "my-show",
      "title": "My Show",
      "feed_url": "https://public-feed.example.com/rss.xml",
      "feed_proxy_path": "/podcasts/provider-feed-id.xml",
      "description": "Short show description.",
      "cover_image": "",
      "order": 1,
      "links": {
        "soundon": "https://...",
        "spotify": "https://...",
        "apple": "https://...",
        "kkbox": "https://..."
      }
    }
  ]
}
```

Behavior:
- `podcasts.html` shows the newest episode globally, then groups the latest 5 loaded episodes per show without removing the featured episode from its show list.
- Refreshing the page triggers live feed reads through same-origin `feed_proxy_path` routes in production; publishing a new episode does not require running `scripts/build_articles.py`.
- If a feed cannot be read in the browser, the page falls back to show-level copy and platform links while leaving other feeds intact.
- On `127.0.0.1` or `localhost`, leaving `proxy_url` blank makes the frontend try `http://127.0.0.1:8787/podcast-feed` automatically for local preview.
- In production, keep `proxy_url` blank and configure CloudFront to route `/podcasts/*` to the SoundOn RSS origin. Set `proxy_url` only if you intentionally switch back to a local/Lambda-compatible proxy endpoint.

Collection-first list page UX:
- `articles.html` shows collection/work cards by default rather than raw article cards.
- Default collection ordering on `articles.html` is newest-first, based on the latest visible article `published_at` within each collection.
- Clicking a collection card opens the existing series-scoped article list with `series=<series_id>`.
- Search is filter-aware and supports `title`, `series`, and `content` modes.
- Title/content search switches the list into article-result mode; series search keeps collection cards.
- Article content search uses the lazy-loaded `site/data/articles.search.json` payload instead of bloating the primary index.
- Collection cards use `series_preview_image`; article cards use `preview_image`.
- `preview_image` falls back to `cover_image` or the first local image found in the article body.
- `series_preview_image` falls back to `series_cover_image` or the first available article preview image in the collection.
- Long result sets on Articles and Projects use progressive loading instead of rendering the full list immediately.
- The filter rows are ordered as `Language` -> `Category` -> `Subcategory` -> `Tags`.
- `Language`, `Category`, `Subcategory`, and `Tags` are multi-select toggle rows.
- The default language selection is both `English` and `中文`.
- Filter semantics are OR within a row and AND across rows.
- Tag selection also uses OR semantics.
- When multiple languages are selected, collection cards merge EN/ZH variants into one card while article results remain language-specific.
- The Articles list uses a two-column card grid on larger screens and collapses to one column on mobile.
- `Subcategory` is derived from the folder taxonomy, for example `Anime_Manga`, `Movie`, `Book`, `Game`, `Operation_Deep_Dive`, or `Operation_Diaries`.

Series filter page UX:
- Shows a dedicated series context banner with:
  - clear series title and counts
  - `Back to articles home`
  - `Clear extra filters`
- selected-language summary when multiple languages are active
- Hides the standard filter summary line in series mode to avoid redundant information.

Filter behavior:
- Filters preserve selected values instead of clearing downstream rows automatically.
- Invalid query values are dropped on load, but valid combinations are preserved even when they produce zero results.
- Option rows are scoped to the current query state while still keeping selected values visible so they can be deselected.

Article detail page UX:
- Repeats the article action chips above the article header and again below the article card.
- Adds `Back to top` at the end of the article and offsets the anchor so the sticky desktop header does not cover the title area.

## Authoring Checklist

When adding or editing an article:

1. Update markdown under `content/articles/**`
2. Organize the file under the appropriate semantic subtree (`others`, `technical`, or `reviews/<type>`)
3. If using frontmatter, ensure it is valid
4. For multi-part content, use `Part1`, `Part2`, ... folder naming or set `series_id` + `part_number`
5. For series entries, keep `title` focused on the part topic only (do not repeat series name or part number in the frontmatter title)
6. Do not add manual `English Version` / `中文版` links or manual previous/next chapter lines in the markdown body; the site renders translation and series navigation for you
7. Do not repeat the article title again as the first heading in the markdown body; the article page already renders the title from frontmatter
8. Do not place a standalone `---` immediately under frontmatter as a visual separator; it is redundant now that the page renders the article header for you
9. Use `![alt text](./image.png "Visible caption")` for image captions; do not place caption text on the next line
10. Keep `external_url` empty if the primary reading path should stay on this website
11. Use a standalone `[Embedded media](https://www.youtube.com/embed/<video-id>)` line when you want a supported video to render directly inside the article
12. Use the prose spacing convention consistently: standalone `\` for a small pause, one blank line for a normal paragraph, and two or more blank lines for a larger pause
13. Do not use trailing `\` at the end of prose lines for spacing; reserve it for command examples inside code blocks
14. If the markdown came from Medium and still points at Medium CDN image URLs, run:
   - `python3 scripts/localize_medium_images.py <path> --write`
15. Run:
   - `python3 scripts/build_articles.py`
16. Verify in browser:
   - `site/articles.html`
   - `site/article.html?...`
   - `site/articles.html?lang=<en|zh>&series=<series_id>` for series-only listing
   - `site/rss.xml`
   - `site/zh/rss.xml`
17. Deploy `site/` to S3

Important:
- `content/articles/` is source-of-truth.
- `site/data/` and RSS are generated artifacts.
- If build is skipped, new articles/tags/RSS will not appear on production.

## Infrastructure Home

- Keep Terraform for this repository under `infra/`.
- Start with a single root stack under `infra/`.
- The Terraform root currently targets the `hashicorp/aws` provider `~> 6.0`.
- The `infra/` root uses S3 remote state in `formoseaniap-platform-tfstate-760259504838-ap-northeast-1-an` with native S3 lock files.
- The production stack creates the private site bucket and CloudFront distribution; the production deploy workflow reads output `site_bucket_name` and output `cloudfront_distribution_id` from Terraform remote state at run time.
- The production stack also creates the private analytics backend:
  - API Gateway HTTP API
  - Lambda collector/admin functions on Python 3.14
  - DynamoDB daily counter and uniqueness tables
  - SNS-backed success-rate alarms for the analytics Lambdas
  - CloudWatch dashboard for analytics backend monitoring
  - Cognito User Pool, App Client, hosted-login domain, and `analytics-admin` group for username-based admin login
- The production stack now also creates the Route 53 public hosted zone for `formoseaniap.com` as the future authoritative zone when the registrar and DNS move are possible.
- The default Terraform design includes the full custom-domain infrastructure:
  - site and auth ACM certificates in `us-east-1`
  - CloudFront aliases for `formoseaniap.com` and `www.formoseaniap.com`
  - a canonical-host redirect function to `https://www.formoseaniap.com`
  - Cognito custom domain `https://auth.formoseaniap.com`
  - managed-login branding assets/settings for the analytics admin login
- When the live DNS provider is still external, the first plain `terraform apply` may stop at ACM validation until you mirror the emitted validation `CNAME`s into Cloudflare, then rerun the same plain `terraform apply`.
- Terraform leaves CloudFront `price_class` unset while the distribution is on a console-managed flat-rate plan, because Free/Pro plans do not allow the price class feature on distribution updates.
- The CloudFront distribution uses AWS-managed cache policies only: `CachingOptimized` for the static site and `CachingDisabled` for `/podcasts/*` and `/analytics-api/*`, avoiding the Business-only custom caching rules that block Free/Pro flat-rate plan changes in the AWS console.
- If a CloudFront flat-rate plan auto-attaches a required WAF web ACL, Terraform ignores `web_acl_id` drift on the distribution and leaves that console-managed association in place.
- If you later move the distribution back to pay-as-you-go, set `cloudfront_price_class` explicitly to a value such as `PriceClass_100`.
- If you manually enable a CloudFront flat-rate plan in the AWS console, Terraform cannot currently unsubscribe or destroy that distribution until the plan is canceled manually and the current billing cycle ends.
- If infrastructure later splits into multiple stacks or modules, update the Terraform workflows to target each stack explicitly.

## AWS Deployment Next Steps

Resume AWS rollout from these steps:

1. Create the GitHub Actions OIDC identity provider in AWS if it does not already exist.
2. Create the IAM roles and policies from `docs/aws-oidc-github-actions.md`.
3. Use `docs/examples/aws-oidc-trust-policy-plan-and-output.json` for the Terraform plan role, because PRs and main-branch pre-promotion plans still use a read-only role.
4. Set GitHub repository variables: `AWS_REGION`, `AWS_TERRAFORM_PLAN_ROLE_ARN`, `AWS_TERRAFORM_APPLY_ROLE_ARN`, `AWS_PROD_ROLE_ARN`, and `TF_VAR_ANALYTICS_ALARM_EMAIL`.
5. Run a plain `terraform apply` so Terraform creates the hosted zone, requests the ACM certificates, and starts the full custom-domain infrastructure rollout.
6. If that first apply stops at ACM validation, read `manual_dns_validation_records` and `manual_dns_prerequisites` from Terraform output or state, then create those validation `CNAME`s at the live DNS provider. Before Cognito can create `auth.formoseaniap.com`, AWS requires the parent domain `formoseaniap.com` to resolve through a real public `A` record. If Cloudflare is still authoritative, do not rely only on proxying or apex CNAME flattening for this step; create a temporary `DNS only` apex `A` record, rerun apply until the Cognito custom domain succeeds, and then replace that temporary record with the final site cutover record.
7. Rerun the same plain `terraform apply` after ACM validation has propagated so Terraform can validate the certificates, attach the site aliases, create the canonical-host redirect function, and create `https://auth.formoseaniap.com` plus its branding.
8. Create the final live DNS records from `manual_dns_site_cutover_records` and `manual_dns_auth_cutover_record`. For Cloudflare, use `DNS only`; the apex record should use Cloudflare CNAME flattening to the CloudFront hostname.
9. After the custom-domain apply finishes, manually create the first Cognito admin user with `username`, `name`, and `email`, then add that user to the `analytics-admin` group if the pool is new or has been replaced.
10. Verify `https://www.formoseaniap.com`, the apex redirect, the legacy CloudFront redirect, `/podcasts/*`, `/analytics-api/*`, and `/admin/analytics.html` on the custom domains.
11. Run `AWS OIDC Smoke` against a `prod` environment-scoped role.
12. Review the optional Terraform plan artifact from `Push Main` when it is available, then approve the protected `prod` environment.
13. Let the gated `Push Main` workflow always run Terraform plan/apply against the production stack and deploy the generated site; it reads `site_bucket_name`, `cloudfront_distribution_id`, and analytics runtime config outputs from Terraform remote state, so separate production bucket/distribution variables are not required.
14. After the monitoring resources are first applied, confirm the SNS email subscription sent to `TF_VAR_ANALYTICS_ALARM_EMAIL`, then verify the CloudWatch alarms and dashboard.

## Style Direction

Reference inspiration:
- https://p5aholic.me/
- https://shoya-kajita.com/
- https://edwinle.com/

Design direction:
- Japanese-style minimalism
- Strong typography and whitespace
- Subtle animation and calm visual tone
- Clear content hierarchy

## Non-Goals (Current)

- Backend CMS before content workflow stabilizes
- Database-backed article management
- Heavy animation frameworks that reduce maintainability

## Development Principles

- Keep it simple first, then iterate.
- Prefer maintainability over premature complexity.
- Build for long-term clarity and extensibility.
- Let the platform reflect both engineering rigor and personal style.
