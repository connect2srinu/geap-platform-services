# ADR-0002: Python 3.12 + FastAPI for reference implementations

- **Status:** Accepted
- **Date:** 2026-10-20
- **Decision owners:** Platform team
- **Scope:** The language and framework for every pattern reference implementation in this repository
- **Related:** `design/000-platform-foundation/intent.md`, `standards/coding.md`

## Context

Patterns publish **implementation code** that domain teams adopt and customize, so the stack choice
is not an internal one — it is imposed on every adopting domain. It needs to match what those teams
already build with.

**VERIFIED** by inspecting sibling projects on 2026-10-20:

- `geap-memory/apps/control-plane-api` — FastAPI, Pydantic, Python 3.12, `ruff`, `pytest`, `uv.lock`,
  Alembic.
- `geap-plarform-poc-agent/caveman-agent` and `cloudrun-eval/*` — Python ADK agents with
  `pyproject.toml` and `uv.lock`.

The consuming agents are built on Google's ADK, which is Python-first. The local toolchain has Python
3.12.3 and `uv`.

## Decision

Reference implementations are **Python 3.12** with **FastAPI** and **Pydantic v2**. Lint and format
with `ruff`; type-check `src/` with `mypy --strict`; test with `pytest`; manage dependencies with
`uv` and a committed `uv.lock`.

Repository validation scripts are held to a stricter rule: standard library plus `PyYAML` and
`jsonschema` only, so that CI and developers can run every validation without a project environment.

## Alternatives considered

| Option | Pros | Cons | Why not chosen |
|---|---|---|---|
| TypeScript / Node | Strong typing; good OpenAPI tooling | Does not match the existing services or the ADK ecosystem; imposes a second toolchain on every adopting domain | Rejected |
| Go | Fast, small single-binary containers, good concurrency for the worker | No existing Go in these teams; a reference implementation nobody can read is not reusable | Rejected — the worker's concurrency needs are modest and bounded by provider quota anyway |
| Python, framework-agnostic | Maximum domain freedom | Every domain re-solves validation, OpenAPI generation and error mapping; the contract stops being uniform | Rejected — uniformity of the tool API is the point |

## Consequences

**Easier:** domains can read, modify and extend the reference implementation immediately; Pydantic
gives schema-validated configuration and OpenAPI generation from one source; it matches the ADK
agents that consume the service.

**Harder:** Python's cold-start and memory profile on Cloud Run is worse than Go's, which matters for
a min-instance-zero read path — mitigated by `min_instances >= 1` in the reference deployment.
`mypy --strict` on `src/` is real ongoing effort. A domain preferring another language gets no
reference implementation and must implement the contract itself; the conformance suite still applies,
since it is black-box.

## Compatibility implications

`spec.runtime.language` in `pattern.yaml` is an enum that already permits `typescript`, `go` and
`java`, so a future pattern in another language does not require a schema change. This ADR constrains
the default, not the schema.

## Status history

| Date | Status | Note |
|---|---|---|
| 2026-10-20 | Accepted | |
