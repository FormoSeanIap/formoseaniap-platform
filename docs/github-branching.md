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

## GitHub Settings To Apply

1. Keep the default branch set to `main`.
2. Protect `main`:
   - require pull requests before merging
   - require the `validate` job from `PR Validate`
   - block force pushes
   - block direct deletion
3. Protect `develop`:
   - require pull requests before merging
   - require the `validate` job from `PR Validate`
   - block force pushes
   - block direct deletion
4. In repository settings:
   - enable auto-delete for merged branches
   - make squash merge available for feature PRs
5. Create GitHub environments:
   - `preview` for optional PR preview deploys
   - `prod` for production site deploys and manual Terraform apply
6. Protect `prod` with required reviewers before AWS credentials are issued.

## Release Flow

1. Branch from `develop` for normal work.
2. Merge reviewed feature PRs into `develop`.
3. Let PR validation, preview, and Terraform plan run on `develop` PRs.
4. Open a release PR from `develop` to `main`.
5. Merge that release PR to trigger production deployment from `main`.

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

- `PR Validate`: tests, site build, and generated-artifact drift check on pull requests to `develop` and `main`
- `PR Preview`: preview artifact on every pull request to `develop` and `main`, plus optional hosted preview deploy
- `Deploy Site Prod`: build on `main` and deploy only the static `site/` output to production
- `Terraform Plan`: enforce `infra/` placement and run Terraform checks on pull requests to `develop` and `main`
- `Terraform Apply Prod`: manual, production-gated apply from `main`
