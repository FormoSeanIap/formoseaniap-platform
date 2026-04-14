output "analytics_auth_domain_url" {
  description = "Resolved managed-login domain URL for the analytics admin app."
  value       = local.custom_auth_domain_live ? "https://${local.analytics_auth_domain}" : local.analytics_cognito_domain_url
}

output "route53_zone_id" {
  description = "Route 53 hosted zone ID for the production site domain."
  value       = aws_route53_zone.site.zone_id
}

output "route53_zone_name_servers" {
  description = "Route 53 name servers for a future registrar or DNS-authority transfer."
  value       = aws_route53_zone.site.name_servers
}

output "site_apex_domain" {
  description = "Configured apex domain for the production site."
  value       = local.site_apex_domain
}

output "site_canonical_domain" {
  description = "Configured canonical domain for the production site."
  value       = local.site_canonical_domain
}

output "site_public_base_url" {
  description = "Resolved public site URL for the production site."
  value       = local.custom_site_domain_live ? "https://${local.site_canonical_domain}" : "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "manual_dns_prerequisites" {
  description = "Manual DNS prerequisites to complete at the live DNS provider before the full custom-domain apply."
  value       = local.manual_dns_prerequisites
}

output "manual_dns_auth_cutover_record" {
  description = "Manual auth-domain cutover record to create at the live DNS provider after the full custom-domain apply creates the Cognito custom domain."
  value       = local.manual_dns_auth_cutover_record
}

output "manual_dns_site_cutover_records" {
  description = "Manual site cutover records to create at the live DNS provider after the full custom-domain apply succeeds. For Cloudflare, use DNS-only CNAMEs and rely on apex flattening for the apex host."
  value       = local.manual_dns_site_cutover_records
}

output "manual_dns_validation_records" {
  description = "Manual ACM validation CNAME records to create at the live DNS provider before the full custom-domain apply."
  value       = local.manual_dns_validation_records
}
