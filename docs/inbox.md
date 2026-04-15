# Inbox

Use this file for fast, low-friction capture when an idea appears before it is ready to be planned.

- Add new items near the top.
- Keep each entry short.
- Move items into `docs/backlog.md` once they are concrete enough to prioritize or implement.

## Open

- Article TODO: “How I built this platform with VS Code (Copilot) / ‘vice coding’”
  - [ ] Decide the article framing (devlog vs. guide) + target reader (solo builder, infra-curious, content-migration pain)
  - [ ] List a simple timeline of milestones (first deploy → DNS → content import → CI/CD → stable prod)
  - [ ] Collect the 5–10 most useful “before/after” artifacts to include (screenshots, error messages, diffs, commands)
  - [ ] Draft structure (sections + bullet notes), then expand each section into prose
  - [ ] Add a short “what I’d do differently next time” section
  - DNS + Cloudflare (can’t use nameservers)
    - [ ] Write the constraint clearly: what prevented using Cloudflare nameservers, and what you did instead (DNS records only)
    - [ ] Capture the concrete symptoms (what broke): SSL errors, wrong origin, bad redirects, propagation delays, etc.
    - [ ] Note the key records and reasoning (A/AAAA vs CNAME, apex handling/flattening, www redirect, TTL choices)
    - [ ] Write the debugging checklist you used (`dig`, Cloudflare dashboard checks, origin health checks)
    - [ ] End with “rules of thumb” you learned for Cloudflare + CDN/static hosting
  - Cloudflare Cache
    - [ ] Add the deploy/cache mismatch story: new CSS was live, but `about.html` still looked old because Cloudflare was serving stale HTML even after the GitHub Actions deploy succeeded
    - [ ] Record the evidence chain you used to confirm it: merged PR contents, successful `push-main` run, `about.html` uploaded to S3, CloudFront invalidation completed, live CSS updated first
    - [ ] Write the troubleshooting sequence: compare live HTML vs CSS, inspect response headers, separate CloudFront from Cloudflare behavior, then purge the exact URL in Cloudflare
    - [ ] Note the practical fix and prevention rule: purge Cloudflare for changed HTML pages or avoid caching HTML there if CloudFront is already the main CDN cache layer
  - Token limits / context limits while pairing with Copilot
    - [ ] Describe the failure mode: hitting token/context limits and losing important repo context
    - [ ] Write the tactics that worked: smaller prompts, one-file-at-a-time, ask for diffs, paste exact error output, pin requirements
    - [ ] Add 2–3 prompt templates you reused (e.g., “Given this error + these files, propose minimal patch”)
    - [ ] Document how you validated changes (tests you ran, `terraform_validate_strict`, smoke checks)
  - Medium → repo content migration (time sink)
    - [ ] Explain the goal and why it was hard (export format, embeds, images, bilingual assets, frontmatter)
    - [ ] Document the pipeline you ended up with (which scripts, in what order)
    - [ ] List the top pitfalls (image hotlinks, filename normalization, duplicates, broken markdown, timestamps)
    - [ ] Provide the “repeatable workflow” you’d recommend to someone else
  - Article organization logic (bilingual + series + categories)
    - [ ] Describe the content model constraints: bilingual versions of the “same” piece, series membership, and standalone articles
    - [ ] Explain the initial taxonomy idea (main categories + tags) and why it didn’t scale
    - [ ] Document the pivot: adding subcategories to make browsing and filtering usable
    - [ ] Write down the rules you ended up using (how you map language variants, series, and category/subcategory in metadata)
    - [ ] Call out how AI plan mode helped (breaking the problem into decisions, tradeoffs, and a step-by-step migration plan)
  - Infra choice and cost control
    - [ ] Explain why AWS was the right fit for this platform (familiarity, full control, existing mental model)
    - [ ] Describe the cost concern and why that mattered early, not after launch
    - [ ] Note the cost alarm you added so you can catch accidental spending before it grows
    - [ ] Summarize how AI + AWS docs helped you compare options and converge on the cheapest workable setup
    - [ ] Mention the CloudFront Flat-rate pricing plans as the standout option for cost control
    - [ ] Explain the Terraform limitation: the AWS Go SDK does not support that CloudFront pricing mode yet, so part of the rollout has to be done manually in the AWS console
    - [ ] Add a short note about the tradeoff: infra as code for most of the stack, with one deliberate manual step until the toolchain catches up
  - Podcast CORS issue (fetching RSS/content)
    - [ ] Describe the exact browser error and constraints (cross-origin fetch from a static site)
    - [ ] Summarize the initial AI-proposed solution (why it was plausible, what assumptions it made)
    - [ ] Explain what ultimately worked after discussing with a CloudFront-familiar colleague (routing/proxying strategy)
    - [ ] Note the key lesson: “same-origin via CloudFront behavior/origin routing” vs trying to fix CORS on third-party feeds
    - [ ] Add a quick debug checklist (Network tab, response headers, CloudFront behavior match, cache invalidation gotchas)
  - GitHub Actions → AWS IAM role assumption (OIDC)
    - [ ] Explain the mental model: GitHub Actions OIDC token → AWS STS AssumeRoleWithWebIdentity → scoped permissions
    - [ ] Add the minimal moving parts checklist (workflow permissions, AWS OIDC provider, role trust policy, permission policy)
    - [ ] Include at least one real debugging story (common `AccessDenied` / mis-scoped `sub` / wrong audience)
    - [ ] Summarize the security lesson: least privilege + environment/branch scoping
