terraform {
  backend "s3" {
    bucket       = ""
    encrypt      = true
    key          = "infra/prod/terraform.tfstate"
    region       = "ap-northeast-1"
    use_lockfile = true
  }
}
