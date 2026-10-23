#!/usr/bin/env python3
"""Create, or tear down, one Agent Engine with Memory Bank for the Tier 1 probe.

Spike tooling for design/001-memory-manager (tasks.md T-24), written 2026-10-22. Not pattern code.

`client.memory_banks.create` in google-cloud-aiplatform 2.3.0 POSTs a `reasoningEngines` resource
whose `context_spec.memory_bank_config` is the Memory Bank: one Agent Engine with Memory Bank. The
printed name is what `probe_memory_bank.py --bank` (or `--ttl-bank`, `--cmek-bank`) takes.

Requirements
    Python 3.10+ and google-cloud-aiplatform[agent_engines]==2.3.0 (provides `agentplatform`).
    Application Default Credentials allowed to create, read and delete Agent Engines in the project.
    With --kms-key, the Agent Platform service agent needs encrypt and decrypt on the key.

Usage
    create_bank.py --project P --location L                      # plain bank (probe --bank)
    create_bank.py --project P --location L --ttl-seconds 300    # generate TTLs (probe --ttl-bank)
    create_bank.py --project P --location L --kms-key KEY        # CMEK bank (probe --cmek-bank)
    create_bank.py --project P --location L --delete NAME        # teardown, including all memories

Delete refuses any engine whose display name does not start with "geap-probe-", the prefix this
script gives every engine it creates, so a mistyped name cannot remove a real bank.

Exit status: 0 done, 1 the provider refused or the operation failed, 2 the script could not start.
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from typing import Any

PINNED_SDK = "2.3.0"
PREFIX = "geap-probe-"


def describe(exc: BaseException) -> str:
    return f"{type(exc).__name__} {getattr(exc, 'code', '')}: {str(exc)[:300]}"


def create(client: Any, args: argparse.Namespace) -> int:
    semantic: dict[str, Any] = {}
    if args.generation_model:
        semantic["generation_config"] = {"model": args.generation_model}
    if args.embedding_model:
        semantic["similarity_search_config"] = {"embedding_model": args.embedding_model}
    if args.ttl_seconds:
        seconds = f"{args.ttl_seconds}s"
        semantic["ttl_config"] = {
            "granular_ttl_config": {
                "create_ttl": seconds,
                "generate_created_ttl": seconds,
                "generate_updated_ttl": seconds,
            }
        }
    config: dict[str, Any] = {"display_name": args.display_name}
    if args.kms_key:
        config["encryption_spec"] = {"kms_key_name": args.kms_key}

    print(
        f"creating '{args.display_name}' in {args.location} (waits for the operation) ..."
    )
    try:
        bank = client.memory_banks.create(
            managed_semantic_memory_config=semantic or None, config=config
        )
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        print(f"FAILED: {describe(exc)}")
        return 1
    print(bank.name)
    return 0


def delete(client: Any, name: str, timeout: float) -> int:
    try:
        bank = client.memory_banks.get(name=name)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        print(f"FAILED to read {name}: {describe(exc)}")
        return 1
    display = getattr(bank, "display_name", None) or ""
    if not display.startswith(PREFIX):
        print(f"REFUSED: display name {display!r} does not start with {PREFIX!r}")
        return 1

    print(f"deleting {name} ('{display}') with force=True: its memories go with it ...")
    try:
        client.memory_banks.delete(name=name, force=True)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        print(f"FAILED: {describe(exc)}")
        return 1

    # delete() returns the operation without waiting, so confirm the resource is gone.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            client.memory_banks.get(name=name)
        except Exception as exc:  # noqa: BLE001 - only a 404 means deleted
            if getattr(exc, "code", None) == 404:
                print(f"deleted: {name}")
                return 0
            print(f"FAILED while confirming: {describe(exc)}")
            return 1
        time.sleep(5)
    print(f"NOT CONFIRMED: {name} still readable after {timeout:.0f} s")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--display-name", default=f"{PREFIX}{uuid.uuid4().hex[:8]}")
    parser.add_argument(
        "--generation-model", help="full model resource name; default: service's"
    )
    parser.add_argument(
        "--embedding-model", help="full model resource name; default: service's"
    )
    parser.add_argument(
        "--ttl-seconds", type=int, help="generate TTLs, for the probe's L7"
    )
    parser.add_argument(
        "--kms-key", help="Cloud KMS key resource name, for the probe's L11"
    )
    parser.add_argument(
        "--delete", metavar="NAME", help="delete this engine instead of creating"
    )
    parser.add_argument(
        "--timeout", type=float, default=300.0, help="seconds to confirm a delete"
    )
    args = parser.parse_args(argv)
    if not args.display_name.startswith(PREFIX):
        parser.error(
            f"--display-name must start with {PREFIX!r}, or --delete will refuse it"
        )

    try:
        import importlib.metadata  # noqa: PLC0415

        sdk = importlib.metadata.version("google-cloud-aiplatform")
        import agentplatform  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 - reported as could-not-start
        print(f"cannot start: {describe(exc)}")
        return 2
    if sdk != PINNED_SDK:
        print(f"WARNING: pinned SDK is {PINNED_SDK}, found {sdk}")
    try:
        client = agentplatform.Client(project=args.project, location=args.location)
    except Exception as exc:  # noqa: BLE001 - reported as could-not-start
        print(f"cannot start: {describe(exc)}")
        return 2

    if args.delete:
        return delete(client, args.delete, args.timeout)
    return create(client, args)


if __name__ == "__main__":
    sys.exit(main())
