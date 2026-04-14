locals {
  site_domain_names = {
    apex      = local.site_apex_domain
    canonical = local.site_canonical_domain
  }
  site_certificate_validation_records = {
    for dvo in aws_acm_certificate.site.domain_validation_options :
    dvo.domain_name => {
      name   = trimsuffix(dvo.resource_record_name, ".")
      record = trimsuffix(dvo.resource_record_value, ".")
      type   = dvo.resource_record_type
    }
  }
  analytics_auth_certificate_validation_records = {
    for dvo in aws_acm_certificate.analytics_auth.domain_validation_options :
    dvo.domain_name => {
      name   = trimsuffix(dvo.resource_record_name, ".")
      record = trimsuffix(dvo.resource_record_value, ".")
      type   = dvo.resource_record_type
    }
  }
  manual_dns_prerequisites = [
    "Before the full custom-domain apply, create the ACM validation CNAME records at the live DNS provider and wait until ACM marks the certificates as issued.",
    "Before Terraform creates ${local.analytics_auth_domain}, Amazon Cognito requires the parent domain ${local.site_apex_domain} to resolve publicly with a real DNS A record. Cloudflare proxying or apex CNAME flattening can still fail this check even when dig returns an address.",
    "If ${local.site_apex_domain} does not already have a DNS-only A record, create a temporary placeholder A record at the live DNS provider, rerun terraform apply until the Cognito custom domain succeeds, then replace that temporary record with the final site cutover record.",
    "If the live DNS provider is Cloudflare, keep the ACM validation and final CNAME records set to DNS only."
  ]
  manual_dns_validation_records = concat(
    [
      for domain_name, record in local.site_certificate_validation_records : {
        fqdn    = record.name
        purpose = "site_certificate_validation"
        type    = record.type
        value   = record.record
      }
    ],
    [
      for domain_name, record in local.analytics_auth_certificate_validation_records : {
        fqdn    = record.name
        purpose = "auth_certificate_validation"
        type    = record.type
        value   = record.record
      }
    ],
  )
  manual_dns_site_cutover_records = [
    {
      fqdn    = local.site_apex_domain
      host    = "@"
      note    = "Use Cloudflare apex CNAME flattening or the equivalent external-DNS alias behavior."
      purpose = "site_apex_cutover"
      type    = "CNAME"
      value   = aws_cloudfront_distribution.site.domain_name
    },
    {
      fqdn    = local.site_canonical_domain
      host    = var.site_canonical_subdomain
      note    = "Canonical public site host."
      purpose = "site_canonical_cutover"
      type    = "CNAME"
      value   = aws_cloudfront_distribution.site.domain_name
    },
  ]
  manual_dns_auth_cutover_record = {
    fqdn    = local.analytics_auth_domain
    host    = var.analytics_auth_subdomain
    note    = "Cognito managed-login custom domain. Value is available after the full custom-domain apply creates the Cognito custom domain."
    purpose = "analytics_auth_cutover"
    type    = "CNAME"
    value   = try(aws_cognito_user_pool_domain.analytics_custom.cloudfront_distribution, null)
  }
}

resource "aws_route53_zone" "site" {
  comment = "Authoritative public DNS zone for ${local.site_apex_domain}."
  name    = local.site_apex_domain

  tags = merge(local.tags, {
    Name = local.site_apex_domain
  })
}

resource "aws_cloudfront_function" "redirect_to_canonical" {
  code    = templatefile("${path.module}/cloudfront/redirect_to_canonical.js.tftpl", { canonical_host = local.site_canonical_domain })
  comment = "Redirect apex and non-canonical hosts to https://${local.site_canonical_domain}."
  name    = "${local.name_prefix}-redirect-to-canonical"
  publish = true
  runtime = "cloudfront-js-2.0"
}

resource "aws_acm_certificate" "site" {
  provider = aws.us_east_1

  domain_name               = local.site_apex_domain
  subject_alternative_names = [local.site_canonical_domain]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-site-domain-cert"
  })
}

resource "aws_acm_certificate" "analytics_auth" {
  provider = aws.us_east_1

  domain_name       = local.analytics_auth_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-analytics-auth-domain-cert"
  })
}

resource "aws_route53_record" "site_certificate_validation" {
  for_each = local.site_certificate_validation_records

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.site.zone_id
}

resource "aws_route53_record" "analytics_auth_certificate_validation" {
  for_each = local.analytics_auth_certificate_validation_records

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.site.zone_id
}

resource "aws_acm_certificate_validation" "site" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for record in aws_route53_record.site_certificate_validation : record.fqdn]
}

resource "aws_acm_certificate_validation" "analytics_auth" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.analytics_auth.arn
  validation_record_fqdns = [for record in aws_route53_record.analytics_auth_certificate_validation : record.fqdn]
}

resource "aws_route53_record" "site_a_alias" {
  for_each = local.site_domain_names

  name    = each.value
  type    = "A"
  zone_id = aws_route53_zone.site.zone_id

  alias {
    evaluate_target_health = false
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
  }
}

resource "aws_route53_record" "site_aaaa_alias" {
  for_each = local.site_domain_names

  name    = each.value
  type    = "AAAA"
  zone_id = aws_route53_zone.site.zone_id

  alias {
    evaluate_target_health = false
    name                   = aws_cloudfront_distribution.site.domain_name
    zone_id                = aws_cloudfront_distribution.site.hosted_zone_id
  }
}

resource "aws_cognito_user_pool_domain" "analytics_custom" {
  certificate_arn       = aws_acm_certificate_validation.analytics_auth.certificate_arn
  domain                = local.analytics_auth_domain
  managed_login_version = 2
  user_pool_id          = aws_cognito_user_pool.analytics.id

  depends_on = [aws_route53_record.site_a_alias]
}

resource "aws_route53_record" "analytics_auth_alias" {
  name    = local.analytics_auth_domain
  type    = "A"
  zone_id = aws_route53_zone.site.zone_id

  alias {
    evaluate_target_health = false
    name                   = aws_cognito_user_pool_domain.analytics_custom.cloudfront_distribution
    zone_id                = aws_cognito_user_pool_domain.analytics_custom.cloudfront_distribution_zone_id
  }
}

resource "aws_cognito_managed_login_branding" "analytics" {
  client_id    = aws_cognito_user_pool_client.analytics.id
  settings     = file("${path.module}/cognito_branding/managed_login_settings.json")
  user_pool_id = aws_cognito_user_pool.analytics.id

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/favicon.svg")
    category   = "FAVICON_SVG"
    color_mode = "DYNAMIC"
    extension  = "SVG"
  }

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/form_logo.svg")
    category   = "FORM_LOGO"
    color_mode = "DYNAMIC"
    extension  = "SVG"
  }

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/page_header_logo.svg")
    category   = "PAGE_HEADER_LOGO"
    color_mode = "DYNAMIC"
    extension  = "SVG"
  }

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/page_background_light.svg")
    category   = "PAGE_BACKGROUND"
    color_mode = "LIGHT"
    extension  = "SVG"
  }

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/page_background_dark.svg")
    category   = "PAGE_BACKGROUND"
    color_mode = "DARK"
    extension  = "SVG"
  }

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/form_background_light.svg")
    category   = "FORM_BACKGROUND"
    color_mode = "LIGHT"
    extension  = "SVG"
  }

  asset {
    bytes      = filebase64("${path.module}/cognito_branding/form_background_dark.svg")
    category   = "FORM_BACKGROUND"
    color_mode = "DARK"
    extension  = "SVG"
  }

  depends_on = [aws_cognito_user_pool_domain.analytics_custom]
}
