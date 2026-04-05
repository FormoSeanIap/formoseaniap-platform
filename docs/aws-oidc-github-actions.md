# AWS OIDC for GitHub Actions

This repository includes a manual smoke-test workflow at `./.github/workflows/aws-oidc-smoke.yml`.

Use it to validate that GitHub Actions can assume an AWS IAM role through OIDC without storing long-lived AWS keys in GitHub.

## What This Gives You

- Short-lived AWS credentials per workflow run
- No `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` stored in GitHub secrets
- Tight trust boundaries by repository, branch, or GitHub environment

## Recommended Role Split

- `gha-terraform-plan-dev`: read-only planning and validation in a dev account
- `gha-apply-dev`: deploy/apply role for dev
- `gha-deploy-prod`: production role restricted to a protected GitHub environment

Keep the local AWS MCP role separate from GitHub Actions roles.

## AWS Setup

1. Create an IAM OIDC identity provider for `https://token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.
2. Create an IAM role for GitHub Actions and attach one of the trust policies under `docs/examples/`.
3. Attach the least-privilege permissions policy for the work that role needs to do.
4. Run the smoke-test workflow manually and pass the role ARN plus region.

## Trust Policy Options

- `docs/examples/aws-oidc-trust-policy-branch.json`
  Use this when only one branch, such as `main`, should be able to assume the role.
- `docs/examples/aws-oidc-trust-policy-environment.json`
  Use this when you want production deploys to require a protected GitHub environment such as `prod`.

Replace these placeholders before use:

- `123456789012`
- `YOUR_ORG`
- `YOUR_REPO`
- `main`
- `prod`

## Smoke Test Workflow

The workflow is manual on purpose. It only:

1. Requests an OIDC token from GitHub
2. Assumes the AWS role you pass in
3. Runs `aws sts get-caller-identity`

That is enough to verify the trust policy and the GitHub-side `id-token: write` permission before you add real deploy steps.

## Next Step for This Repo

When the new AWS account is ready:

1. Create the OIDC identity provider
2. Create a dev role using one of the trust policy templates
3. Run the smoke-test workflow with that role ARN
4. After that works, add the real deploy workflow for S3 + CloudFront
