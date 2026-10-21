# Container build template — domain-owned

## Ownership

The **domain team** owns this build: the image, the registry it is pushed to, the scanning, and the
lifecycle. The platform team publishes pattern source and never builds a domain's image.

## Before first use

1. Pin the base image to a digest. Replace `<BASE_IMAGE_DIGEST>` in the `Dockerfile`.
   ```bash
   docker pull python:3.12-slim
   docker inspect --format='{{index .RepoDigests 0}}' python:3.12-slim
   ```
2. Vendor the pattern source into `vendor/pattern/` at the pinned version from `pattern.lock.yaml`.
3. Place the domain's extension implementations in `extensions/`.

## Build and scan

```bash
docker build -t <region>-docker.pkg.dev/<project>/<repo>/<service>:<tag> .
```

```bash
docker scout cves <region>-docker.pkg.dev/<project>/<repo>/<service>:<tag>
```

Scan before pushing. A failing scan blocks the push in the reference CI pipeline.

## Required properties — asserted in CI

- Non-root user (control `C-12`)
- Pinned base image digest
- No secrets in any layer
- Minimal final image — no build toolchain in the runtime stage
