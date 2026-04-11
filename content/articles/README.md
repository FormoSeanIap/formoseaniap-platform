# Articles Content Schema

Preferred source layout is semantic and work-first:

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

Minimum frontmatter:

```yaml
id: terraform-modules-small
lang: en # en | zh
title: ...
slug: ...
excerpt: ...
category: technical # technical | review | other
tags: [terraform, philosophy]
published_at: 2026-03-01
updated_at: 2026-03-02
read_time: 8
draft: false
```

Optional:

```yaml
external_url: https://medium.com/...
cover_image: /assets/img/articles/example.jpg
series_cover_image: ../Shared/collection-cover.jpg # optional collection card cover
series_id: devops-sre-diaries-maintenance-mode
series_title: DevOps SRE Diaries - Building A Reliable Maintenance Mode
series_order: 7 # optional explicit order within a shared series without forcing a visible Part label
part_number: 2
```

Rules:
- `id` must match between language versions.
- `slug` can differ by language if desired, but keeping it aligned reduces complexity.
- `tags` must use keys from `content/tags.json`.
- Put each article under the semantic subtree that matches it: `others`, `technical`, or `reviews/<type>`.
- For review articles, use the review medium folders (`Anime_Manga`, `Movie`, `TV_Drama`, `Book`, `Game`, `Novel`) when relevant.
- Standalone `\` line means a small pause between prose blocks.
- One blank line means a normal paragraph break.
- Two or more blank lines mean a larger pause.
- Do not use trailing `\` at the end of prose lines for spacing; reserve it for command examples inside code blocks.
- Use explicit image titles on image-only lines for captions: `![alt text](./image.png "Visible caption")`.
- The image title is rendered as the visible caption under the image block.
- Inline images inside paragraphs do not render visible captions.
- If the caption text contains double quotes, escape them as `\"` inside the image title.
- If English and Mandarin versions use the exact same image, store it once in a `Shared/` folder under the common work/article parent and reference it relatively.
- Keep images inside `English/` or `Mandarin/` only when the underlying binaries differ.
- Folder and asset names under `content/articles/**` must avoid `:"<>|*?` so generated site assets remain uploadable through GitHub Actions artifacts across filesystems.
- `series_cover_image` may be an absolute `/assets/...` path or a relative asset path from the markdown file.
- When multiple files belong to the same `series_id`, any non-empty `series_cover_image` values must resolve to the same final asset path or the build will fail.
- Prefer storing collection covers in an existing work-local `Shared/` folder so the cover lives with the source material and is copied into `site/assets/articles/**` automatically.
- Use a standalone `[Embedded media](https://www.youtube.com/embed/<video-id>)` line to render a supported embedded player inside the article.
- Supported embedded providers are YouTube (`youtube.com/embed`, `youtube.com/watch`, `youtu.be`) and Vimeo (`vimeo.com`, `player.vimeo.com/video/...`).
- Ordinary inline video links remain normal links; only the standalone `Embedded media` form is auto-embedded.
- Do not repeat the article title again as the first heading inside the markdown body; the article page renders the title from frontmatter.
- Do not place a standalone `---` immediately under frontmatter as a visual separator; it becomes redundant once the page header is rendered separately.
- Do not add manual translation links such as `English Version` / `中文版` inside the body.
- Do not add manual previous/next article lines inside the body; the site renders series navigation automatically.

Legacy support:
- The builder also supports deeply nested frontmatter-based files.
- The builder also supports deeply nested legacy files without frontmatter.
- For those files, metadata is inferred from path + markdown content.
- Series relationships are inferred from folder names like `Part1`, `Part2`, etc.

Build command:
- `python3 scripts/build_articles.py`

Localization helper:
- Dry-run Medium image localization: `python3 scripts/localize_medium_images.py <path>`
- Apply Medium image localization: `python3 scripts/localize_medium_images.py <path> --write`
- This downloads Medium CDN images referenced by markdown image embeds, stores them beside the markdown file, and rewrites the embed to `./image.ext`.
- Dry-run bilingual image deduplication: `python3 scripts/dedupe_bilingual_images.py`
- Apply bilingual image deduplication: `python3 scripts/dedupe_bilingual_images.py --write --verify`
- This moves exact EN/ZH duplicate images into a language-neutral `Shared/` folder and rewrites markdown refs accordingly.

Generated outputs:
- `site/data/articles.index.json`
- `site/data/articles.search.json`
- `site/data/articles/<lang>/<id>.json`
- `site/rss.xml`
- `site/zh/rss.xml`

Series navigation:
- Each article JSON may include `series_previous` and `series_next` so the detail page can link across parts.
- `series_order` can define the order inside a shared series without making the article itself display as a numbered part.
