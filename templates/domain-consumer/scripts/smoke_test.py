#!/usr/bin/env python3
"""Post-deployment smoke test for a domain's Memory Manager.

Proves the deployment actually works end to end, against the real managed service -- which unit
tests and a fake provider cannot do.

    python3 scripts/smoke_test.py --base-url https://<service-url> --agent-id <your-caller-id>

Identity comes from --token, else $ID_TOKEN, else `gcloud auth print-identity-token`.
Standard library only, so it runs in CI without a project environment.

The topic and field default to the ones in the shipped template configuration. Pass yours.

Every check prints passed or failed, and the run exits non-zero if any failed. Nothing is
reported as passing that did not run.

Note on what a failure means here: a fact the domain's policy REFUSES is a successful request
with `outcome: noop`, not an error. This script checks for the outcome, not the status code.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

GREEN, RED, RESET = "\033[32m", "\033[31m", "\033[0m"


def identity_token(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("ID_TOKEN")
    if env:
        return env
    try:
        return subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit(
            "error: no identity token. Pass --token, set $ID_TOKEN, or authenticate gcloud."
        )


def call(
    base: str,
    method: str,
    path: str,
    token: str,
    agent_id: str | None = None,
    body: dict | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, dict | str]:
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    request.add_header("Authorization", f"Bearer {token}")
    if agent_id:
        request.add_header("X-Agent-ID", agent_id)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if idempotency_key:
        request.add_header("Idempotency-Key", idempotency_key)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode()
            try:
                return response.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        return 0, f"unreachable: {exc.reason}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token")
    parser.add_argument(
        "--agent-id", default="example-writer-agent", help="your registered caller id"
    )
    parser.add_argument("--topic", default="example_preference")
    parser.add_argument("--field", default="preference")
    parser.add_argument(
        "--sensitive-topic",
        default="example_sensitive_topic",
        help="a topic your configuration classifies sensitive or restricted",
    )
    args = parser.parse_args()

    token = identity_token(args.token)
    agent = args.agent_id
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"{GREEN}passed{RESET}  {name}")
        else:
            print(f"{RED}failed{RESET}  {name}" + (f" — {detail}" if detail else ""))
            failures.append(name)

    def fact(value: str, text: str, topic: str | None = None) -> dict:
        return {
            "facts": [
                {
                    "topic": topic or args.topic,
                    "field": args.field,
                    "value": value,
                    "fact": text,
                }
            ]
        }

    status, payload = call(args.base_url, "GET", "/readyz", token, agent)
    check("readiness", status == 200, f"status {status}: {payload}")

    # 1. A clean fact is stored, synchronously. There is no queue: by the time this returns, the
    #    write has been made and read back.
    value = f"smoke-{uuid.uuid4().hex[:8]}"
    key = str(uuid.uuid4())
    status, payload = call(
        args.base_url,
        "POST",
        "/v1/memories",
        token,
        agent,
        fact(value, f"Smoke test preference {value}."),
        key,
    )
    body = payload if isinstance(payload, dict) else {}
    check("remember returns 200", status == 200, f"status {status}: {payload}")
    check(
        "the fact was stored",
        body.get("outcome") in ("written", "written_unverified"),
        f"outcome {body.get('outcome')}: {body.get('results')}",
    )
    if body.get("outcome") == "written_unverified":
        print(
            "        note: stored, but the service could not re-read it to confirm. "
            "Not a smoke-test failure; worth an operator's attention."
        )

    # 2. Replaying the same key with the same body returns the original outcome.
    status_repeat, repeat = call(
        args.base_url,
        "POST",
        "/v1/memories",
        token,
        agent,
        fact(value, f"Smoke test preference {value}."),
        key,
    )
    check(
        "replaying the same key is idempotent",
        status_repeat == 200,
        f"status {status_repeat}: {repeat}",
    )

    # 3. The same key with a DIFFERENT body is refused, not silently applied.
    status_conflict, conflict = call(
        args.base_url,
        "POST",
        "/v1/memories",
        token,
        agent,
        fact(value + "-different", "A different fact under the same key."),
        key,
    )
    check(
        "the same key with a different body is refused",
        status_conflict == 422,
        f"status {status_conflict}: {conflict}",
    )

    # 4. Recall returns it. Synchronous, so no polling.
    status, payload = call(
        args.base_url, "GET", f"/v1/memories?topic={args.topic}", token, agent
    )
    values = payload.get("values", []) if isinstance(payload, dict) else []
    check("recall returns 200", status == 200, f"status {status}: {payload}")
    check(
        "recall returns the written value",
        any(value in str(item.get("fact", "")) for item in values),
        f"{len(values)} value(s) returned, none containing {value}",
    )

    # 5. A sensitive topic is refused -- and refused as a no-op, not an error. This is the check
    #    that proves the governance is actually switched on in this deployment.
    status, payload = call(
        args.base_url,
        "POST",
        "/v1/memories",
        token,
        agent,
        fact("smoke", "Smoke test sensitive value.", args.sensitive_topic),
        str(uuid.uuid4()),
    )
    body = payload if isinstance(payload, dict) else {}
    check(
        "a sensitive topic is refused as a no-op",
        status == 200 and body.get("outcome") == "noop" and body.get("stored") == 0,
        f"status {status}: {payload}",
    )

    # 6. An unauthenticated request is refused.
    try:
        request = urllib.request.Request(f"{args.base_url.rstrip('/')}/v1/memories")
        with urllib.request.urlopen(request, timeout=30) as response:
            check(
                "unauthenticated request is refused", False, f"status {response.status}"
            )
    except urllib.error.HTTPError as exc:
        check(
            "unauthenticated request is refused",
            exc.code in (401, 403),
            f"status {exc.code}",
        )
    except urllib.error.URLError as exc:
        check("unauthenticated request is refused", False, f"unreachable: {exc.reason}")

    print()
    if failures:
        print(
            f"{RED}SMOKE TEST FAILED{RESET} — {len(failures)} check(s): {', '.join(failures)}"
        )
        return 1
    print(f"{GREEN}SMOKE TEST PASSED{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
