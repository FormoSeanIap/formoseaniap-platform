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

- [ ] Run `terraform plan` on normal pushes when infra files change
  - Why: today `push-others.yml` only calls `_terraform-validate-shared.yml` (local `fmt`/`init`/`validate`). The actual `terraform plan` — which catches IAM permission errors, missing resources, and provider bugs — only runs inside `pr-validate.yml`. This means infra breakages are not surfaced until a PR is opened.
  - Scope:
    1. In `.github/workflows/push-others.yml`, add `id-token: write` to the top-level `permissions` block (needed for OIDC).
    2. Add a new `terraform_plan` job after `terraform_validate`, gated on `needs.terraform_validate.outputs.has_tf_changes == 'true' && needs.terraform_validate.outputs.has_tf_root == 'true'` (same condition used in `pr-validate.yml`).
    3. The job should: checkout → setup Terraform → configure AWS credentials via OIDC using `vars.AWS_TERRAFORM_PLAN_ROLE_ARN` → `terraform init` → `terraform plan -input=false -no-color`. No need to upload plan artifacts (that is only useful for PR review).
    4. Include the same "Note plan status when AWS is not configured" guard step so the job degrades gracefully when repo variables are missing.
    5. Use `role-session-name: gha-terraform-plan-push-${{ github.run_number }}` to distinguish push-plan sessions from PR-plan sessions in CloudTrail.
    6. Consider extracting the plan steps into a shared composite action (e.g. `.github/actions/terraform-plan`) to avoid duplicating the logic between `pr-validate.yml` and `push-others.yml`. If extracted, update both callers.
  - Done when: a push to `develop` or a feature branch that touches `infra/**` triggers a `terraform plan` against live AWS state, and the workflow fails visibly if the plan fails.

## Later

- [ ] Add custom domain for the production site
  - Why: the site will eventually need a branded public hostname instead of the default CloudFront domain.
  - Scope: buy the domain, request the viewer certificate in ACM `us-east-1`, add the Route 53 hosted zone and alias records, attach the certificate and aliases to the CloudFront distribution, and update any deploy/runtime configuration that currently assumes provider-generated URLs.
  - Done when: the production site is reachable on the purchased domain over HTTPS and the old CloudFront hostname is no longer the primary public entrypoint.
