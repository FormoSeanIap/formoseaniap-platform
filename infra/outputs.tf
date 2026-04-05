output "podcast_proxy_function_url" {
  description = "Public Function URL for the podcast RSS proxy."
  value       = aws_lambda_function_url.podcast_proxy.function_url
}
