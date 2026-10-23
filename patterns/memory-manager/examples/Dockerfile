# Domain-owned container build.
#
# OWNERSHIP: the domain team owns this image, its registry and its scanning.
# The platform team publishes the pattern source; it never builds or operates this image.
#
# Replace <BASE_IMAGE_DIGEST> with a pinned base image before use. A floating tag is not
# a reproducible build.

# ---- build stage ------------------------------------------------------------
FROM python:3.12-slim@sha256:<BASE_IMAGE_DIGEST> AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Dependencies first, so a source change does not invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.5.11 \
 && uv export --frozen --no-dev --format requirements-txt > /tmp/requirements.txt \
 && pip install --no-cache-dir --prefix=/install -r /tmp/requirements.txt

# Vendored pattern source plus the domain's own extensions and configuration.
COPY vendor/pattern/ ./vendor/pattern/
COPY extensions/ ./extensions/
RUN pip install --no-cache-dir --prefix=/install ./vendor/pattern

# ---- runtime stage ----------------------------------------------------------
FROM python:3.12-slim@sha256:<BASE_IMAGE_DIGEST>

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Control C-12: never run as root.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home app

COPY --from=build /install /usr/local
COPY --chown=app:app extensions/ /app/extensions/
COPY --chown=app:app config/ /app/config/

WORKDIR /app
USER 10001:10001

EXPOSE 8080

# No secrets in any layer. Configuration arrives via environment and Secret Manager
# references at runtime; see standards/configuration.md.

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=2).status==200 else 1)"

# The factory form, so a configuration error is reported as one rather than as an import
# traceback from inside uvicorn's loader.
CMD ["python3", "-m", "uvicorn", "src.asgi:create", "--factory", "--host", "0.0.0.0", "--port", "8080"]
