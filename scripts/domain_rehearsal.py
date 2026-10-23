#!/usr/bin/env python3
"""Perform a domain adoption rehearsal, start to finish.

The onboarding materials rotted because nothing executed them. Seven defects reached `main`
together: a configuration that could not validate, a smoke test written against a superseded API,
documentation describing endpoints that do not exist, a Dockerfile naming a module that does not
exist. Every one was correct when it was written.

So this is the fix, and the seven corrections are only what it takes to make it pass. It builds a
domain project from `templates/domain-consumer/`, vendors the pattern, boots the service and runs
the pattern's conformance suite against it over HTTP.

    python3 scripts/domain_rehearsal.py [--keep]

Uses the fake memory bank, so it needs no cloud credentials and runs on every pull request. It
therefore proves the documented path works, **not** that the provider does — live verification is
a separate, explicitly labelled step.

Exit status: 0 every step passed, 1 a step failed.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "templates" / "domain-consumer"
PATTERN_NAME = "memory-manager"
PORT = int(os.environ.get("REHEARSAL_PORT", "8123"))
BASE = f"http://127.0.0.1:{PORT}"

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"

#: Values the rehearsal writes, which must never appear in the service's own output.
PROHIBITED_IN_LOGS = ("Horizon", "20mg", "end-user-rehearsal")

results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    mark = f"{GREEN}passed{RESET}" if ok else f"{RED}failed{RESET}"
    print(f"  {mark}  {name}" + (f" — {detail}" if detail and not ok else ""))
    return ok


def run(
    args: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
    )


def call(
    method: str, path: str, body: dict | None = None, **headers: str
) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{BASE}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name.replace("_", "-"), value)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {}
    except urllib.error.URLError as exc:
        return 0, {"unreachable": str(exc.reason)}


def build_project(workspace: Path) -> Path:
    """Step 3 of the adoption guide: copy the template into your own repository."""
    project = workspace / "domain-project"
    shutil.copytree(TEMPLATE, project)
    (project / "pattern.lock.yaml").write_text(
        "pattern:\n"
        f"  name: {PATTERN_NAME}\n"
        "  version: 0.1.0\n"
        f"  source: {REPO}\n"
        f"  path: {REPO}\n"
        "  unreleased: true\n"
        "  manifestDigest:\n",
        encoding="utf-8",
    )
    return project


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep", action="store_true", help="leave the project in place"
    )
    args = parser.parse_args()

    workspace = Path(tempfile.mkdtemp(prefix="rehearsal-"))
    server: subprocess.Popen[bytes] | None = None
    log_path = workspace / "server.log"
    try:
        print(f"{DIM}workspace {workspace}{RESET}\n")

        print("1. a domain project, from the template")
        project = build_project(workspace)
        step("template copied", (project / "config" / "domain-config.yaml").is_file())

        print("\n2. vendor the pattern")
        vendored = run([sys.executable, "scripts/vendor_pattern.py"], project)
        if not step(
            "vendored",
            vendored.returncode == 0 and (project / "vendor" / "pattern").is_dir(),
            (vendored.stdout + vendored.stderr)[-400:],
        ):
            return finish()
        locked = run([sys.executable, "scripts/verify_pattern_lock.py"], project)
        step("lock verifies", locked.returncode == 0, locked.stdout + locked.stderr)

        print("\n3. install it into the project's own environment")
        # A dedicated environment, not this one. Otherwise the pattern is already importable and
        # the rehearsal proves nothing about whether the vendored copy installs — which is how
        # the first run of this script passed step 4 while step 3 was failing.
        venv = project / ".venv"
        created = run([sys.executable, "-m", "venv", str(venv)], project)
        python = venv / "bin" / "python"
        if not step(
            "project environment created",
            created.returncode == 0 and python.is_file(),
            (created.stderr or "")[-400:],
        ):
            return finish()
        # The [dev] extra, because the conformance suite needs an HTTP client to reach a
        # deployed service. A base install cannot run it, which nothing told a domain.
        install = run(
            [str(python), "-m", "pip", "install", "--quiet", "./vendor/pattern[dev]"],
            project,
        )
        step(
            "the vendored pattern installs",
            install.returncode == 0,
            (install.stderr or install.stdout or "")[-500:],
        )

        print("\n4. boot the service on the domain's own configuration")
        env = {
            "PYTHONPATH": str(project),
            "CONFIG_PATH": str(project / "config" / "domain-config.yaml"),
            "ENVIRONMENT": "local",
            "SUBJECT_HMAC_KEY": "rehearsal-only-key",
            "MAX_INSTANCES": "1",
        }
        with log_path.open("wb") as log:
            server = subprocess.Popen(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "memory_manager.asgi:create",
                    "--factory",
                    "--port",
                    str(PORT),
                ],
                cwd=project,
                env={**os.environ, **env},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        healthy = False
        for _ in range(40):
            if call("GET", "/healthz")[0] == 200:
                healthy = True
                break
            time.sleep(0.5)
        if not step(
            "service healthy", healthy, log_path.read_text(errors="ignore")[-600:]
        ):
            return finish()

        print("\n5. the pattern's conformance suite, against this build")
        conformance = run(
            [str(python), "-m", "pytest", "-q", "vendor/pattern/conformance/"],
            project,
            {
                "CONFORMANCE_BASE_URL": BASE,
                "CONFORMANCE_AGENT_ID": "example-writer-agent",
                "CONFORMANCE_READER_ID": "example-reader-agent",
                "CONFORMANCE_ALLOWED_TOPIC": "example_preference",
                "CONFORMANCE_ALLOWED_FIELD": "preference",
                "CONFORMANCE_SENSITIVE_TOPIC": "example_sensitive_topic",
            },
        )
        step(
            "conformance against the domain build",
            conformance.returncode == 0,
            conformance.stdout[-700:],
        )

        print("\n6. the governance a domain is adopting this for")
        writer = {
            "X_Agent_ID": "example-writer-agent",
            "Authorization": "Bearer end-user-rehearsal",
        }

        def remember(topic: str, text: str, value: str = "Horizon") -> dict:
            return call(
                "POST",
                "/v1/memories",
                {
                    "facts": [
                        {
                            "topic": topic,
                            "field": "preference",
                            "value": value,
                            "fact": text,
                        }
                    ]
                },
                Idempotency_Key=str(uuid.uuid4()),
                **writer,
            )[1]

        ok = remember("example_preference", "Prefers the organic brand Horizon.")
        step("a clean fact is stored", ok.get("outcome") == "written", str(ok))

        blocked = remember("example_sensitive_topic", "Something sensitive.")
        step(
            "a sensitive topic is refused",
            blocked.get("outcome") == "noop",
            str(blocked),
        )

        prohibited = remember(
            "example_preference", "Takes 20mg of something and prefers Horizon."
        )
        reason = (prohibited.get("results") or [{}])[0].get("reasonCode")
        step(
            "an allowed topic carrying prohibited content is refused",
            prohibited.get("outcome") == "noop" and reason == "VALUE_PROHIBITED",
            str(prohibited),
        )

        status, recalled = call(
            "GET", "/v1/memories?topic=example_preference", **writer
        )
        values = recalled.get("values", [])
        step(
            "recall returns the stored fact and nothing else",
            status == 200
            and len(values) == 1
            and "Horizon" in str(values[0].get("fact")),
            str(recalled),
        )

        print("\n7. nothing the service refused reached its own output (S-4)")
        output = log_path.read_text(errors="ignore")
        leaked = [
            token for token in PROHIBITED_IN_LOGS if token.lower() in output.lower()
        ]
        step("no payload or raw subject in the logs", not leaked, f"leaked: {leaked}")

    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover
                server.kill()
        if args.keep:
            print(f"\n{DIM}--keep: {workspace}{RESET}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)

    return finish()


def finish() -> int:
    failed = [name for name, ok, _ in results if not ok]
    print()
    if failed:
        print(f"{RED}REHEARSAL FAILED{RESET} — {len(failed)}: {', '.join(failed)}")
        return 1
    print(
        f"{GREEN}REHEARSAL PASSED{RESET} — {len(results)} steps. "
        "Against the FAKE memory bank: this proves the documented path works, "
        "not that the provider does."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
