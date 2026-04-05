variable "podcast_proxy_cors_allow_origins" {
  default     = ["*"]
  description = "Origins allowed to read the podcast proxy."
  type        = list(string)
}

variable "podcast_proxy_function_name" {
  default     = "formoseaniap-podcast-proxy"
  description = "Lambda function name for the podcast proxy."
  type        = string
}

variable "podcast_proxy_log_retention_days" {
  default     = 14
  description = "CloudWatch log retention for the podcast proxy."
  type        = number
}
