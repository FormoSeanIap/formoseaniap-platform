# Terraform Home

This directory contains the production infrastructure root stack for this repository.

Current convention:

- Keep repository-managed Terraform under `infra/`.
- Use one root stack in this directory until there is a concrete reason to split it.
- The root stack currently targets the `hashicorp/aws` provider `~> 6.0`.
- Store remote state in the existing S3 backend bucket `formoseaniap-platform-tfstate-760259504838-ap-northeast-1-an`.
- Use pull requests into `develop` or `main` for `terraform fmt -check`, `terraform validate`, and optional `terraform plan`.
- Use the manual `Terraform Apply Prod` workflow for production applies.
- Do not auto-apply Terraform on every push to `main`.

Current production stack:

- Creates a private S3 bucket for the static site origin.
- Blocks all public S3 access and enables bucket-owner-enforced ownership, SSE-S3 encryption, and versioning.
- Creates a CloudFront distribution with Origin Access Control for the private S3 origin.
- Defaults CloudFront pay-as-you-go traffic to `PriceClass_100` to minimize cost until Terraform supports CloudFront flat-rate plans.
- Uses AWS-managed CloudFront cache policies only: `CachingOptimized` for the static site and `CachingDisabled` for `/podcasts/*`, so the distribution avoids Business-only custom caching rules and stays eligible for later Free/Pro flat-rate plan changes in the AWS console.
- Routes `/podcasts/*` through the same CloudFront distribution to the SoundOn RSS origin `feeds.soundon.fm`.
- Uses the default CloudFront certificate until a custom domain is purchased and added later.
- Does not provision the old Lambda Function URL podcast proxy. The local Python proxy remains available for localhost preview only.

Operational caveat:

- If you manually subscribe the CloudFront distribution to a flat-rate plan in the AWS console, Terraform cannot currently manage or cancel that subscription.
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

`Deploy Site Prod` reads these from Terraform remote state at run time, so they do not need separate GitHub repository variables.

If you later split infrastructure into multiple stacks or modules, update the Terraform workflows to target each stack explicitly instead of scattering `.tf` files across the repository.
