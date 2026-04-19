variable "aws_region" {
  default     = "ap-northeast-1"
  description = "AWS region for regional resources such as the private S3 site origin."
  type        = string
}

variable "cloudfront_price_class" {
  default     = null
  description = "Optional CloudFront edge location price class for pay-as-you-go distributions. Leave null when the distribution is on a console-managed flat-rate plan."
  nullable    = true
  type        = string
}

variable "cloudfront_wait_for_deployment" {
  default     = true
  description = "Whether Terraform should wait for CloudFront distribution changes to finish deploying."
  type        = bool
}

variable "static_site_cache_policy_id" {
  default     = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  description = "CloudFront cache policy ID for static site objects. Defaults to AWS-managed CachingOptimized so the distribution avoids Business-only custom caching rules."
  type        = string
}

variable "default_root_object" {
  default     = "index.html"
  description = "CloudFront default root object for the static site."
  type        = string
}

variable "environment" {
  default     = "prod"
  description = "Deployment environment name."
  type        = string
}

variable "podcast_feed_cache_policy_id" {
  default     = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  description = "CloudFront cache policy ID for proxied podcast RSS feed responses. Defaults to AWS-managed CachingDisabled to keep feed reads fresh without custom caching rules."
  type        = string
}

variable "podcast_feed_origin_domain" {
  default     = "feeds.soundon.fm"
  description = "Third-party podcast RSS origin domain routed through CloudFront."
  type        = string
}

variable "podcast_feed_path_pattern" {
  default     = "/podcasts/*"
  description = "CloudFront behavior path pattern for same-origin podcast RSS feed reads."
  type        = string
}

variable "project_name" {
  default     = "formoseaniap-platform"
  description = "Project name prefix used for AWS resources."
  type        = string
}

variable "site_bucket_force_destroy" {
  default     = false
  description = "Whether Terraform can delete the site bucket even when objects exist. Keep false for production safety."
  type        = bool
}

variable "site_bucket_name" {
  default     = ""
  description = "Optional explicit private S3 site bucket name. Defaults to a project/environment/account/region-based name."
  type        = string
}

variable "site_bucket_versioning_enabled" {
  default     = true
  description = "Whether to enable versioning on the private S3 site bucket."
  type        = bool
}

variable "engineering_subdomain" {
  default     = "engineer"
  description = "Subdomain for the engineering portfolio site."
  type        = string
}

variable "engineering_site_bucket_name" {
  default     = ""
  description = "Optional explicit S3 bucket name for the engineering site. Defaults to a project/environment/account/region-based name."
  type        = string
}
