# Build instructions — domain-owned

> The pattern is `proposed` and has no implementation yet. These instructions describe the intended
> build and are not yet executable.

## Ownership

The **domain team** builds, scans, publishes and operates this image. The platform team publishes
source only.

## Steps

1. Vendor the pattern source at the pinned version from `pattern.lock.yaml`.
2. Pin the base image by digest in the Dockerfile — replace `<BASE_IMAGE_DIGEST>`.
3. Place your extension implementations in `extensions/`.
4. Build:
   ```bash
   docker build -t <region>-docker.pkg.dev/<project>/<repo>/memory-manager:<tag> .
   ```
5. Scan before pushing. A CRITICAL or HIGH finding blocks the push in the reference pipeline.
6. Push to **your** registry and deploy by digest, never by tag.

## Required properties

Non-root user (`C-12`) · pinned base digest · no secrets in any layer · minimal runtime stage.
