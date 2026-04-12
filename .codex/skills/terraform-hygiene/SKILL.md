---
name: terraform-hygiene
description: Validate Terraform changes against current docs and block deprecated settings in this repo. Use when tasks touch infra/*.tf, .terraform.lock.hcl, Terraform CI validation, or Terraform workflow/docs changes.
---

# Terraform Hygiene

## Overview

Use this skill when work touches Terraform in this repository. The goal is to keep provider syntax current and make deprecations fail locally and in CI instead of slipping through as warnings.

## Workflow

1. Identify the touched Terraform surface first:
   - provider resources and data sources under `infra/*.tf`
   - Terraform workflows under `.github/workflows/**`
   - lockfile changes in `infra/.terraform.lock.hcl`

2. Fetch current docs before editing:
   - For provider resources or data sources, use Terraform MCP `search_providers` then `get_provider_details`.
   - For Terraform Registry modules, use Terraform MCP `search_modules` then `get_module_details`.
   - Prefer the exact provider version already pinned by the repo when the docs allow version targeting.

3. If the docs are ambiguous:
   - Run backendless `terraform init` with a dedicated `TF_DATA_DIR`.
   - Inspect `terraform providers schema -json` instead of guessing block or attribute names.

4. After edits:
   - Run `python3 scripts/terraform_validate_strict.py`.
   - Do not stop at plain `terraform validate` success if deprecated arguments or blocks are still reported.

5. If a deprecation cannot be resolved cleanly:
   - Stop and surface the exact warning and the doc or schema conflict instead of guessing.

## Repo Notes

- The strict local command is `python3 scripts/terraform_validate_strict.py`.
- Shared CI uses the same command through `.github/workflows/_terraform-validate-shared.yml`.
- Deprecation warnings are blocking in this repo even when Terraform itself exits with success.
