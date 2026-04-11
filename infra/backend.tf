terraform {
  backend "s3" {
    bucket       = "formoseaniap-platform-tfstate-760259504838-ap-northeast-1-an"
    encrypt      = true
    key          = "infra/prod/terraform.tfstate"
    region       = "ap-northeast-1"
    use_lockfile = true
  }
}
