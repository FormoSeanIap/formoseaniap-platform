# AWS OIDC for GitHub Actions

This repository includes a manual smoke-test workflow at `./.github/workflows/aws-oidc-smoke.yml`.

Use it to validate that GitHub Actions can assume an AWS IAM role through OIDC without storing long-lived AWS keys in GitHub.

## What This Gives You

- Short-lived AWS credentials per workflow run
- No `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` stored in GitHub secrets
- Tight trust boundaries by repository, branch, or GitHub environment

## Recommended Role Split

- `gha-preview`: optional preview deploy role scoped to the `preview` GitHub environment
- `gha-deploy-prod`: production site deploy role scoped to the `prod` GitHub environment
- `gha-terraform-plan`: read-only Terraform plan role scoped to `pull_request` jobs
- `gha-terraform-apply-prod`: production Terraform apply role scoped to the `prod` GitHub environment

Keep the local AWS MCP role separate from GitHub Actions roles.

## AWS Setup

1. Create an IAM OIDC identity provider for `https://token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.
2. Create an IAM role for GitHub Actions and attach one of the trust policies under `docs/examples/`.
3. Attach the least-privilege permissions policy for the work that role needs to do.
4. Run the smoke-test workflow manually and pass the role ARN plus region.

## Trust Policy Options

- `docs/examples/aws-oidc-trust-policy-branch.json`
  Use this for manual smoke tests or other jobs that should only run from one branch such as `main`.
- `docs/examples/aws-oidc-trust-policy-environment.json`
  Use this for jobs that should require a protected GitHub environment such as `preview` or `prod`.
- `docs/examples/aws-oidc-trust-policy-pull-request.json`
  Use this for PR-triggered jobs such as `Terraform Plan` when the job does not reference a GitHub environment.

Replace these placeholders before use:

- `123456789012`
- `YOUR_ORG`
- `YOUR_REPO`
- `main`
- `prod`
- `preview`

## Smoke Test Workflow

The workflow is manual on purpose. It only:

1. Requests an OIDC token from GitHub
2. Assumes the AWS role you pass in
3. Runs `aws sts get-caller-identity`

That is enough to verify the trust policy and the GitHub-side `id-token: write` permission before you add real deploy steps.

## Workflow Mapping For This Repo

- `aws-oidc-smoke.yml`
  Manual bootstrap check for OIDC trust and AWS role assumption.
- `pr-preview.yml`
  Optional preview deploy. Because the deploy job uses the `preview` environment, the OIDC subject should be environment-scoped.
- `deploy-site-prod.yml`
  Production site deploy from `main`. Because the deploy job uses the `prod` environment, the OIDC subject should be environment-scoped.
- `terraform-plan.yml`
  PR-triggered validation and optional plan. Because the plan job does not use a GitHub environment, the OIDC subject should be `pull_request`.
- `terraform-apply-prod.yml`
  Manual production apply gated by the `prod` environment.

## GitHub Variables Expected By The Workflows

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

## Next Steps For This Repo

When the new AWS account is ready:

1. Create the OIDC identity provider
2. Create the GitHub Actions roles using the trust policy templates above
3. Run the smoke-test workflow with one role ARN to confirm trust
4. Set the repository variables used by the workflows
5. Protect the `prod` GitHub environment before enabling production deploys
