# Personal Portfolio Platform

A long-term personal portfolio platform to present identity, work, and ideas.

This project is designed to start simple (static site first), then evolve into a cloud-native deployment with infrastructure-as-code and CI/CD.

## Vision

Build a portfolio that balances:
- Technical professionalism (cloud/infrastructure engineering)
- Personal expression (writing, creative work, visual identity)
- Long-term maintainability (clear structure, reusable systems)

## Profile Focus

This platform introduces me as:
- Platform engineer
- Writer
- Creator

## Current State (March 2026)

Implemented updates in the static site:
- Identity and branding synchronized across pages (Home, Projects, Articles, Artworks, About)
  - Name: Sêng-Gān Ia̍p
  - Role line: Platform Engineer / Writer / Creator
- About page content pass completed
  - Personal narrative refined to reflect engineering + philosophy + creative direction
  - Snapshot section enriched with core stack and certifications
  - Contact section connected with real links (email, GitHub, LinkedIn, Medium)
  - Milestones rewritten with real career timeline and IT Ironman achievement
- Home page layout tuned
  - Hero card returned to square presentation
  - Viewport-aware sizing adjusted to keep header, hero, and footer visible together on typical desktop screens
  - Typography adjusted to improve name rendering with diacritics
- Shared UI consistency improvements
  - Footer identity synchronized across pages
  - Link affordance improved in milestone reference links

## Core Goals

- Introduce who I am and what I value
- Showcase projects, articles, and creative work
- Build a scalable and maintainable portfolio platform
- Demonstrate engineering skills (AWS, Terraform, CI/CD)

## Style Direction

Reference inspiration:
- https://p5aholic.me/
- https://shoya-kajita.com/
- https://edwinle.com/

Design direction for this project:
- Japanese-style minimalism
- Clean and intentional layout
- Strong typography and whitespace
- Subtle interactions and animation
- Calm visual tone with clear content hierarchy

## Product Scope (v1)

Pages:
- Home
- Projects
- Articles
- About

Optional (v1.1):
- Creative/Gallery page

Initial content target:
- 3 project entries
- 2 article entries
- 1 concise personal story/about section

## Build Strategy (Agreed)

We will build in this order:

1. Define content and design in this README
2. Build static frontend first (HTML/CSS/JS)
3. Review locally in browser and iterate quickly
4. Freeze v1 UI/content structure
5. Add Terraform infrastructure
6. Add GitHub Actions CI/CD deployment

Why this order:
- Reduces infrastructure rework while UI/content are still evolving
- Speeds up visual feedback and decision making
- Keeps development simple early, extensible later

## Planned Repository Structure

/
- infra/      Terraform code for AWS resources
- site/       Static frontend files (HTML/CSS/JS/assets)
- .github/    GitHub Actions workflows
- README.md

## Frontend Plan (Phase 1)

site/
- index.html
- projects.html
- articles.html
- about.html
- assets/
  - css/
    - variables.css
    - base.css
    - layout.css
    - components.css
  - js/
    - main.js
  - img/

Frontend principles:
- Semantic HTML
- Reusable CSS variables/tokens
- Lightweight JS for small interactions only
- Mobile-first and responsive design
- Performance-conscious assets

## Infrastructure Plan (Phase 2)

Target architecture:
- AWS S3 for static file hosting
- AWS CloudFront for CDN + HTTPS
- Private S3 bucket behind CloudFront OAC
- Custom domain (Route 53 or external DNS)

Terraform approach:
- Modular and reusable
- Environment-aware variables
- Clear outputs and minimal complexity for v1

## CI/CD Plan (Phase 3)

GitHub Actions workflow goals:
- Trigger on push to main
- Build static site
- Sync files to S3
- Invalidate CloudFront cache

Security and operations notes:
- Use GitHub Secrets for AWS credentials/role
- Prefer OIDC where possible (future improvement)
- Keep deployment logs simple and traceable

## Content Model (Draft)

Project fields:
- title
- summary
- role
- stack
- architecture
- outcome
- links
- date
- featured

Article fields:
- title
- excerpt
- tags
- read_time
- published_date
- slug

Creative work fields:
- title
- medium
- year
- caption
- images

## Non-Goals (for now)

- Complex backend features
- CMS integration before content structure is validated
- Advanced animation systems that increase maintenance burden

## Future Enhancements

- Blog system (Markdown or CMS)
- Artwork gallery
- Analytics and monitoring
- Performance and caching optimization
- API/Lambda features if needed

## Immediate Next Steps

1. Review and polish mobile layout behavior for the home hero and footer fit
2. Continue replacing placeholder project/article entries with real content
3. Add an explicit Experience page (optional) if milestone detail grows
4. Prepare Terraform and deployment workflows after content pass stabilizes

## Development Principles

- Keep it simple first, then iterate
- Build for long-term clarity and extensibility
- Prefer maintainability over premature complexity
- Let the project reflect both technical rigor and personal style
