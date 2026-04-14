# Terraform Home

This directory contains the production infrastructure root stack for this repository.

Current convention:

- Keep repository-managed Terraform under `infra/`.
- Use one root stack in this directory until there is a concrete reason to split it.
- The root stack currently targets the `hashicorp/aws` provider `~> 6.0`.
- Store remote state in the existing S3 backend bucket `formoseaniap-platform-tfstate-760259504838-ap-northeast-1-an`.
- Use pull requests into `develop` or `main` for `terraform fmt -check`, `terraform validate`, and optional `terraform plan`.
- Let the protected `Push Main` workflow own production `terraform plan` / `terraform apply` after approval at the `prod` environment gate.
- Run `python3 scripts/terraform_validate_strict.py` from the repo root for the local Terraform validation path used by CI.
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
  - Cognito User Pool, App Client, hosted-login domain, `analytics-admin` group, and managed-login configuration for username-based admin login
- Creates the Route 53 public hosted zone for `formoseaniap.com` as the future authoritative zone once the registrar and DNS move are possible.
- Includes the full custom-domain infrastructure in the default stack:
  - ACM certificates in `us-east-1` for the site and Cognito auth domain
  - Route 53 validation records and alias records for the future transfer
  - CloudFront aliases for `formoseaniap.com` and `www.formoseaniap.com`
  - a CloudFront viewer-request function that redirects any non-canonical host to `https://www.formoseaniap.com`
  - Cognito custom domain `https://auth.formoseaniap.com`
  - Cognito managed-login branding JSON + SVG assets stored in this repo
- Ignores CloudFront `web_acl_id` drift in Terraform because flat-rate plan subscriptions can auto-create and require a console-managed WAF web ACL.
- Does not provision the old Lambda Function URL podcast proxy. The local Python proxy remains available for localhost preview only.

Important staged variables:

- `site_root_domain` defaults to `formoseaniap.com`.
- `site_canonical_subdomain` defaults to `www`.
- `analytics_auth_subdomain` defaults to `auth`.

Important outputs:

- `site_bucket_name`
- `cloudfront_distribution_id`
- `analytics_runtime_config`
- `manual_dns_prerequisites`
- `manual_dns_validation_records`
- `manual_dns_site_cutover_records`
- `manual_dns_auth_cutover_record`
- `route53_zone_name_servers`
- `site_public_base_url`
- `analytics_auth_domain_url`

`Push Main` reads the remote-state outputs at deploy time, writes the live analytics runtime config into the built site artifact, and then syncs the site to production.

Operational caveats:

- If you manually subscribe the CloudFront distribution to a flat-rate plan in the AWS console, Terraform cannot currently manage or cancel that subscription.
- When the distribution is on a flat-rate plan, leave `cloudfront_price_class = null`. If you later move back to pay-as-you-go, set a value such as `PriceClass_100` explicitly.
- Flat-rate plan subscriptions can also auto-attach a required WAF web ACL. Terraform currently leaves that association alone instead of trying to import or replace the console-managed web ACL.
- `terraform destroy` may fail to delete the distribution until you manually unsubscribe it in the console and wait for the cancellation to take effect at the end of the current billing cycle.
- Do not try to copy the Route 53 alias records directly into Cloudflare. Use the manual DNS outputs instead. Route 53 alias records become Cloudflare `CNAME` records, with Cloudflare apex flattening used for `formoseaniap.com`.

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

Live rollout sequence for `formoseaniap.com` while Cloudflare remains authoritative:

1. Run a plain `terraform apply` so Terraform creates the hosted zone, requests the ACM certificates, and starts the full custom-domain rollout.
2. If the apply stops at ACM validation, read `manual_dns_validation_records` and `manual_dns_prerequisites` from Terraform output or state.
3. Create the validation CNAME records at the live DNS provider from `manual_dns_validation_records`.
4. Before rerunning apply, make sure `formoseaniap.com` resolves publicly through a real `A` record. Amazon Cognito checks the parent of `auth.formoseaniap.com` this way and can still reject a Cloudflare-proxied or apex-flattened setup even if external `dig` output already shows an address.
5. If the live DNS provider is Cloudflare, keep the validation records `DNS only`. If needed, temporarily replace the apex cutover record with a `DNS only` placeholder `A` record until the Cognito custom domain is created, then switch the apex back to the final site cutover record.
6. Rerun the same plain `terraform apply` after ACM validation has propagated.
7. Create the final live DNS records from `manual_dns_site_cutover_records` and `manual_dns_auth_cutover_record`. If the live DNS provider is Cloudflare, use `DNS only` and rely on Cloudflare CNAME flattening for the apex record.
8. Verify the site, apex redirect, legacy CloudFront redirect, analytics admin login/logout, `/podcasts/*`, and `/analytics-api/*`.
9. When the registrar lock expires and Route 53 can become authoritative, switch over to the Route 53 nameservers from Terraform output.

Analytics auth notes:

- `public_site_base_url` is optional. If left blank, Terraform derives the correct origin from the current rollout stage:
  - CloudFront default hostname before custom-domain cutover
  - `https://www.formoseaniap.com` after the full custom-domain apply succeeds
- The browser-facing `analytics_runtime_config` JSON contract stays stable. Only the deployed values change between rollout stages.
- Terraform provisions the user pool, app client, domain, branding, and admin group, but does not create the first admin user.
- After apply, manually create the admin user with `username`, `name`, and `email`, then add that user to the `analytics-admin` Cognito group before testing `/admin/analytics.html`.
- Rebuilding the analytics user pool is a direct cutover: existing admin sessions become invalid and the admin user must be bootstrapped again in the replacement pool.

If you later split infrastructure into multiple stacks or modules, update the Terraform workflows to target each stack explicitly instead of scattering `.tf` files across the repository.
