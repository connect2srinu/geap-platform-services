# Domain CI/CD pipeline template — GitHub Actions

Copy `domain-pipeline.yml` into the domain repository's `.github/workflows/`.

## What it does

| Job | Purpose |
|---|---|
| `quality` | Lint, types, the domain's own tests |
| `pattern-conformance` | **Runs the pattern's conformance suite** and verifies the pinned version has not drifted |
| `security` | Dependency, secret and Terraform policy scanning |
| `terraform` | Format and validate |
| `build` | Build the domain-owned image, scan it, push on `main` |
| `deploy` | Terraform apply and smoke test, behind a GitHub Environment |

## Required repository variables

| Variable | Example |
|---|---|
| `WIF_PROVIDER` | `projects/<n>/locations/global/workloadIdentityPools/<pool>/providers/<provider>` |
| `DEPLOY_SERVICE_ACCOUNT` | `<domain>-deployer@<project>.iam.gserviceaccount.com` |
| `REGION` | `us-central1` |
| `IMAGE_REPO` | `us-central1-docker.pkg.dev/<project>/<repo>/<service>` |
| `SERVICE_URL` | the deployed endpoint, for the smoke test |

**Workload Identity Federation only.** Never a downloaded service account key.

## What the pipeline does not do

It does not prove to the platform team that the domain is conformant — the platform cannot see this
run. If the domain removes the conformance job, nothing outside the domain notices. The only controls
that survive that are the platform-owned memory bank IAM binding and audit sink.

## Manual configuration

The `production` environment and its **required reviewers** are configured in GitHub by a repository
administrator. The `environment:` key in this file names the gate; it does not create or enforce it.
