# Architecture Overview

## System Architecture

### CI/CD Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Developer Workstation                        │
│                                                                     │
│   git push / pull request                                           │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions CI                            │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐  │
│  │ Pre-commit  │  │  Test & Lint │  │ SAST Scan  │  │ Build &  │  │
│  │   Checks   │  │  (pytest 80%)│  │  (Bandit)  │  │  Trivy   │  │
│  └─────────────┘  └──────────────┘  └────────────┘  └──────────┘  │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │  Terraform  │  │   Checkov    │  │       OPA / Rego           │ │
│  │  Validate   │  │ Policy Scan  │  │   K8s Manifest Check       │ │
│  │  + tfsec    │  │              │  │                            │ │
│  └─────────────┘  └──────────────┘  └────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │  on merge to main (workflow_dispatch)
                             ▼
                   ┌──────────────────┐
                   │   Amazon ECR     │
                   │  (image registry)│
                   │  immutable tags  │
                   │  scan-on-push    │
                   └────────┬─────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       AWS Cloud (us-east-1)                         │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    VPC (10.0.0.0/16)                          │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │               Public Subnets (us-east-1a/1b)            │  │  │
│  │  │                                                         │  │  │
│  │  │   ┌──────────────────┐       ┌──────────────────┐      │  │  │
│  │  │   │  Internet Gateway│       │   NAT Gateway    │      │  │  │
│  │  │   └────────┬─────────┘       └────────┬─────────┘      │  │  │
│  │  │            │                          │                 │  │  │
│  │  │   ┌────────▼─────────────────────┐   │                 │  │  │
│  │  │   │   Application Load Balancer  │   │                 │  │  │
│  │  │   │   HTTP :80  →  HTTPS :443    │   │                 │  │  │
│  │  │   └────────────────┬─────────────┘   │                 │  │  │
│  │  └────────────────────┼─────────────────┼─────────────────┘  │  │
│  │                       │                 │                     │  │
│  │  ┌────────────────────┼─────────────────┼─────────────────┐  │  │
│  │  │          Private Subnets (us-east-1a/1b)               │  │  │
│  │  │                   │                 │                   │  │  │
│  │  │          ┌────────▼──────────┐      │ (outbound only)   │  │  │
│  │  │          │   ECS Fargate     │◄─────┘                   │  │  │
│  │  │          │   (3 tasks)       │                           │  │  │
│  │  │          │   port 8080       │                           │  │  │
│  │  │          │   Flask + Gunicorn│                           │  │  │
│  │  │          └────────┬──────────┘                           │  │  │
│  │  │                   │ port 5432                            │  │  │
│  │  │          ┌────────▼──────────┐                           │  │  │
│  │  │          │   RDS PostgreSQL  │                           │  │  │
│  │  │          │   (private only)  │                           │  │  │
│  │  │          │   encrypted, MZ   │                           │  │  │
│  │  │          └───────────────────┘                           │  │  │
│  │  └───────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  CloudWatch  │  │  Secrets Mgr │  │     IAM (OIDC)           │  │
│  │  Logs/Metrics│  │  RDS password│  │  GitHub Actions → AWS    │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                   ┌──────────────────┐
                   │    Internet      │
                   │  (end users)     │
                   └──────────────────┘
```

---

## AWS Services Used

| Service | Purpose |
|---|---|
| **ECR** | Container image registry (immutable tags, scan-on-push) |
| **ECS Fargate** | Serverless container compute (no EC2 to manage) |
| **ALB** | Application Load Balancer (HTTP→HTTPS redirect, health checks) |
| **RDS PostgreSQL** | Managed database (encrypted at rest, multi-AZ in prod) |
| **VPC** | Network isolation (public/private subnets, flow logs) |
| **NAT Gateway** | Outbound internet for private subnets |
| **Secrets Manager** | RDS master password (no plaintext credentials) |
| **CloudWatch** | Container logs, ECS metrics, VPC flow logs |
| **IAM** | Least-privilege roles; OIDC trust for GitHub Actions |
| **S3** | Terraform remote state storage (versioned, KMS-encrypted) |
| **DynamoDB** | Terraform state lock table |

---

## Security Layers

```
┌────────────────────────────────────────────────────────────────┐
│                     Security Controls                          │
│                                                                │
│  SHIFT-LEFT (pre-commit)                                       │
│  ├── detect-secrets    → blocks committed secrets              │
│  ├── hadolint          → Dockerfile best practices             │
│  └── yamllint          → YAML syntax and style                 │
│                                                                │
│  CI PIPELINE                                                   │
│  ├── Bandit            → Python SAST (security anti-patterns)  │
│  ├── Ruff              → Python lint incl. security rules      │
│  ├── Trivy             → Container image CVE scan (CRITICAL/HIGH│
│  │                        blocks the build)                    │
│  ├── tfsec             → Terraform misconfigurations           │
│  ├── Checkov           → Policy-as-code (IaC, Docker, K8s)    │
│  └── OPA / Rego        → K8s manifest admission rules          │
│                                                                │
│  RUNTIME (AWS)                                                 │
│  ├── Non-root container (UID 10000, read-only filesystem)      │
│  ├── ECR immutable tags + scan-on-push                         │
│  ├── ALB enforces HTTPS (HTTP 301 redirect)                    │
│  ├── ECS tasks in private subnets only                         │
│  ├── RDS in private subnets (no public access)                 │
│  ├── VPC flow logs (all traffic, 30-day retention)             │
│  ├── Secrets Manager (no plaintext credentials)                │
│  └── IAM least-privilege + GitHub OIDC (no static keys)       │
│                                                                │
│  KUBERNETES (optional EKS deployment)                          │
│  ├── Pod security: runAsNonRoot, readOnlyRootFilesystem        │
│  ├── Drop all Linux capabilities                               │
│  ├── OPA admission control (7 deny policies)                   │
│  └── NetworkPolicy: egress to PostgreSQL + DNS only            │
└────────────────────────────────────────────────────────────────┘
```

---

## Environment Topology

| Config | Dev | Prod |
|---|---|---|
| VPC CIDR | 10.0.0.0/16 | 10.1.0.0/16 |
| Availability Zones | 2 (1a, 1b) | 3 (1a, 1b, 1c) |
| ECS Tasks | 1 | 3 |
| ECS CPU / Memory | 256 / 512 MiB | 512 / 1024 MiB |
| DB Instance | db.t3.micro | db.t3.small |
| DB Multi-AZ | No | Yes |
| Auto-scaling max | 6 tasks | 6 tasks |
| Auto-scaling trigger | CPU 70% | CPU 70% |
