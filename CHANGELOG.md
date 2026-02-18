# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [Semantic Versioning](https://semver.org/).

---

## [1.0.0] - 2026-02-18

First production-ready release. Covers the complete secure software delivery
lifecycle: local development → CI security scanning → container registry →
ECS Fargate deployment → observability.

### Added

#### Application
- Flask REST API with `/health`, `/api/v1/items` (GET + POST), and `/metrics` endpoints
- Prometheus metrics instrumentation (`http_requests_total`, `http_request_duration_seconds`)
- PostgreSQL database integration via `psycopg2` with per-request connection pooling through Flask `g`
- Environment-variable-driven DB configuration (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`)
- `python-dotenv` support for local `.env` files
- Graceful DB error handling — routes return HTTP 503 on connection failure rather than crashing
- Database migration runner (`app/migrations/migrate.py`) with idempotent, ordered SQL file execution
- `schema_migrations` tracking table so re-running migrations is always safe
- Initial schema migration (`app/migrations/001_initial_schema.sql`) with indexed `items` table

#### CI/CD Pipeline
- 7-stage parallel CI pipeline (pre-commit, lint/test, SAST, build/scan, Terraform validate, Checkov, OPA)
- CD pipeline with ECR push → ECS rolling deploy → smoke test, triggered via `workflow_dispatch`
- 80% minimum test coverage threshold enforced via `--cov-fail-under=80`
- SBOM generation in both SPDX-JSON and CycloneDX-JSON formats
- GitHub OIDC → AWS IAM authentication (no long-lived access keys stored in GitHub)

#### Infrastructure (Terraform)
- Modular Terraform layout: `bootstrap/`, `modules/{vpc,ecs,rds,iam}`, `environments/{dev,prod}`
- VPC with public/private subnets, Internet Gateway, NAT gateway, and VPC Flow Logs (30-day retention)
- **Multi-AZ NAT gateway option** (`enable_multi_az_nat`): one NAT per AZ in production for HA,
  single shared NAT in dev for cost efficiency
- ECS Fargate cluster with ALB, CloudWatch Container Insights, and CPU-based auto-scaling (70% target, max 6 tasks)
- RDS PostgreSQL 16 with encryption at rest, automated backups (7-day retention), Secrets Manager password,
  storage auto-scaling (20 → 100 GB), and Performance Insights
- IAM least-privilege roles for ECS task execution and application; GitHub Actions OIDC trust policy
- S3 + DynamoDB Terraform remote state with KMS encryption and versioning
- ECR repository with immutable tags and scan-on-push enabled

#### Kubernetes (EKS-ready)
- Hardened `Deployment` manifest: non-root UID 10000, read-only root filesystem, all capabilities dropped,
  seccomp `RuntimeDefault`, topology spread across AZs, resource requests/limits
- `ClusterIP` Service, ALB Ingress with HTTPS annotation, and `NetworkPolicy` (egress to PostgreSQL + DNS only)

#### Security
- Container image scanning with Trivy (blocks on CRITICAL/HIGH CVEs)
- Python SAST with Bandit; lint-level security rules via Ruff (`S`, `B` rule sets)
- Infrastructure scanning with tfsec (Terraform) and Checkov (Terraform, Docker, Kubernetes)
- OPA/Rego admission control policies (7 deny rules: non-root, resource limits, no privilege escalation,
  trusted registry, read-only filesystem, liveness probe, readiness probe)
- Secret detection via `detect-secrets` pre-commit hook with baseline
- Dockerfile linting via `hadolint`

#### Observability
- Prometheus scrape configuration targeting the app at 10-second intervals
- Grafana dashboard with request rate, error rate gauge, and P95 latency panels
- Alert rules: `HighErrorRate` (5xx > 5% for 5 min), `HighLatency` (p95 > 1s for 5 min), `InstanceDown`

#### Documentation
- Comprehensive `README.md` with Mermaid architecture diagram, tech-stack table, CI/CD workflow,
  security controls reference, and local development quickstart
- `docs/architecture.md` — ASCII diagrams for CI/CD flow, AWS VPC topology, and security layers
- `docs/branch-strategy.md` — branch protection rules, conventional commits, and environment promotion model
- `Production Deployment Prerequisites` section in README covering ACM, ALB HTTPS, DNS, GitHub OIDC,
  and Terraform bootstrap setup
- `Database Migrations` section in README with run instructions, example output, and deployment order
- MIT License (`LICENSE`)
- This `CHANGELOG.md`

### Fixed

- OPA registry policy used the literal string `AWS_ACCOUNT_ID` which never matched real ECR URIs;
  replaced with `regex.match` against the pattern `^\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/`
- `imagePullPolicy: Always` added to Kubernetes Deployment (resolves Checkov CKV_K8S_15)
- Hardened RDS: `deletion_protection`, `copy_tags_to_snapshot`, documented Checkov risk acceptances
- Terraform formatting (`terraform fmt`) applied across all modules
- CodeQL upload action upgraded to `v4`
- Pre-commit import-order issues resolved for Ruff isort compliance
- `detect-secrets` baseline updated to allowlist GitHub OIDC thumbprint

### Security

- All container images built from Python 3.12-slim with a distroless runtime layer
- ECS tasks and RDS instances placed in private subnets; only ALB exposed publicly
- RDS master password managed exclusively by AWS Secrets Manager (no plaintext in state or code)
- ECR image tags set to `IMMUTABLE`; scan-on-push enabled

---

### Known Limitations / Pre-deployment Steps

The following items are template placeholders that **must be configured** before deploying
to a real AWS account. See `README.md → Production Deployment Prerequisites` for step-by-step
instructions.

| Item | Location | Action Required |
|---|---|---|
| ACM certificate ARN | `terraform.tfvars` | Request cert, add `acm_certificate_arn` |
| Domain name | `k8s/ingress.yaml` | Replace `api.example.com` |
| Container image | `k8s/deployment.yaml` | Replace `AWS_ACCOUNT_ID` and tag |
| GitHub secret | GitHub repo settings | Add `AWS_ROLE_ARN` from Terraform output |
| Terraform bootstrap | `terraform/bootstrap/` | Run `terraform apply` once before anything else |

[1.0.0]: https://github.com/Amirhossein-Asadzadeh/secure-devsecops-aws-pipeline/releases/tag/v1.0.0
