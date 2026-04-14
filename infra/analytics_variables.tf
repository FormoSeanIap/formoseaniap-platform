variable "analytics_admin_group_name" {
  default     = "analytics-admin"
  description = "Cognito group name required for access to the private analytics admin API."
  type        = string
}

variable "analytics_alarm_email" {
  description = "Email address subscribed to analytics backend Lambda alarm notifications."
  type        = string
}

variable "analytics_api_cache_policy_id" {
  default     = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  description = "CloudFront cache policy ID for analytics API responses. Defaults to AWS-managed CachingDisabled."
  type        = string
}

variable "analytics_api_origin_request_policy_id" {
  default     = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  description = "CloudFront origin request policy ID for the analytics API. Defaults to AWS-managed AllViewerExceptHostHeader for API Gateway compatibility."
  type        = string
}

variable "analytics_api_path_pattern" {
  default     = "/analytics-api/*"
  description = "CloudFront behavior path pattern for same-origin analytics API requests."
  type        = string
}

variable "analytics_cognito_domain_prefix" {
  default     = ""
  description = "Optional explicit fallback Cognito prefix domain. Leave blank to derive one from the project, environment, and AWS account ID."
  type        = string
}

variable "analytics_collect_throttling_burst_limit" {
  default     = 25
  description = "API Gateway burst throttling limit for the public analytics collector route."
  type        = number
}

variable "analytics_collect_throttling_rate_limit" {
  default     = 10
  description = "API Gateway steady-state rate limit for the public analytics collector route."
  type        = number
}

variable "analytics_default_throttling_burst_limit" {
  default     = 15
  description = "API Gateway default burst throttling limit for analytics admin routes."
  type        = number
}

variable "analytics_default_throttling_rate_limit" {
  default     = 8
  description = "API Gateway default steady-state rate limit for analytics admin routes."
  type        = number
}

variable "analytics_uniques_ttl_days" {
  default     = 7
  description = "How many days to retain per-visitor uniqueness records used for daily dedupe."
  type        = number
}

variable "public_site_base_url" {
  default     = ""
  description = "Public base URL for the production site, used for Cognito callback and logout URLs. Leave blank to use the canonical custom domain after the custom-domain infrastructure is live, otherwise the CloudFront distribution domain."
  type        = string
}
