locals {
  engineering_site_domain      = "${var.engineering_subdomain}.${local.site_apex_domain}"
  engineering_site_bucket_name = "${local.name_prefix}-eng-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  engineering_s3_origin_id     = "${local.name_prefix}-engineering-site-s3"
}

resource "aws_s3_bucket" "engineering_site" {
  bucket        = local.engineering_site_bucket_name
  force_destroy = var.site_bucket_force_destroy

  tags = merge(local.tags, {
    Name = local.engineering_site_bucket_name
  })
}

resource "aws_s3_bucket_public_access_block" "engineering_site" {
  bucket = aws_s3_bucket.engineering_site.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "engineering_site" {
  bucket = aws_s3_bucket.engineering_site.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "engineering_site" {
  bucket = aws_s3_bucket.engineering_site.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "engineering_site" {
  bucket = aws_s3_bucket.engineering_site.id

  versioning_configuration {
    status = var.site_bucket_versioning_enabled ? "Enabled" : "Suspended"
  }
}

resource "aws_cloudfront_origin_access_control" "engineering_site" {
  name                              = "${local.name_prefix}-engineering-site-oac"
  description                       = "CloudFront access to the private ${local.engineering_site_bucket_name} S3 origin."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_function" "engineer_path_rewrite" {
  code    = file("${path.module}/cloudfront/engineer_path_rewrite.js")
  comment = "Strip /engineer prefix from viewer requests before forwarding to the engineering S3 origin."
  name    = "${local.name_prefix}-engineer-path-rewrite"
  publish = true
  runtime = "cloudfront-js-2.0"
}

data "aws_iam_policy_document" "engineering_site_bucket" {
  statement {
    sid = "AllowCloudFrontRead"

    actions = ["s3:GetObject"]

    principals {
      identifiers = ["cloudfront.amazonaws.com"]
      type        = "Service"
    }

    resources = ["${aws_s3_bucket.engineering_site.arn}/*"]

    condition {
      test     = "StringEquals"
      values   = [aws_cloudfront_distribution.site.arn]
      variable = "AWS:SourceArn"
    }
  }
}

resource "aws_s3_bucket_policy" "engineering_site" {
  bucket = aws_s3_bucket.engineering_site.id
  policy = data.aws_iam_policy_document.engineering_site_bucket.json
}
