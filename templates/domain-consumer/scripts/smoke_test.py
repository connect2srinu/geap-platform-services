#!/usr/bin/env python3
"""Post-deployment smoke test for a domain's Memory Manager.

Proves the deployment actually works end to end, against the real managed service -- which unit
tests and a mock provider cannot do.

    python3 scripts/smoke_test.py --base-url https://<service-url>

Identity comes from --token, else $ID_TOKEN, else `gcloud auth print-identity-token`.
Standard library only, so it runs in CI without a project environment.

Exits non-zero on the first failure. Each check prints passed / failed; nothing is reported as
passing that did not run.
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
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit("error: no identity token. Pass --token, set $ID_TOKEN, or authenticate gcloud.")


def call(
    base: str, method: str, path: str, token: str,
    body: dict | None = None, idempotency_key: str | None = None,
) -> tuple[int, dict | str]:
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    request.add_header("Authorization", f"Bearer {token}")
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
    parser.add_argument("--attribute", default="smoke_test_preference")
    args = parser.parse_args()

    token = identity_token(args.token)
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        if ok:
            print(f"{GREEN}passed{RESET}  {name}")
        else:
            print(f"{RED}failed{RESET}  {name}" + (f" — {detail}" if detail else ""))
            failures.append(name)

    # 1. Readiness. Fails until the PLATFORM-OWNED memory bank IAM binding exists, which is
    #    expected on a first deploy -- see docs/runbook.md.
    status, payload = call(args.base_url, "GET", "/readyz", token)
    check("readiness", status == 200, f"status {status}: {payload}")
    if status != 200:
        print("\n  /readyz is failing. If this is a first deployment, the platform team may not")
        print("  have applied the memory bank IAM binding yet. Check that before debugging code.")
        return 1

    # 2. A write is accepted and durably enqueued.
    key = str(uuid.uuid4())
    value = f"smoke-{key[:8]}"
    status, payload = call(
        args.base_url, "POST", "/v1/memories", token,
        body={"fact": {"attribute": args.attribute, "value": value}, "extraction_mode": "none"},
        idempotency_key=key,
    )
    # 202 means durably enqueued. 503 means NOT accepted -- a real distinction, not a nuance.
    check("remember returns 202", status == 202, f"status {status}: {payload}")

    # 3. The same key twice must produce one effect, not two.
    status_repeat, _ = call(
        args.base_url, "POST", "/v1/memories", token,
        body={"fact": {"attribute": args.attribute, "value": value}, "extraction_mode": "none"},
        idempotency_key=key,
    )
    check("duplicate idempotency key is accepted idempotently", status_repeat in (200, 202),
          f"status {status_repeat}")

    # 4. A different payload under the same key must be refused.
    status_conflict, _ = call(
        args.base_url, "POST", "/v1/memories", token,
        body={"fact": {"attribute": args.attribute, "value": value + "-different"},
              "extraction_mode": "none"},
        idempotency_key=key,
    )
    check("same key with a different payload returns 422", status_conflict == 422,
          f"status {status_conflict}")

    # 5. The value reads back. Writes are asynchronous and provider reads are eventually
    #    consistent, so this is retried rather than asserted once.
    found = False
    for _ in range(10):
        status, payload = call(
            args.base_url, "GET", f"/v1/memories?attribute={args.attribute}", token)
        if status == 200 and value in json.dumps(payload):
            found = True
            break
        import time
        time.sleep(3)
    check("recall returns the written value", found, "not visible within 30s")

    # 6. An unauthenticated caller is refused (control C-01).
    request = urllib.request.Request(f"{args.base_url.rstrip('/')}/v1/memories")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            check("unauthenticated request is refused", False, f"status {response.status}")
    except urllib.error.HTTPError as exc:
        check("unauthenticated request is refused", exc.code in (401, 403), f"status {exc.code}")
    except urllib.error.URLError as exc:
        check("unauthenticated request is refused", False, f"unreachable: {exc.reason}")

    print()
    if failures:
        print(f"{RED}SMOKE TEST FAILED{RESET} — {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print(f"{GREEN}SMOKE TEST PASSED{RESET}")
    print("\nThis proves the live path works. It does NOT check that memory content stays out of")
    print("logs — verify that separately; see docs/runbook.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
