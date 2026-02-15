# Branch Protection & Merge Strategy

## Branch Model

```
main (protected)
 ├── feature/*      ← new features
 ├── fix/*          ← bug fixes
 ├── hotfix/*       ← critical production fixes
 └── chore/*        ← maintenance, CI, docs
```

All changes reach `main` exclusively through pull requests. Direct pushes are blocked.

## Branch Protection Rules (`main`)

| Rule | Setting |
|------|---------|
| Require pull request before merging | Enabled |
| Required approvals | 1 minimum |
| Dismiss stale reviews on new commits | Enabled |
| Require status checks to pass | Enabled |
| Required status checks | `Pre-commit Checks`, `Test & Lint`, `SAST Scan`, `Terraform Validate`, `OPA Policy Check`, `Build & Scan Image` |
| Require branches to be up to date | Enabled |
| Require signed commits | Recommended |
| Require linear history | Enabled (squash merge) |
| Include administrators | Enabled |
| Allow force pushes | Disabled |
| Allow deletions | Disabled |

## Merge Strategy

**Squash and merge** is the enforced merge method:

- Each PR becomes a single commit on `main`
- Keeps the history clean and bisectable
- PR title becomes the commit message (follows Conventional Commits)

### Conventional Commits

All PR titles must follow this format:

```
<type>: <short description>
```

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `chore` | CI, deps, maintenance |
| `refactor` | Code restructure (no behavior change) |
| `test` | Adding or updating tests |
| `security` | Security patches or hardening |

Examples:
```
feat: add user authentication endpoint
fix: resolve race condition in health check
security: upgrade base image to patch CVE-2025-1234
chore: bump Terraform provider to v5.40
```

## CI Status Gates

Every pull request must pass all of these before merge is allowed:

```
PR opened
 │
 ├── Pre-commit Checks ─── trailing whitespace, YAML, JSON, secrets, black, ruff
 ├── Test & Lint ────────── ruff linter + pytest with coverage
 ├── SAST Scan ──────────── Bandit static analysis
 ├── Terraform Validate ─── fmt, init, validate, tfsec
 ├── OPA Policy Check ───── K8s manifests against Rego policies
 └── Build & Scan Image ─── Docker build + Trivy vulnerability scan
      │
      ▼
 All green → Review → Squash merge → CD triggers
```

## Environment Promotion

```
feature branch → PR → main → auto-deploy to staging → manual approval → production
```

| Environment | Trigger | Approval |
|-------------|---------|----------|
| Staging | Automatic on merge to `main` | None |
| Production | Manual `workflow_dispatch` | Required (team lead) |

## Hotfix Process

For critical production issues:

1. Create `hotfix/<description>` from `main`
2. Apply minimal fix
3. Open PR — all status checks still required
4. Fast-track review (single approver, no waiting period)
5. Squash merge to `main`
6. Deploy via CD pipeline

No exceptions to CI checks, even for hotfixes.

## Setup Instructions

Apply these rules via GitHub CLI:

```bash
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Pre-commit Checks","Test & Lint","SAST Scan","Terraform Validate","OPA Policy Check","Build & Scan Image"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```
