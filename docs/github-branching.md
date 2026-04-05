# GitHub Branching and Environment Workflow

This repository now uses trunk-based branching.

## Branch Model

- `main` is the only long-lived branch and the production deployment source.
- Open short-lived branches from the latest `main` using `feature/`, `fix/`, `chore/`, `docs/`, or `hotfix/`.
- Merge back with a pull request into `main`.
- Prefer squash merges so each merged pull request lands as one reviewed change on `main`.

## GitHub Settings To Apply

1. Set the default branch to `main`.
2. Protect `main`:
   - require pull requests before merging
   - require the `validate` job from `PR Validate`
   - block force pushes
   - block direct deletion
3. In repository settings:
   - enable auto-delete for merged branches
   - make squash merge the default or only merge strategy
4. Create GitHub environments:
   - `preview` for optional PR preview deploys
   - `prod` for production site deploys and manual Terraform apply
5. Protect `prod` with required reviewers before AWS credentials are issued.

## Current Migration Off `develop`

1. Merge the current `develop` work into `main`.
2. Retarget any open pull requests from `develop` to `main`.
3. Stop opening new work from `develop`.
4. Delete `develop` after `main` is the source of truth.
5. Rebase or merge stale feature branches onto `main` before continuing work.

## Repo Variables For Workflow Activation

Set these as GitHub repository variables when the AWS side is ready:

- `AWS_REGION`
- `AWS_PREVIEW_ROLE_ARN`
- `PREVIEW_S3_BUCKET`
- `PREVIEW_BASE_URL` (optional)
- `PREVIEW_CLOUDFRONT_DISTRIBUTION_ID` (optional)
- `AWS_PROD_ROLE_ARN`
- `PROD_S3_BUCKET`
- `PROD_CLOUDFRONT_DISTRIBUTION_ID` (optional)
- `AWS_TERRAFORM_PLAN_ROLE_ARN`
- `AWS_TERRAFORM_APPLY_ROLE_ARN`

## Resulting Workflow Split

- `PR Validate`: tests, site build, and generated-artifact drift check on pull requests to `main`
- `PR Preview`: preview artifact on every pull request and optional hosted preview deploy
- `Deploy Site Prod`: build on `main` and deploy only the static `site/` output to production
- `Terraform Plan`: enforce `infra/` placement and run Terraform checks on pull requests
- `Terraform Apply Prod`: manual, production-gated apply from `main`
