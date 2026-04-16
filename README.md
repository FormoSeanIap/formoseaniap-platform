# Formoseaniap Platform

Static-first personal portfolio platform for writing, projects, podcasts, and a small private analytics surface.

Live site: [https://www.formoseaniap.com/](https://www.formoseaniap.com/)

## Website Preview

| Light mode | Dark mode |
| --- | --- |
| ![Homepage light mode](docs/assets/readme/homepage-light.png) | ![Homepage dark mode](docs/assets/readme/homepage-dark.png) |

## At a Glance

| Area | What it does |
| --- | --- |
| Site delivery | Static pages are served from a private S3 bucket through CloudFront. |
| Edge protection | AWS WAF sits at the CloudFront layer for rate limiting and edge filtering. |
| Writing pipeline | Markdown in `content/articles/**` is built into JSON and RSS artifacts under `site/data/`. |
| Podcast page | The browser reads podcast feeds through the same CloudFront domain so third-party CORS restrictions do not break the page. |
| Backend | A small analytics/admin backend uses CloudFront + API Gateway + Lambda + DynamoDB. |
| Auth | The private analytics page uses Cognito managed login with Authorization Code + PKCE. |
| DNS | Cloudflare is still the live DNS provider today; Route 53 is the planned future authoritative DNS home. |
| Deployments | GitHub Actions validates, plans, previews, and promotes production through AWS OIDC role assumption. |

## Architecture

### Web
![AWS architecture diagram for the platform](docs/assets/readme/architecture.png)

Sources:
- [`docs/assets/readme/architecture.svg`](docs/assets/readme/architecture.svg)
- [`docs/assets/readme/architecture.png`](docs/assets/readme/architecture.png)
- [`docs/assets/readme/architecture.drawio`](docs/assets/readme/architecture.drawio)

Current DNS note: the diagram shows the target DNS design with Route 53, but the live domain is still using Cloudflare today. Route 53 is the planned destination once the DNS migration is finished.

### Monitoring and alerts
![AWS architecture diagram for monitoring and alerts](docs/assets/readme/monitoring.png)

Sources:
- [`docs/assets/readme/monitoring.svg`](docs/assets/readme/monitoring.svg)
- [`docs/assets/readme/monitoring.png`](docs/assets/readme/monitoring.png)
- [`docs/assets/readme/monitoring.drawio`](docs/assets/readme/monitoring.drawio)

### Admin login flow

```mermaid
sequenceDiagram
  autonumber
  actor User as Visitor browser
  participant AdminPage as Static admin page<br/>www.formoseaniap.com/admin/analytics.html
  participant CF as CloudFront
  participant Cognito as Cognito managed login<br/>auth.formoseaniap.com
  participant API as API Gateway<br/>/analytics-api/admin/*
  participant Lambda as Admin Lambda
  participant DDB as DynamoDB

  User->>CF: GET /admin/analytics.html
  CF-->>User: Static HTML, JS, and analytics config
  User->>AdminPage: Load admin-analytics.js
  AdminPage->>AdminPage: Check stored tokens and config

  alt No valid token in browser
    AdminPage->>AdminPage: Generate PKCE verifier and state
    AdminPage->>Cognito: Redirect to /oauth2/authorize
    Cognito-->>User: Hosted sign-in page
    User->>Cognito: Submit credentials
    Cognito-->>AdminPage: Redirect back with code and state
    AdminPage->>AdminPage: Verify returned state
    AdminPage->>Cognito: POST /oauth2/token with code_verifier
    Cognito-->>AdminPage: Access token and ID token
    AdminPage->>AdminPage: Store tokens and clean URL
  end

  AdminPage->>CF: Call /analytics-api/admin/session with Bearer token
  CF->>API: Forward same-origin admin API request
  API->>API: Validate JWT issuer and audience
  API->>Lambda: Invoke protected admin route
  Lambda->>Lambda: Check analytics-admin Cognito group
  Lambda->>DDB: Read analytics data
  DDB-->>Lambda: Return overview and article metrics
  Lambda-->>API: JSON response
  API-->>CF: Authorized response
  CF-->>AdminPage: Admin analytics payload
  AdminPage-->>User: Render private dashboard
```

- [`docs/assets/readme/admin-login-flow.mmd`](docs/assets/readme/admin-login-flow.mmd)

### Why the podcast page uses CloudFront as a proxy

The podcast feeds are owned by a third party, so the browser cannot rely on upstream CORS headers being present or correct. Instead of trying to change the remote feed provider, the site routes `/podcasts/*` through the same CloudFront distribution. From the browser's point of view the request stays same-origin, which avoids the podcast-page CORS failure.

## Infrastructure Notes

| Component | Current design |
| --- | --- |
| Static frontend | CloudFront reads from a private S3 origin through Origin Access Control. |
| Edge security | AWS WAF sits in front of CloudFront for edge-side filtering and rate limiting. |
| DNS | Cloudflare remains the current authoritative DNS provider. Route 53 is provisioned/planned as the future DNS authority after migration. |
| Podcast feed path | CloudFront routes `/podcasts/*` to the upstream RSS host. |
| Analytics API | CloudFront routes `/analytics-api/*` to a regional API Gateway HTTP API. |
| Analytics storage | Lambda writes counters and uniqueness state to DynamoDB. |
| Monitoring | CloudWatch dashboard and SNS-backed Lambda alarms are provisioned by Terraform. |
| Custom domains | `www.formoseaniap.com` is the canonical host, with apex redirect support. |
| Cost control | The stack uses AWS-managed CloudFront cache policies and keeps flat-rate CloudFront plan handling as a deliberate console-managed step. |

## Cost Estimate

This estimate is a rough order-of-magnitude view of the production stack cost as of April 16, 2026. It is meant for planning and discussion, not as a billing guarantee. Exact AWS charges still depend on region, monthly traffic shape, account-level free-tier eligibility, and whether the Route 53 hosted zone is attached to the CloudFront flat-rate plan.

### Fixed baseline

| Item | Assumption | Estimated cost |
| --- | --- | --- |
| Domain registration | Third-party registrar cost for `formoseaniap.com` | about `$15/year` or `$1.25/month` |
| CloudFront flat-rate plan | Free tier with one distribution | `$0/month` |
| Route 53 hosted zone | `$0` when attached to the CloudFront plan, otherwise standard Route 53 pricing applies | `$0` or about `$0.50/month` plus DNS queries |
| S3 site storage | Local site output is well below the Free plan's included `5 GB` of S3 Standard credits | effectively `$0/month` at current size |
| Cognito admin login | Admin-only access pattern, expected to stay far below the standard MAU threshold for meaningful cost | effectively `$0/month` at current scale |
| CloudWatch dashboard and alarms | One dashboard and two alarms, which fit comfortably inside small-scale usage | effectively `$0/month` at current scale |
| SNS alarm email delivery | Only sends when alarms trigger | near `$0/month` unless alarms become noisy |

### Variable backend cost

The traffic-sensitive part of the stack is the backend behind CloudFront:

- `API Gateway HTTP API` handles analytics and admin requests.
- `Lambda` runs the collector and admin handlers.
- `DynamoDB` stores counters and uniqueness state.

The current analytics collector writes more than one record per tracked view. Each collect request attempts two uniqueness writes and performs two counter updates, so DynamoDB contributes more to variable cost than it would in a simpler single-write design.

Using AWS reference pricing as a working estimate:

- `API Gateway HTTP API`: about `$1.00 / 1M requests`
- `Lambda`: about `$0.30-$0.41 / 1M requests` assuming `128 MB` memory and `50-100 ms` average duration
- `DynamoDB on-demand`: about `$2.50 / 1M analytics collect requests`

That gives a rough backend variable cost of about `~$3.8-$3.9 per 1M analytics collect requests`.

### Traffic scenarios

These scenarios assume the Route 53 zone is attached to the CloudFront plan, the CloudFront plan stays on the Free tier, and each analytics page view results in one collect request.

| Scenario | Analytics collect requests / month | Estimated backend usage | Estimated monthly total |
| --- | ---: | ---: | ---: |
| Small | `10,000` | about `$0.04` | about `$1.29/month` |
| Medium | `100,000` | about `$0.38-$0.39` | about `$1.63-$1.64/month` |
| Large | `1,000,000` | about `$3.80-$3.91` | about `$5.05-$5.16/month` |

If the Route 53 hosted zone is not attached to the CloudFront plan, add about `+$0.50/month` plus Route 53 DNS query charges.

### CloudFront plan note

CloudFront flat-rate plans no longer behave like the older pay-as-you-go CDN model:

- The Free plan includes `1M requests/month` and `100 GB/month` data transfer as its published allowance.
- AWS states there are no overage charges when you exceed the allowance.
- If usage stays materially above the allowance for multiple months, AWS may recommend upgrading the plan or may adjust delivery performance instead of billing request overages.

In practice, that means the predictable cost risk at this scale is mostly the regional backend usage, not CloudFront edge overages. If sustained traffic growth pushes the site past the Free plan's intended baseline, the next obvious planning step is to compare whether the `Pro` CloudFront plan at about `$15/month` is justified for performance headroom.

## CI/CD Design

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| [`push-others.yml`](.github/workflows/push-others.yml) | `develop` and work branches | Validate the site, rebuild generated artifacts, and run Terraform validation plus optional plan on infra changes. |
| [`pr-validate.yml`](.github/workflows/pr-validate.yml) | Pull requests into `develop` or `main` | Re-run validation, attach a preview artifact, and optionally deploy a hosted preview after Terraform checks pass. |
| [`push-main.yml`](.github/workflows/push-main.yml) | Push to `main` | Re-run validation, wait at the protected `prod` environment, run production Terraform plan/apply, write runtime config, deploy the site, and invalidate CloudFront. |

```mermaid
flowchart LR
  Dev[Work branch or develop] --> PushOthers[push-others.yml]
  PR[Pull request] --> PRValidate[pr-validate.yml]
  Main[main] --> PushMain[push-main.yml]

  PushOthers --> Validate1[Validate + optional Terraform plan]
  PRValidate --> Validate2[Validate + preview artifact or preview deploy]
  PushMain --> Gate[Protected prod environment]
  Gate --> TFApply[Terraform plan and apply]
  TFApply --> Deploy[Sync site to S3]
  Deploy --> Invalidate[CloudFront invalidation]
```

Source: [`docs/assets/readme/cicd-pipeline.mmd`](docs/assets/readme/cicd-pipeline.mmd)

## GitHub Actions OIDC

The pipelines do not store long-lived AWS keys in GitHub. Each job requests a GitHub OIDC token, exchanges it with AWS STS, and receives short-lived credentials for a narrowly scoped IAM role.

```mermaid
flowchart LR
  GHA[GitHub Actions job] --> Token[GitHub OIDC token]
  Token --> STS[AWS STS AssumeRoleWithWebIdentity]
  STS --> PlanRole[Terraform plan role]
  STS --> ApplyRole[Terraform apply role]
  STS --> DeployRole[Production deploy role]
  STS --> PreviewRole[Preview role]

  PlanRole --> ReadOnly[Read-only Terraform plan access]
  ApplyRole --> TFWrite[Production Terraform changes]
  DeployRole --> Ship[Site sync + CloudFront invalidation]
  PreviewRole --> Preview[Preview S3 and optional preview CDN]
```

Source: [`docs/assets/readme/oidc-roles.mmd`](docs/assets/readme/oidc-roles.mmd)

| Role | Used by | Scope |
| --- | --- | --- |
| Terraform plan role | PR validation, branch validation, pre-promotion plan on `main` | Read-only access needed for live-state Terraform plans. |
| Terraform apply role | Protected production stage in `push-main.yml` | Applies Terraform against the production state. |
| Production deploy role | Protected production stage in `push-main.yml` | Syncs the built site to S3 and invalidates CloudFront. |
| Preview role | Optional preview stage in `pr-validate.yml` | Deploys PR previews when preview infrastructure is configured. |

## Repository Map

| Path | Purpose |
| --- | --- |
| `site/` | Static pages, assets, and generated runtime data consumed by the browser. |
| `content/` | Markdown articles and site metadata. |
| `scripts/` | Build, validation, migration, and local utility scripts. |
| `analytics_backend/` | Lambda handler code for analytics collection and admin reads. |
| `infra/` | Terraform for AWS hosting, analytics backend, auth, and domain resources. |
| `.github/` | Shared GitHub Actions and workflow definitions. |
| `docs/` | Operational notes, examples, and backlog/inbox planning files. |

## Local Development

Run the site preview and the podcast proxy in separate terminals when working locally. The site preview serves `site/` as the web root, and the podcast proxy keeps the podcast page working locally without depending on production routing.

```bash
python3 scripts/site_preview.py
python3 scripts/podcast_proxy.py
```

## Design Direction

This platform is intended to evolve toward a calmer and more opinionated visual identity, with design choices that reflect both engineering rigor and personal taste rather than a generic portfolio template.

### Style direction

Reference inspiration:

- [p5aholic.me](https://p5aholic.me/)
- [shoya-kajita.com](https://shoya-kajita.com/)
- [edwinle.com](https://edwinle.com/)

Design goals:

- Japanese-style minimalism
- Strong typography and whitespace
- Subtle animation and a calm visual tone
- Clear content hierarchy

### Development principles

- Keep it simple first, then iterate.
- Prefer maintainability over premature complexity.
- Build for long-term clarity and extensibility.
- Let the platform reflect both engineering rigor and personal style.

## Further Reading

- [infra/README.md](infra/README.md)
- [docs/aws-oidc-github-actions.md](docs/aws-oidc-github-actions.md)
- [docs/github-branching.md](docs/github-branching.md)
