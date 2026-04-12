# Terraform Home

This directory contains the production infrastructure root stack for this repository.

Current convention:

- Keep repository-managed Terraform under `infra/`.
- Use one root stack in this directory until there is a concrete reason to split it.
- The root stack currently targets the `hashicorp/aws` provider `~> 6.0`.
- Store remote state in the existing S3 backend bucket `formoseaniap-platform-tfstate-760259504838-ap-northeast-1-an`.
- Use pull requests into `develop` or `main` for `terraform fmt -check`, `terraform validate`, and optional `terraform plan`.
- Run `python3 scripts/terraform_validate_strict.py` from the repo root for the local Terraform validation path used by CI.
- Use the manual `Terraform Apply Prod` workflow for production applies.
- Do not auto-apply Terraform on every push to `main`.
- Terraform deprecation warnings are treated as blocking in this repo even when plain `terraform validate` would only warn.
- Prefer Terraform MCP for current provider or module docs before editing Terraform, and fall back to local provider-schema inspection when docs are ambiguous.

Current production stack:

- Creates a private S3 bucket for the static site origin.
- Blocks all public S3 access and enables bucket-owner-enforced ownership, SSE-S3 encryption, and versioning.
- Creates a CloudFront distribution with Origin Access Control for the private S3 origin.
- Leaves CloudFront `price_class` unset while the distribution is on a console-managed flat-rate plan, because Free/Pro plans do not allow the price class feature on distribution updates.
- Uses AWS-managed CloudFront cache policies only: `CachingOptimized` for the static site and `CachingDisabled` for `/podcasts/*` and `/analytics-api/*`, so the distribution avoids Business-only custom caching rules and stays eligible for later Free/Pro flat-rate plan changes in the AWS console.
- Routes `/podcasts/*` through the same CloudFront distribution to the SoundOn RSS origin `feeds.soundon.fm`.
- Routes `/analytics-api/*` through the same CloudFront distribution to a regional API Gateway HTTP API.
- Creates a private analytics backend made of:
  - Lambda collector/admin handlers
  - DynamoDB daily counters + daily uniqueness tables
  - Cognito User Pool, App Client, Hosted UI domain, and `analytics-admin` group
- Uses the default CloudFront certificate until a custom domain is purchased and added later.
- Ignores CloudFront `web_acl_id` drift in Terraform because flat-rate plan subscriptions can auto-create and require a console-managed WAF web ACL.
- Does not provision the old Lambda Function URL podcast proxy. The local Python proxy remains available for localhost preview only.

Operational caveat:

- If you manually subscribe the CloudFront distribution to a flat-rate plan in the AWS console, Terraform cannot currently manage or cancel that subscription.
- When the distribution is on a flat-rate plan, leave `cloudfront_price_class = null`. If you later move back to pay-as-you-go, set a value such as `PriceClass_100` explicitly.
- Flat-rate plan subscriptions can also auto-attach a required WAF web ACL. Terraform currently leaves that association alone instead of trying to import or replace the console-managed web ACL.
- `terraform destroy` may fail to delete the distribution until you manually unsubscribe it in the console and wait for the cancellation to take effect at the end of the current billing cycle.

Remote backend:

```hcl
terraform {
  backend "s3" {
    bucket       = "formoseaniap-platform-tfstate-760259504838-ap-northeast-1-an"
    encrypt      = true
    key          = "infra/prod/terraform.tfstate"
    region       = "ap-northeast-1"
    use_lockfile = true
  }
}
```

Expected production outputs read by the deploy workflow:

- `site_bucket_name`
- `cloudfront_distribution_id`
- `analytics_runtime_config`

`Deploy Site Prod` reads these from Terraform remote state at run time, writes the live analytics runtime config into the built site artifact, and then syncs the site to production.

Analytics auth notes:

- Set `public_site_base_url` if you want Cognito callback/logout URLs to use a custom production hostname; otherwise Terraform defaults to the CloudFront distribution domain.
- Terraform provisions the user pool, app client, domain, and admin group, but does not create the first admin user.
- After apply, manually create the admin user and add it to the `analytics-admin` Cognito group before testing `/admin/analytics.html`.

If you later split infrastructure into multiple stacks or modules, update the Terraform workflows to target each stack explicitly instead of scattering `.tf` files across the repository.
