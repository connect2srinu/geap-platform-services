# Coding standards

## Language and toolchain

| | |
|---|---|
| Language | Python 3.12 |
| Framework | FastAPI + Pydantic v2 |
| Lint and format | `ruff` (lint + format) |
| Types | `mypy --strict` on `src/`; tests may relax |
| Tests | `pytest` |
| Dependencies | `uv`, with `uv.lock` committed |

Chosen for consistency with the team's existing services and the ADK ecosystem
(`docs/decisions/ADR-0002-reference-implementation-stack.md`).

## Structure

Follow the layering in `standards/architecture.md`. One module, one responsibility. A module that
needs "and" to describe it should be two.

## Typing

Public functions are fully annotated. `Any` requires a comment explaining why. Prefer Pydantic models
over dicts for anything crossing a boundary — a `dict[str, Any]` at a module edge is a missing model.

## Errors

- Raise domain-meaningful exceptions in `policy/` and `providers/`; map to HTTP in `api/` only.
- Every error returned to a caller carries a **stable machine-readable code** from the pattern's
  error catalogue, and a correlation ID.
- Never swallow an exception. Never `except Exception: pass`.
- Never put a provider's raw error text in a caller-facing response — it leaks internals. Log it with
  the correlation ID and return a catalogue code.

## Configuration

No literal environment lookups scattered through the code. Configuration is loaded once, validated
against the schema, and injected. Precedence: defaults → file → environment → secret reference. See
`standards/configuration.md`.

## Dependencies

- Pin exact versions; commit the lockfile.
- A new dependency needs a reason in the design or the task, and goes through dependency scanning.
- No undeclared dependencies — if it is imported, it is in `pyproject.toml`.
- Prefer the standard library. Scripts under `scripts/` may use **only** the standard library plus
  `PyYAML` and `jsonschema` (`scripts/requirements.txt`), so that CI and developers can run every
  validation without a project environment. They must fail with an actionable message, not a
  traceback, when those two are absent.

## Comments

Explain *why*, not *what*. Match the density of surrounding code. A comment restating the line below
it is noise; a comment explaining a non-obvious constraint — a provider quirk, a quota interaction,
an ordering requirement — is valuable and should be there.

## What not to do

- No business-domain rules in `src/`. See `.claude/rules/platform-vs-domain.md`.
- No real enterprise identifiers anywhere in code, config, templates or examples.
- No opportunistic refactoring outside the task.
- No new abstraction with exactly one implementation and no second one in sight.
