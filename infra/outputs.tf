output "cloudfront_distribution_domain_name" {
  description = "CloudFront distribution domain name for the production site."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID for cache invalidations."
  value       = aws_cloudfront_distribution.site.id
}

output "cloudfront_distribution_arn" {
  description = "CloudFront distribution ARN."
  value       = aws_cloudfront_distribution.site.arn
}

output "podcast_feed_origin_domain" {
  description = "Third-party podcast RSS origin domain routed through CloudFront."
  value       = var.podcast_feed_origin_domain
}

output "podcast_feed_path_pattern" {
  description = "CloudFront path pattern for same-origin podcast RSS feed reads."
  value       = var.podcast_feed_path_pattern
}

output "site_bucket_arn" {
  description = "Private S3 bucket ARN for the production site origin."
  value       = aws_s3_bucket.site.arn
}

output "site_bucket_name" {
  description = "Private S3 bucket name for production site deploys."
  value       = aws_s3_bucket.site.bucket
}
