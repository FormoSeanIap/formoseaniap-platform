locals {
  analytics_api_origin_id    = "${local.name_prefix}-analytics-api"
  analytics_api_name         = "${local.name_prefix}-analytics-api"
  analytics_admin_group_name = var.analytics_admin_group_name
  analytics_admin_path       = "/admin/analytics.html"
  analytics_backend_source_files = {
    for path in sort(fileset("${path.module}/../analytics_backend", "**/*.py")) :
    path => path
  }
  analytics_cognito_prefix_domain_name = (
    var.analytics_cognito_domain_prefix != ""
    ? var.analytics_cognito_domain_prefix
    : "${local.name_prefix}-${data.aws_caller_identity.current.account_id}"
  )
  analytics_cognito_domain_url = (
    local.custom_auth_domain_live
    ? "https://${aws_cognito_user_pool_domain.analytics_custom.domain}"
    : "https://${aws_cognito_user_pool_domain.analytics.domain}.auth.${var.aws_region}.amazoncognito.com"
  )
  analytics_cognito_issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.analytics.id}"
  analytics_public_site_base_url = trimsuffix(
    var.public_site_base_url != ""
    ? var.public_site_base_url
    : (
      local.custom_site_domain_live
      ? "https://${local.site_canonical_domain}"
      : "https://${aws_cloudfront_distribution.site.domain_name}"
    ),
    "/",
  )
  analytics_runtime_config = {
    admin = {
      enabled       = true
      site_base_url = local.analytics_public_site_base_url
    }
    api_base_path = "/analytics-api"
    cognito = {
      client_id     = aws_cognito_user_pool_client.analytics.id
      domain_url    = local.analytics_cognito_domain_url
      redirect_path = local.analytics_admin_path
      scopes        = ["openid", "email", "profile"]
      user_pool_id  = aws_cognito_user_pool.analytics.id
    }
  }
}

data "archive_file" "analytics_backend" {
  type        = "zip"
  output_path = "${path.module}/build/analytics_backend.zip"

  dynamic "source" {
    for_each = local.analytics_backend_source_files

    content {
      content  = file("${path.module}/../analytics_backend/${source.value}")
      filename = "analytics_backend/${source.value}"
    }
  }
}

resource "random_password" "analytics_visitor_hmac_secret" {
  length  = 48
  special = false
}

resource "aws_dynamodb_table" "analytics_daily_counters" {
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  name         = "${local.name_prefix}-analytics-daily-counters"
  range_key    = "sk"

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  global_secondary_index {
    name            = "gsi1"
    projection_type = "ALL"

    key_schema {
      attribute_name = "gsi1pk"
      key_type       = "HASH"
    }

    key_schema {
      attribute_name = "gsi1sk"
      key_type       = "RANGE"
    }
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-analytics-daily-counters"
  })
}

resource "aws_dynamodb_table" "analytics_daily_uniques" {
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  name         = "${local.name_prefix}-analytics-daily-uniques"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "expire_at"
    enabled        = true
  }

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-analytics-daily-uniques"
  })
}

resource "aws_iam_role" "analytics_lambda" {
  name = "${local.name_prefix}-analytics-lambda"

  assume_role_policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Action = "sts:AssumeRole"
          Effect = "Allow"
          Principal = {
            Service = "lambda.amazonaws.com"
          }
        },
      ]
    }
  )

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "analytics_lambda_logs" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.analytics_lambda.name
}

resource "aws_iam_role_policy" "analytics_lambda_dynamodb" {
  name = "${local.name_prefix}-analytics-dynamodb"
  role = aws_iam_role.analytics_lambda.id

  policy = jsonencode(
    {
      Version = "2012-10-17"
      Statement = [
        {
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:Query",
            "dynamodb:TransactWriteItems",
            "dynamodb:UpdateItem",
          ]
          Effect = "Allow"
          Resource = [
            aws_dynamodb_table.analytics_daily_counters.arn,
            "${aws_dynamodb_table.analytics_daily_counters.arn}/index/gsi1",
            aws_dynamodb_table.analytics_daily_uniques.arn,
          ]
        },
      ]
    }
  )
}

resource "aws_lambda_function" "analytics_collector" {
  filename         = data.archive_file.analytics_backend.output_path
  function_name    = "${local.name_prefix}-analytics-collector"
  handler          = "analytics_backend.collector_lambda.handler"
  role             = aws_iam_role.analytics_lambda.arn
  runtime          = "python3.13"
  source_code_hash = data.archive_file.analytics_backend.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      ANALYTICS_ADMIN_GROUP_NAME    = local.analytics_admin_group_name
      ANALYTICS_COUNTERS_TABLE_NAME = aws_dynamodb_table.analytics_daily_counters.name
      ANALYTICS_UNIQUES_TABLE_NAME  = aws_dynamodb_table.analytics_daily_uniques.name
      ANALYTICS_UNIQUES_TTL_DAYS    = tostring(var.analytics_uniques_ttl_days)
      ANALYTICS_VISITOR_HMAC_SECRET = random_password.analytics_visitor_hmac_secret.result
    }
  }

  tags = local.tags
}

