output "engineering_site_bucket_name" {
  description = "S3 bucket name for the engineering section."
  value       = aws_s3_bucket.engineering_site.bucket
}
