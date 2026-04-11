# AWS OIDC for GitHub Actions

This repository includes a manual smoke-test workflow at `./.github/workflows/aws-oidc-smoke.yml`.

Use it to validate that GitHub Actions can assume an AWS IAM role through OIDC without storing long-lived AWS keys in GitHub.

## What This Gives You

- Short-lived AWS credentials per workflow run
- No `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` stored in GitHub secrets
- Tight trust boundaries by repository, branch, or GitHub environment

## Recommended Role Split

- `formoseaniap-platform-gha-deploy-prod`: production site deploy role scoped to the `prod` GitHub environment
- `formoseaniap-platform-gha-terraform-plan`: read-only Terraform plan role scoped to PR plans and pre-promotion plans on `main`
- `formoseaniap-platform-gha-terraform-apply-prod`: production Terraform apply role scoped to the `prod` GitHub environment
- `formoseaniap-platform-gha-preview`: optional future preview deploy role scoped to the `preview` GitHub environment

Keep the local AWS MCP role separate from GitHub Actions roles.

## AWS Setup

1. Create an IAM OIDC identity provider for `https://token.actions.githubusercontent.com` with audience `sts.amazonaws.com`.
2. Create the three production roles listed above and attach the matching trust policies under `docs/examples/`.
3. Attach the matching permissions policies under `docs/examples/`.
4. Run the smoke-test workflow manually against an environment-scoped role such as `formoseaniap-platform-gha-terraform-apply-prod`.
5. Set the repository variables used by the workflows.

## Trust Policy Options

- `docs/examples/aws-oidc-trust-policy-branch.json`
  Use this for manual smoke tests or other jobs that should only run from one branch such as `main`.
- `docs/examples/aws-oidc-trust-policy-environment.json`
  Use this for jobs that should require the protected `prod` GitHub environment. Attach this to `formoseaniap-platform-gha-deploy-prod` and `formoseaniap-platform-gha-terraform-apply-prod`.
- `docs/examples/aws-oidc-trust-policy-pull-request.json`
  Use this for jobs that only need PR-triggered OIDC without a GitHub environment.
- `docs/examples/aws-oidc-trust-policy-plan-and-output.json`
  Use this for `formoseaniap-platform-gha-terraform-plan`, which runs Terraform plan from PR-triggered jobs and pre-promotion plan jobs on `main`.

The trust policy examples are prefilled for:

- AWS account `760259504838`
- GitHub repo `FormoSeanIap/formoseaniap-platform`
- `prod`

If the repo or account changes, update those values before attaching the policies.

## Permissions Policy Options

- `docs/examples/aws-oidc-policy-deploy-prod.json`
  Attach to `formoseaniap-platform-gha-deploy-prod`. It can sync objects into the production site bucket and create CloudFront invalidations.
- `docs/examples/aws-oidc-policy-terraform-plan.json`
  Attach to `formoseaniap-platform-gha-terraform-plan`. It can read Terraform-managed S3/CloudFront resources and use the S3 state lock file.
- `docs/examples/aws-oidc-policy-terraform-apply-prod.json`
  Attach to `formoseaniap-platform-gha-terraform-apply-prod`. It can manage the private S3 site bucket, CloudFront distribution, cache policies, OAC, and Terraform state.

The first-pass Terraform apply policy intentionally grants broad CloudFront access because CloudFront resource-level support is limited across management actions. Tighten the policy after the distribution IDs are stable if needed.

## Smoke Test Workflow

The workflow is manual on purpose. It only:

1. Requests an OIDC token from GitHub
2. Assumes the AWS role you pass in
3. Runs `aws sts get-caller-identity`

That is enough to verify the trust policy and the GitHub-side `id-token: write` permission before you add real deploy steps.

## Workflow Mapping For This Repo

- `aws-oidc-smoke.yml`
  Manual bootstrap check for OIDC trust and AWS role assumption. The workflow now accepts a `github_environment` input and defaults to `prod`, so it can test environment-scoped roles.
- `pr-validate.yml`
  PR validation plus optional preview deploy and optional Terraform plan. The workflow runs shared Terraform validation first, and preview waits for the Terraform PR checks to complete. Because the preview deploy job uses the `preview` environment, the OIDC subject should be environment-scoped. The Terraform plan job does not use a GitHub environment, so its OIDC subject remains `pull_request`.
- `push-main.yml`
  Production promotion from `main`. It re-runs the shared site validation path, reuses the shared Terraform validation path for changed Terraform files, can publish a pre-promotion Terraform plan artifact through the read-only plan role, then waits on the protected `prod` environment before always running Terraform plan/apply with the production apply role and deploying the site with the production deploy role.
## GitHub Variables Expected By The Workflows

- `AWS_REGION`: `ap-northeast-1`
- `AWS_PROD_ROLE_ARN`: `arn:aws:iam::760259504838:role/formoseaniap-platform-gha-deploy-prod`
- `AWS_TERRAFORM_PLAN_ROLE_ARN`: `arn:aws:iam::760259504838:role/formoseaniap-platform-gha-terraform-plan`
- `AWS_TERRAFORM_APPLY_ROLE_ARN`: `arn:aws:iam::760259504838:role/formoseaniap-platform-gha-terraform-apply-prod`
- `AWS_PREVIEW_ROLE_ARN` (optional)
- `PREVIEW_S3_BUCKET` (optional)
- `PREVIEW_BASE_URL` (optional)
- `PREVIEW_CLOUDFRONT_DISTRIBUTION_ID` (optional)

`push-main.yml` reads `site_bucket_name` and `cloudfront_distribution_id` from Terraform remote state after the gated Terraform stage, so `PROD_S3_BUCKET` and `PROD_CLOUDFRONT_DISTRIBUTION_ID` repository variables are not required.

## Next Steps For This Repo

When the new AWS account is ready:

1. Create the OIDC identity provider if it does not already exist.
2. Create the GitHub Actions roles using the trust policy and permissions policy templates above.
3. Protect the `prod` GitHub environment before AWS credentials are issued.
4. Run the smoke-test workflow with `github_environment=prod`, `aws_region=ap-northeast-1`, and one prod environment-scoped role ARN.
5. Set `AWS_REGION`, `AWS_TERRAFORM_PLAN_ROLE_ARN`, `AWS_TERRAFORM_APPLY_ROLE_ARN`, and `AWS_PROD_ROLE_ARN`.
6. Merge or push the release to `main`.
7. Review the optional Terraform plan artifact from `Push Main` when it is available.
8. Approve the `prod` environment in the `Push Main` workflow from `push-main.yml` so it can always run Terraform plan/apply against production and deploy the site.
