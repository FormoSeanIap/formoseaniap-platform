output "analytics_admin_group_name" {
  description = "Cognito group name required for analytics admin access."
  value       = local.analytics_admin_group_name
}

output "analytics_api_path_pattern" {
  description = "CloudFront path pattern for same-origin analytics API requests."
  value       = var.analytics_api_path_pattern
}

output "analytics_cognito_client_id" {
  description = "Cognito app client ID used by the static analytics admin page."
  value       = aws_cognito_user_pool_client.analytics.id
}

output "analytics_cognito_domain_url" {
  description = "Resolved Cognito domain URL for analytics admin authentication."
  value       = local.analytics_cognito_domain_url
}

output "analytics_cognito_user_pool_id" {
  description = "Cognito user pool ID for the analytics admin app."
  value       = aws_cognito_user_pool.analytics.id
}

output "analytics_public_site_base_url" {
  description = "Resolved public base URL used by Cognito callback and logout URLs."
  value       = local.analytics_public_site_base_url
}

output "analytics_runtime_config" {
  description = "Production runtime config for the static analytics admin page."
  value       = local.analytics_runtime_config
}
