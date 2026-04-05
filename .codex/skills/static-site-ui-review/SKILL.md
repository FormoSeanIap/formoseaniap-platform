---
name: static-site-ui-review
description: Review and finalize frontend changes in this static portfolio repo. Use when tasks touch site/*.html, site/assets/css/**, site/assets/js/**, article list/detail rendering, responsive behavior, navigation, accessibility, typography, or visual regressions on the Home, Projects, Articles, and About pages.
---

# Static Site UI Review

## Overview

Review frontend changes in this repo with a static-site mindset. Prioritize readable content, stable layout, responsive behavior, and small purposeful JavaScript over framework-heavy solutions.

## Start With File Scope

- Map changed files to responsibility before editing:
  - `site/*.html`: page structure and content slots
  - `site/assets/css/variables.css`: tokens, colors, spacing scale, type scale, motion, max width
  - `site/assets/css/layout.css`: page shell, section spacing, grids, sticky header, breakpoints
  - `site/assets/css/components.css`: cards, chips, tags, article body styles, reusable UI pieces
  - `site/assets/js/main.js`: shared nav state, reveal animation, landing-page enhancement, footer year
  - `site/assets/js/articles.js`: article list/detail rendering, filters, series navigation, translation links
- Treat `content/articles/**` as source of truth when article content drives the change.
- Never hand-edit `site/data/**`; rebuild generated article data instead.

## Review Workflow

1. Identify whether the problem is structure, styling, behavior, or content/build output before changing files.
2. Read the smallest relevant HTML, CSS, and JS files together so layout and behavior are reviewed in context.
3. Check desktop and mobile behavior. Default to narrow-width review because content pages regress there first.
4. Run the smallest relevant verification:
   - Run `python3 scripts/build_articles.py` when article content or article rendering changes.
   - Preview `site/` with a simple static server when layout, filters, navigation, or page rendering changes.
5. Report findings first. Call out bugs, regressions, accessibility risks, and missing verification before offering summary or polish suggestions.

## Core Review Priorities

### Layout And Spacing

- Preserve a clear max width and comfortable whitespace.
- Check chip wrapping, card padding, section spacing, and header/footer alignment.
- Prefer fixing layout with CSS before adding JavaScript.

### Typography And Reading Experience

- Protect heading hierarchy, paragraph width, line height, and contrast.
- Optimize article pages for long-form reading before adding decorative changes.
- Avoid visually noisy styling that competes with the content.

### Responsive Behavior

- Verify behavior around the existing breakpoints in `site/assets/css/layout.css`, especially near `900px` and `680px`.
- Check sticky-header interactions, anchor offsets, filter rows, long titles, and image overflow.
- Confirm the mobile header remains usable after stacking.

### Interaction And Navigation

- Confirm active nav state from `site/assets/js/main.js`.
- Confirm filter chips, series navigation, translation links, and external article links from `site/assets/js/articles.js`.
- Preserve visible focus states and obvious link affordance.

### Accessibility

- Keep semantic HTML. Use links for navigation and buttons only for actions.
- Preserve `aria-label`, `aria-current`, `hidden`, and keyboard-focus behavior.
- Check that text remains legible against the dark theme.

## Page-Specific Checks

### Articles List

- Verify language, category, and tag filters reflect the current scope.
- Verify the series context banner only appears in series mode and its actions still work.
- Verify the empty state and chip wrapping still read cleanly.
- Confirm article cards still show series and part metadata correctly.

### Article Detail

- Verify title, excerpt, meta, tags, and article body render in the expected order.
- Verify the top and bottom action rows remain in sync.
- Verify `Back to top` lands correctly below the sticky desktop header.
- Verify series previous/next links and translation links remain coherent.
- Verify spacing for headings, lists, quotes, links, and images inside the article body.

### Shared Pages

- Verify shared shell consistency across `site/index.html`, `site/projects.html`, and `site/about.html`.
- Treat the landing-page orb effect as enhancement, not required layout logic.

## Decision Rules

- Edit `site/assets/css/variables.css` when the problem is global.
- Edit `site/assets/css/layout.css` when the issue is page shell, breakpoint behavior, or positioning across multiple components.
- Edit `site/assets/css/components.css` when the issue is localized to cards, chips, tags, or article body styling.
- Edit JavaScript only when HTML or CSS cannot solve the problem.
- Ask whether a change belongs in content, template, CSS, or JS before editing.

## Verification Checklist

- Preview at one desktop width and one mobile width.
- Check keyboard focus on the main nav and relevant filter/action chips.
- Check long article titles, excerpts, and tag combinations for wrapping problems.
- For article/detail changes, verify series pages, translations, and external-link mode if relevant.
- State explicitly what was not verified.

## Output Expectations

- For review requests, list findings by severity with concrete file references.
- State explicitly when no findings are discovered.
- Mention residual risks such as unverified mobile behavior, build output not regenerated, or manual preview not performed.
