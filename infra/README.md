# Terraform Home

This directory is reserved for infrastructure code for this repository.

Current convention:

- Keep repository-managed Terraform under `infra/`.
- Start with a single root stack in this directory.
- Use pull requests into `main` for `terraform fmt -check`, `terraform validate`, and optional `terraform plan`.
- Use the manual `Terraform Apply Prod` workflow for production applies.
- Do not auto-apply Terraform on every push to `main`.

If you later split infrastructure into multiple stacks or modules, update the Terraform workflows to target each stack explicitly instead of scattering `.tf` files across the repository.