resource "aws_lambda_function" "analytics_admin" {
  filename         = data.archive_file.analytics_backend.output_path
  function_name    = "${local.name_prefix}-analytics-admin"
  handler          = "analytics_backend.admin_lambda.handler"
  role             = aws_iam_role.analytics_lambda.arn
  runtime          = "python3.13"
  source_code_hash = data.archive_file.analytics_backend.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      ANALYTICS_ADMIN_GROUP_NAME    = local.analytics_admin_group_name
      ANALYTICS_COUNTERS_TABLE_NAME = aws_dynamodb_table.analytics_daily_counters.name
      ANALYTICS_UNIQUES_TABLE_NAME  = aws_dynamodb_table.analytics_daily_uniques.name
      ANALYTICS_UNIQUES_TTL_DAYS    = tostring(var.analytics_uniques_ttl_days)
      ANALYTICS_VISITOR_HMAC_SECRET = random_password.analytics_visitor_hmac_secret.result
    }
  }

  tags = local.tags
}

resource "aws_cognito_user_pool" "analytics" {
  name           = "${local.name_prefix}-analytics"
  user_pool_tier = "ESSENTIALS"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  auto_verified_attributes = ["email"]

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "email"
    required                 = true

    string_attribute_constraints {
      max_length = 2048
      min_length = 0
    }
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "name"
    required                 = true

    string_attribute_constraints {
      max_length = 2048
      min_length = 1
    }
  }

  password_policy {
    minimum_length    = 14
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  username_configuration {
    case_sensitive = false
  }

  tags = local.tags
}

resource "aws_cognito_user_pool_domain" "analytics" {
  domain       = local.analytics_cognito_prefix_domain_name
  user_pool_id = aws_cognito_user_pool.analytics.id
}

resource "aws_cognito_user_pool_client" "analytics" {
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = ["${local.analytics_public_site_base_url}${local.analytics_admin_path}"]
  generate_secret                      = false
  logout_urls                          = ["${local.analytics_public_site_base_url}${local.analytics_admin_path}"]
  name                                 = "${local.name_prefix}-analytics-spa"
  prevent_user_existence_errors        = "ENABLED"
  read_attributes                      = ["email", "email_verified", "name"]
  supported_identity_providers         = ["COGNITO"]
  user_pool_id                         = aws_cognito_user_pool.analytics.id
}

resource "aws_cognito_user_group" "analytics_admin" {
  name         = local.analytics_admin_group_name
  user_pool_id = aws_cognito_user_pool.analytics.id
}

resource "aws_apigatewayv2_api" "analytics" {
  name          = local.analytics_api_name
  protocol_type = "HTTP"

  tags = local.tags
}

resource "aws_apigatewayv2_authorizer" "analytics_jwt" {
  api_id           = aws_apigatewayv2_api.analytics.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "${local.name_prefix}-analytics-jwt"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.analytics.id]
    issuer   = local.analytics_cognito_issuer
  }
}

resource "aws_apigatewayv2_integration" "analytics_collector" {
  api_id                 = aws_apigatewayv2_api.analytics.id
  integration_method     = "POST"
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.analytics_collector.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "analytics_admin" {
  api_id                 = aws_apigatewayv2_api.analytics.id
  integration_method     = "POST"
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.analytics_admin.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "analytics_collect" {
  api_id    = aws_apigatewayv2_api.analytics.id
  route_key = "POST /analytics-api/collect"
  target    = "integrations/${aws_apigatewayv2_integration.analytics_collector.id}"
}

resource "aws_apigatewayv2_route" "analytics_admin_session" {
  api_id             = aws_apigatewayv2_api.analytics.id
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.analytics_jwt.id
  route_key          = "GET /analytics-api/admin/session"
  target             = "integrations/${aws_apigatewayv2_integration.analytics_admin.id}"
}

resource "aws_apigatewayv2_route" "analytics_admin_overview" {
  api_id             = aws_apigatewayv2_api.analytics.id
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.analytics_jwt.id
  route_key          = "GET /analytics-api/admin/overview"
  target             = "integrations/${aws_apigatewayv2_integration.analytics_admin.id}"
}

resource "aws_apigatewayv2_route" "analytics_admin_articles" {
  api_id             = aws_apigatewayv2_api.analytics.id
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.analytics_jwt.id
  route_key          = "GET /analytics-api/admin/articles"
  target             = "integrations/${aws_apigatewayv2_integration.analytics_admin.id}"
}

resource "aws_apigatewayv2_route" "analytics_admin_article_detail" {
  api_id             = aws_apigatewayv2_api.analytics.id
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.analytics_jwt.id
  route_key          = "GET /analytics-api/admin/articles/{article_id}"
  target             = "integrations/${aws_apigatewayv2_integration.analytics_admin.id}"
}

resource "aws_apigatewayv2_stage" "analytics" {
  api_id      = aws_apigatewayv2_api.analytics.id
  auto_deploy = true
  name        = "$default"

  default_route_settings {
    throttling_burst_limit = var.analytics_default_throttling_burst_limit
    throttling_rate_limit  = var.analytics_default_throttling_rate_limit
  }

  route_settings {
    route_key              = aws_apigatewayv2_route.analytics_collect.route_key
    throttling_burst_limit = var.analytics_collect_throttling_burst_limit
    throttling_rate_limit  = var.analytics_collect_throttling_rate_limit
  }

  tags = local.tags
}

resource "aws_lambda_permission" "analytics_collector_api" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analytics_collector.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.analytics.execution_arn}/*/*"
  statement_id  = "AllowInvokeFromApiGatewayCollector"
}

resource "aws_lambda_permission" "analytics_admin_api" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analytics_admin.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.analytics.execution_arn}/*/*"
  statement_id  = "AllowInvokeFromApiGatewayAdmin"
}
