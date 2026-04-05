terraform {
  required_version = ">= 1.5.0"

  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.5"
    }

    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {}

data "archive_file" "podcast_proxy" {
  type        = "zip"
  output_path = "${path.module}/build/podcast-proxy.zip"

  source {
    content  = file("${path.module}/../scripts/podcast_proxy.py")
    filename = "podcast_proxy.py"
  }

  source {
    content  = file("${path.module}/../site/data/podcasts.shows.json")
    filename = "podcasts.shows.json"
  }
}

data "aws_iam_policy_document" "podcast_proxy_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      identifiers = ["lambda.amazonaws.com"]
      type        = "Service"
    }
  }
}

resource "aws_iam_role" "podcast_proxy" {
  assume_role_policy = data.aws_iam_policy_document.podcast_proxy_assume_role.json
  name               = var.podcast_proxy_function_name
}

resource "aws_iam_role_policy_attachment" "podcast_proxy_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.podcast_proxy.name
}

resource "aws_cloudwatch_log_group" "podcast_proxy" {
  name              = "/aws/lambda/${var.podcast_proxy_function_name}"
  retention_in_days = var.podcast_proxy_log_retention_days
}

resource "aws_lambda_function" "podcast_proxy" {
  filename         = data.archive_file.podcast_proxy.output_path
  function_name    = var.podcast_proxy_function_name
  handler          = "podcast_proxy.lambda_handler"
  memory_size      = 128
  role             = aws_iam_role.podcast_proxy.arn
  runtime          = "python3.11"
  source_code_hash = data.archive_file.podcast_proxy.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      PODCAST_SHOWS_CONFIG = "podcasts.shows.json"
    }
  }

  depends_on = [aws_cloudwatch_log_group.podcast_proxy]
}

resource "aws_lambda_function_url" "podcast_proxy" {
  authorization_type = "NONE"
  function_name      = aws_lambda_function.podcast_proxy.function_name

  cors {
    allow_headers = ["Content-Type"]
    allow_methods = ["GET", "OPTIONS"]
    allow_origins = var.podcast_proxy_cors_allow_origins
    max_age       = 86400
  }
}
