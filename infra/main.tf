terraform {
  required_version = ">= 1.10.0"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

data "aws_caller_identity" "current" {}

locals {
  name_prefix                  = "${var.project_name}-${var.environment}"
  cloudfront_distribution_name = "${local.name_prefix}-site-cdn"
  site_apex_domain             = trimsuffix(var.site_root_domain, ".")
  site_canonical_domain        = "${var.site_canonical_subdomain}.${local.site_apex_domain}"
  analytics_auth_domain        = "${var.analytics_auth_subdomain}.${local.site_apex_domain}"
  custom_auth_domain_live      = try(aws_cognito_user_pool_domain.analytics_custom.domain, null) != null
  custom_site_domain_live      = try(aws_acm_certificate_validation.site.certificate_arn, null) != null
  s3_origin_id                 = "${local.name_prefix}-site-s3"
  soundon_origin_id            = "${local.name_prefix}-soundon-rss"
  site_bucket_name = (
    var.site_bucket_name != ""
    ? var.site_bucket_name
    : "${local.name_prefix}-site-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  )

  tags = {
    Environment = var.environment
    Project     = var.project_name
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket" "site" {
  bucket        = local.site_bucket_name
  force_destroy = var.site_bucket_force_destroy

  tags = merge(local.tags, {
    Name = local.site_bucket_name
  })
}

resource "aws_s3_bucket_public_access_block" "site" {
  bucket = aws_s3_bucket.site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "site" {
  bucket = aws_s3_bucket.site.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "site" {
  bucket = aws_s3_bucket.site.id

  versioning_configuration {
    status = var.site_bucket_versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "${local.name_prefix}-site-oac"
  description                       = "CloudFront access to the private ${local.site_bucket_name} S3 origin."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  aliases             = [local.site_apex_domain, local.site_canonical_domain]
  comment             = local.cloudfront_distribution_name
  default_root_object = var.default_root_object
  enabled             = true
  http_version        = "http2and3"
  is_ipv6_enabled     = true
  price_class         = var.cloudfront_price_class
  wait_for_deployment = var.cloudfront_wait_for_deployment

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id
    origin_id                = local.s3_origin_id
  }

  origin {
    domain_name = var.podcast_feed_origin_domain
    origin_id   = local.soundon_origin_id

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  origin {
    domain_name = replace(aws_apigatewayv2_api.analytics.api_endpoint, "https://", "")
    origin_id   = local.analytics_api_origin_id

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  origin {
    domain_name              = aws_s3_bucket.engineering_site.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.engineering_site.id
    origin_id                = local.engineering_s3_origin_id
  }

  default_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cache_policy_id            = var.static_site_cache_policy_id
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    response_headers_policy_id = var.static_site_response_headers_policy_id
    target_origin_id           = local.s3_origin_id
    viewer_protocol_policy     = "redirect-to-https"

    dynamic "function_association" {
      for_each = [aws_cloudfront_function.redirect_to_canonical.arn]

      content {
        event_type   = "viewer-request"
        function_arn = function_association.value
      }
    }
  }

  ordered_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cache_policy_id        = var.podcast_feed_cache_policy_id
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    path_pattern           = var.podcast_feed_path_pattern
    target_origin_id       = local.soundon_origin_id
    viewer_protocol_policy = "redirect-to-https"

    dynamic "function_association" {
      for_each = [aws_cloudfront_function.redirect_to_canonical.arn]

      content {
        event_type   = "viewer-request"
        function_arn = function_association.value
      }
    }
  }

  ordered_cache_behavior {
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cache_policy_id          = var.analytics_api_cache_policy_id
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    origin_request_policy_id = var.analytics_api_origin_request_policy_id
    path_pattern             = var.analytics_api_path_pattern
    target_origin_id         = local.analytics_api_origin_id
    viewer_protocol_policy   = "redirect-to-https"

    dynamic "function_association" {
      for_each = [aws_cloudfront_function.redirect_to_canonical.arn]

      content {
        event_type   = "viewer-request"
        function_arn = function_association.value
      }
    }
  }

  ordered_cache_behavior {
    allowed_methods            = ["GET", "HEAD"]
    cache_policy_id            = var.static_site_cache_policy_id
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    path_pattern               = "/engineer/*"
    response_headers_policy_id = var.static_site_response_headers_policy_id
    target_origin_id           = local.engineering_s3_origin_id
    viewer_protocol_policy     = "redirect-to-https"

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.engineer_path_rewrite.arn
    }
  }

  restrictions {
    geo_restriction {
      locations        = []
      restriction_type = "none"
    }
  }

  # Replace the default CloudFront / S3 XML error pages with a branded
  # HTML 404. S3 with Origin Access Control returns 403 AccessDenied for
  # both missing and forbidden keys (it cannot distinguish the two
  # without s3:ListBucket permission), so we intercept both 403 and 404
  # from the origin and show the same "not found" page. The intercepted
  # response is normalised to HTTP 404 so crawlers treat it as a missing
  # URL rather than a forbidden one. The 10-second error caching TTL
  # keeps error responses fresh enough that a recently-fixed bad link
  # does not linger on the CDN.
  #
  # Note: this mapping is distribution-wide, so a genuine 403 or 404
  # from the /analytics-api/* admin routes (unauthorised non-admin
  # user, or an unknown route) is also rewritten to the static 404
  # page. The admin dashboard is the only consumer of those routes in
  # practice, and the dashboard JS degrades gracefully on HTML-shaped
  # responses; seeing "page not found" after trying an unauthorised
  # admin action is acceptable.
  custom_error_response {
    error_caching_min_ttl = 10
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
  }

  custom_error_response {
    error_caching_min_ttl = 10
    error_code            = 404
    response_code         = 404
    response_page_path    = "/404.html"
  }

  viewer_certificate {
    acm_certificate_arn            = aws_acm_certificate_validation.site.certificate_arn
    cloudfront_default_certificate = false
    minimum_protocol_version       = "TLSv1.2_2021"
    ssl_support_method             = "sni-only"
  }

  # Flat-rate CloudFront plans can auto-attach a required web ACL in the console.
  # Keep Terraform from trying to remove that console-managed association.
  lifecycle {
    ignore_changes = [web_acl_id]
  }

  tags = merge(local.tags, {
    Name = local.cloudfront_distribution_name
  })
}

data "aws_iam_policy_document" "site_bucket" {
  statement {
    sid = "AllowCloudFrontRead"

    actions = ["s3:GetObject"]

    principals {
      identifiers = ["cloudfront.amazonaws.com"]
      type        = "Service"
    }

    resources = ["${aws_s3_bucket.site.arn}/*"]

    condition {
      test     = "StringEquals"
      values   = [aws_cloudfront_distribution.site.arn]
      variable = "AWS:SourceArn"
    }
  }
}

resource "aws_s3_bucket_policy" "site" {
  bucket = aws_s3_bucket.site.id
  policy = data.aws_iam_policy_document.site_bucket.json
}
