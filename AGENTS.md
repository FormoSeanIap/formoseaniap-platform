# Repository Instructions

- Treat `/home/ubuntu/non_work/formoseaniap-platform` as the default permission boundary for this repo. Do not read, write, search, or run commands outside this repository unless the user explicitly asks for it.
- After any code change, review the root `README.md`.
- Update `README.md` if the change affects setup, usage, commands, configuration, behavior, dependencies, or project structure.
- If no `README.md` update is needed, say that explicitly in the final response.
- Only update `content/articles/README.md` when the article-writing workflow or article structure changes.

## Terraform Hygiene

- For changes under `infra/**` or `.terraform.lock.hcl`, verify touched Terraform resources, arguments, and blocks against current provider or module documentation before editing.
- Prefer Terraform MCP for current provider or module docs; if the docs are ambiguous, inspect the initialized provider schema locally before changing Terraform syntax.
- After Terraform edits, run `python3 scripts/terraform_validate_strict.py`.
- Treat Terraform deprecation warnings as blocking. Do not leave deprecated settings in the repo even if plain `terraform validate` still exits successfully.

## AWS OIDC Policy Review

- When Terraform-managed AWS resources change, review whether these GitHub Actions OIDC permission policy examples still match the Terraform surface:
  - `docs/examples/aws-oidc-policy-terraform-plan.json`
  - `docs/examples/aws-oidc-policy-terraform-apply-prod.json`
- Default expectation:
  - `aws-oidc-policy-terraform-plan.json` needs read/list/describe access for every Terraform-managed AWS service refreshed during `terraform plan`
  - `aws-oidc-policy-terraform-apply-prod.json` needs create/update/delete/read access for every Terraform-managed AWS service managed during production apply
- Do not update `docs/examples/aws-oidc-policy-deploy-prod.json` unless the production deploy workflow changes what it does after Terraform, such as deploying to different buckets, invalidating different distributions, or calling additional AWS APIs.
- When changing GitHub Actions workflow triggers, environments, or role-assumption contexts, also review the matching OIDC trust policy examples under `docs/examples/`.

## Todo Capture

- Use `docs/inbox.md` for quick idea capture when the user explicitly asks to add a todo.
- Use `docs/backlog.md` for curated and actionable follow-up work.
- Default behavior:
  - If the user gives a rough idea only, add it to `docs/inbox.md`.
  - If the user gives enough detail to make the item actionable, or asks to organize/prioritize it, add or promote it to `docs/backlog.md`.
- Keep backlog entries concise and implementation-oriented: include a short summary, rough scope, and a practical definition of done.
- When completed work clearly satisfies an existing backlog item, update or remove the stale backlog entry instead of leaving it open.
- Do not put future todos in `README.md` unless the user explicitly wants public roadmap-style documentation there.

## Git Commit Rules

- Only create commits when explicitly asked.
- Keep each commit focused on one logical change.
- Do not mix unrelated modified files or hunks into the same commit.
- Before committing, review the staged diff and make sure only the intended changes are included.
- Run the smallest relevant verification for the staged changes before committing; if verification is not possible, say that explicitly.
- Use a concise commit message in `type(scope): summary` format when it fits the change; otherwise use a short imperative summary.
- Update `README.md` before committing when the staged changes affect setup, usage, commands, configuration, behavior, dependencies, or project structure.
- Do not amend existing commits unless explicitly requested.
