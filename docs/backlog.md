# Backlog

Curated follow-up work for the portfolio platform.

## Now

- _None_

## Next

- [ ] Fix the backend analytics collector Lambda
  - Why: the backend Lambda that sends platform analytics is currently failing or unreliable, which means analytics data cannot be trusted until the collector path is repaired.
  - Scope: inspect the current Lambda handler, identify the failure mode, fix the analytics submission flow, and verify that expected analytics events are emitted successfully without breaking the rest of the backend path.
  - Done when: the analytics collector Lambda runs without the known error and platform analytics are recorded successfully in the intended destination.

- [ ] Add backend Lambda monitoring with email alarms
  - Why: backend failures should be detected automatically instead of waiting for manual checks, especially for the analytics collector and other Lambda-backed functionality.
  - Scope: define the key Lambda CloudWatch metrics to monitor, create alarms for error conditions, wire the alarms to an email notification path such as SNS, and verify that alarm delivery works end to end.
  - Done when: Lambda error metrics trigger CloudWatch alarms and an email notification is delivered to the configured recipient when a backend issue is detected.

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

- [ ] Complete the `formoseaniap.com` cutover while Cloudflare remains authoritative
  - Why: the infrastructure now supports the branded production hostname, but Cloudflare must stay as the live DNS provider until the new-domain transfer lock expires.
  - Scope: run a plain `terraform apply`, create the ACM validation records manually in Cloudflare from the Terraform manual-DNS outputs if the first apply stops at validation, rerun the same plain apply, then add the final cutover records in Cloudflare, verifying `www` as the canonical host plus apex and legacy CloudFront redirects.
  - Done when: `https://www.formoseaniap.com` is the canonical public site, `https://formoseaniap.com` and the old CloudFront hostname redirect there, and `https://auth.formoseaniap.com` is serving Cognito managed login for the admin flow while Cloudflare remains the live DNS authority.

- [ ] Transfer `formoseaniap.com` DNS authority to Route 53 and then enable DNSSEC
  - Why: the current Cloudflare-authoritative setup requires manual DNS mirroring; after the transfer hold expires, Route 53 should become the single source of truth and DNSSEC can be enabled there cleanly.
  - Scope: once the registrar lock window allows it, move nameserver control or the registrar itself so Route 53 becomes authoritative, remove the need to mirror records into Cloudflare, then design and implement DNSSEC as a follow-up in the now-authoritative Route 53 setup.
  - Done when: Route 53 is authoritative for `formoseaniap.com`, the live DNS records are served directly from the Terraform-managed hosted zone, and DNSSEC validates publicly without depending on manual Cloudflare DNS mirroring.
