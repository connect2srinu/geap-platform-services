"""The ASGI entry point a container runs.

Exposed as a factory rather than a module-level ``app`` so that a configuration error raises
:class:`~.api.main.ConfigurationError` with a message naming the field, instead of an import-time
traceback from inside uvicorn's loader.

    uvicorn src.asgi:create --factory --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from .api.main import create_app
from .bootstrap import build_deployment, load_config

#: Where the domain's configuration is mounted. The Dockerfile copies `config/` to /app/config.
DEFAULT_CONFIG_PATH = "/app/config/domain.yaml"


def create() -> FastAPI:
    """Build the application from `CONFIG_PATH` and the environment."""
    config = load_config(os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH))
    environment = os.environ.get("ENVIRONMENT", "production")
    return create_app(
        build_deployment(config, environment=environment), environment=environment
    )
