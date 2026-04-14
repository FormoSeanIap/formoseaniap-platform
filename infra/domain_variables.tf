variable "site_root_domain" {
  default     = "formoseaniap.com"
  description = "Root DNS domain for the production site and hosted zone."
  type        = string
}

variable "site_canonical_subdomain" {
  default     = "www"
  description = "Subdomain used as the canonical public site host."
  type        = string
}

variable "analytics_auth_subdomain" {
  default     = "auth"
  description = "Subdomain used for the Cognito managed-login custom domain."
  type        = string
}
