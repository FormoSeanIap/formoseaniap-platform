# GitHub Branching and Environment Workflow

This repository uses a two-tier branch model.

## Branch Model

- `main` is the default branch, the production deployment source, and the only branch that should trigger production deploys.
- `develop` is the long-lived integration branch for day-to-day work, PR validation, and preview testing.
- Open short-lived `feature/*`, `fix/*`, `chore/*`, and `docs/*` branches from the latest `develop`.
- Open `hotfix/*` branches from the latest `main`.
- Merge feature work into `develop` with pull requests.
- Release by opening a pull request from `develop` to `main`.

## Merge Policy

- Prefer squash merges for feature PRs into `develop` so integration history stays compact.
- Prefer a normal merge commit for `develop` to `main` release PRs so release boundaries remain visible in history.
- After merging a `hotfix/*` branch to `main`, immediately merge or cherry-pick the same fix back into `develop`.
- Direct pushes are not the preferred merge path, but push-time validation exists in `Push Others` for work branches and `develop`, while `Push Main` re-validates `main` inside the gated production workflow as a safety net for local merge-and-push cases.

## GitHub Settings To Apply

1. Keep the default branch set to `main`.
2. Protect `main`:
   - require pull requests before merging
   - require the `validate`, `terraform_validate`, and `terraform_plan` jobs from `PR Validate`
   - block force pushes
   - block direct deletion
3. Protect `develop`:
   - require pull requests before merging
   - require the `validate`, `terraform_validate`, and `terraform_plan` jobs from `PR Validate`
   - block force pushes
   - block direct deletion
4. In repository settings:
   - enable auto-delete for merged branches
   - make squash merge available for feature PRs
5. Create GitHub environments:
   - `preview` for optional PR preview deploys
   - `prod` for the gated production promotion stage on `main`
6. Protect `prod` with required reviewers before AWS credentials are issued.

## Release Flow

1. Branch from `develop` for normal work.
2. Merge reviewed feature PRs into `develop`.
3. Let PR validation, preview, and optional Terraform plan run on `develop` PRs.
4. Open a release PR from `develop` to `main`.
5. Merge that release PR to trigger the `main` production workflow.
6. Approve the protected `prod` environment in the same workflow run so `Push Main` can always run Terraform plan/apply against production and then deploy the generated site.

When a local merge is pushed directly to a work branch or `develop`, `Push Others` still runs, and both Terraform validation and live-state Terraform plan run automatically when Terraform-related files changed. A direct push to `main` still re-runs validation inside `Push Main` before the protected `prod` gate. That does not replace the preferred PR-based review path.

## Repo Variables For Workflow Activation

Set these as GitHub repository variables when the AWS side is ready:

- `AWS_REGION`: `ap-northeast-1`
- `AWS_PROD_ROLE_ARN`: `arn:aws:iam::760259504838:role/formoseaniap-platform-gha-deploy-prod`
- `AWS_TERRAFORM_PLAN_ROLE_ARN`: `arn:aws:iam::760259504838:role/formoseaniap-platform-gha-terraform-plan`
- `AWS_TERRAFORM_APPLY_ROLE_ARN`: `arn:aws:iam::760259504838:role/formoseaniap-platform-gha-terraform-apply-prod`
- `AWS_PREVIEW_ROLE_ARN` (optional)
- `PREVIEW_S3_BUCKET` (optional)
- `PREVIEW_BASE_URL` (optional)
- `PREVIEW_CLOUDFRONT_DISTRIBUTION_ID` (optional)

Production deploy reads `site_bucket_name` and `cloudfront_distribution_id` from Terraform remote state, so separate `PROD_S3_BUCKET` and `PROD_CLOUDFRONT_DISTRIBUTION_ID` variables are not required.

## Resulting Workflow Split

- `push-others.yml` (`Push Others`): tests, site build, generated-artifact drift checks, shared Terraform validation, and live-state Terraform plan on `feature/*`, `fix/*`, `chore/*`, `docs/*`, `hotfix/*`, and `develop` when infra files changed
- `pr-validate.yml` (`PR Validate`): tests, site build, generated-artifact drift check, shared Terraform validation, optional Terraform plan when infra files changed, preview artifact upload, and optional hosted preview deploy on pull requests to `develop` and `main`
- `push-main.yml` (`Push Main`): run the same validation path on `main`, optionally publish a pre-promotion Terraform plan artifact when the read-only plan role is configured, and wait at the protected `prod` environment before always running Terraform plan/apply plus site deploy
