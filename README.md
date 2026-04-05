# Personal Portfolio Platform

Long-term portfolio platform for identity, technical work, and writing.

This project is static-first and deploys to S3/CloudFront without backend APIs or databases.

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

## Current State (April 4, 2026)

Implemented:
- Shared static pages and branding across Home / Projects / Articles / About.
- Consistent design system via `site/assets/css/*` and `site/assets/js/main.js`.
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

## Architecture

Static-only runtime:
- S3 serves HTML/CSS/JS/JSON/XML files.
- No API server and no runtime database.

Build-time flow:
1. Author Markdown in `content/articles/**`
2. Run Python build script
3. Script writes generated artifacts into `site/data/` and `site/rss.xml`
4. Deploy `site/` to S3

## Repository Structure

```text
/
- .github/
  - workflows/
    - aws-oidc-smoke.yml        manual GitHub OIDC -> AWS trust smoke test
- .codex/
  - config.toml                 repo-local Codex sandbox/approval defaults
  - skills/
    - static-site-ui-review/     repo-local Codex skill for frontend UI review
- content/
  - articles/
  - tags.json
  - site.json
- docs/
  - aws-oidc-github-actions.md  GitHub Actions -> AWS OIDC setup notes
  - examples/
    - aws-oidc-trust-policy-branch.json
    - aws-oidc-trust-policy-environment.json
  - inbox.md                quick todo capture
  - backlog.md              curated implementation backlog
- scripts/
  - build_articles.py
  - dedupe_bilingual_images.py
- site/
  - assets/
  - data/                    generated article JSON
    - articles.search.json   lazy-loaded article search index
    - projects.json          project listing data
  - articles.html            list/filter page
  - article.html             detail page
  - projects.html            project list page
  - rss.xml                  generated EN feed
  - zh/rss.xml               generated ZH feed
- README.md
```

## Repo-Local Codex Skills

- `./.codex/skills/static-site-ui-review` provides a repo-specific frontend review workflow for this static site.
- Use it when reviewing or finalizing changes to `site/*.html`, `site/assets/css/**`, `site/assets/js/**`, or article list/detail rendering behavior.

## Repo-Local Codex Config

- `./.codex/config.toml` sets this repository to `workspace-write` with `approval_policy = "on-request"`.
- In a trusted project, that means Codex can read, edit, and run routine local commands inside this repo without prompting.
- Codex still asks for approval when it needs to go outside the workspace boundary or use network access.

## AWS OIDC Bootstrap

- `./.github/workflows/aws-oidc-smoke.yml` is a manual GitHub Actions workflow that validates GitHub OIDC -> AWS role assumption with `aws sts get-caller-identity`.
- `./docs/aws-oidc-github-actions.md` explains the role split and the bootstrap sequence for moving this repo onto AWS via GitHub Actions.
- `./docs/examples/aws-oidc-trust-policy-branch.json` and `./docs/examples/aws-oidc-trust-policy-environment.json` provide branch-scoped and environment-scoped IAM trust policy templates.

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
- Python 3.10+ (stdlib only, no pip dependencies required)

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

Generated outputs:
- `site/data/articles.index.json`
- `site/data/articles.search.json`
- `site/data/articles/en/*.json`
- `site/data/articles/zh/*.json`
- `site/assets/articles/**` (copied image assets referenced by markdown)
- `site/rss.xml`
- `site/zh/rss.xml`

## Local Preview

Use any static server that serves the `site/` directory.

Example:
```bash
cd site
python3 -m http.server 5500
```

Then open:
- `http://127.0.0.1:5500/articles.html`
- `http://127.0.0.1:5500/articles.html?lang=en&lang=zh&category=review&subcategory=Anime_Manga`
- `http://127.0.0.1:5500/article.html?id=terraform-modules-small&lang=en`
- `http://127.0.0.1:5500/articles.html?series=<series_id>&lang=en&lang=zh`
- `http://127.0.0.1:5500/projects.html`

Collection-first list page UX:
- `articles.html` shows collection/work cards by default rather than raw article cards.
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

## Deployment Plan

Target infrastructure:
- S3 static website hosting
- CloudFront CDN + HTTPS
- Optional custom domain

CI/CD recommendations:
- Trigger on push to `main`
- Run `python3 scripts/build_articles.py`
- Sync `site/` to S3
- Invalidate CloudFront cache when needed

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
