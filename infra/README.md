# Terraform Home

This directory is reserved for infrastructure code for this repository.

Current convention:

- Keep repository-managed Terraform under `infra/`.
- Start with a single root stack in this directory.
- Use pull requests into `main` for `terraform fmt -check`, `terraform validate`, and optional `terraform plan`.
- Use the manual `Terraform Apply Prod` workflow for production applies.
- Do not auto-apply Terraform on every push to `main`.
- The current stack provisions the podcast RSS proxy as an AWS Lambda Function URL so the static site can read SoundOn feeds without browser CORS failures.

Current proxy flow:

- Terraform packages `scripts/podcast_proxy.py` together with `site/data/podcasts.shows.json`.
- The Lambda function exposes a public GET endpoint that accepts `show_id=<configured id>`.
- The static site should copy the Terraform output `podcast_proxy_function_url` into `site/data/podcasts.shows.json` as `proxy_url` before deploying the site.
- For local preview, run `python3 scripts/podcast_proxy.py` and the frontend will automatically use `http://127.0.0.1:8787/podcast-feed` on localhost when `proxy_url` is blank.

If you later split infrastructure into multiple stacks or modules, update the Terraform workflows to target each stack explicitly instead of scattering `.tf` files across the repository.
