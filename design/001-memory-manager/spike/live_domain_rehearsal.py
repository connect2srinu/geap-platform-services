#!/usr/bin/env python3
"""Run the Memory Manager the way an adopting domain runs it, against a real Memory Bank.

`verify_live.py` already drives the service against the provider, but it hand-wires a
`Deployment` in Python and substitutes `LocalHeaderVerifier`. That proves the adapter and the
policy pipeline. It does not touch the path a domain actually runs, so three things had never
been exercised together against a real bank:

* `bootstrap.build_deployment` reading a domain's `domain-config.yaml`,
* `asgi:create`, the container entry point, under a real ASGI server over real HTTP,
* `JwtSubjectVerifier` — real RS256 tokens fetched from a real JWKS endpoint.

They are coupled, which is why this script exists: in `bootstrap._bank` one flag chooses both the
bank and the verifier. `ENVIRONMENT=local` is the fake bank *and* header authentication; anything
else is the real bank *and* full token verification. There is no supported way to point the
running service at a real bank without an OIDC issuer in front of it, so this supplies one.

The issuer is throwaway. A 2048-bit RSA key is generated per run, held in memory, served from
localhost, and discarded when the process exits; it is never written to disk and never leaves the
machine. It stands in for the domain's real identity provider and is not part of the pattern.

Not pattern code, and not a test: it writes to a real bank and costs real quota.

Requirements
    Python 3.12, `uv`, and Application Default Credentials that may generate, list and delete
    memories on --bank. The script builds its own virtualenv and re-executes itself inside it, so
    nothing needs to be installed first.

Usage
    live_domain_rehearsal.py --project P --location us-central1 --bank <reasoningEngines name>
    live_domain_rehearsal.py ... --keep      # leave the memories and the project dir behind

Writes are confined to two end users carrying a random run id, and deleted afterwards unless
--keep.

Exit status: 0 every check passed, 1 a check failed, 2 the script could not start.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "domain-consumer"
PATTERN = REPO / "patterns" / "memory-manager"

#: Set in the child so the re-exec happens exactly once.
REEXEC_FLAG = "GEAP_LIVE_REHEARSAL_INNER"

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  {mark}  {name}" + (f" — {detail}" if detail else ""))


def step(text: str) -> None:
    print(f"\n{YELLOW}>>{RESET} {text}")


# -- the throwaway issuer ----------------------------------------------------------------


def _b64url(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class ThrowawayIssuer:
    """An RSA keypair and the JWKS endpoint that publishes it, on localhost.

    The private key never leaves this process. `sign` mints the kind of token a domain's identity
    provider would forward: one end user per `subject`.
    """

    def __init__(self, audience: str) -> None:
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.audience = audience
        self.kid = uuid.uuid4().hex[:16]
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = self._private.public_key().public_numbers()
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.kid,
                    "n": _b64url(numbers.n),
                    "e": _b64url(numbers.e),
                }
            ]
        }
        self._server: HTTPServer | None = None

    def start(self) -> str:
        """Serve the JWKS and return the issuer URL."""
        body = json.dumps(self.jwks).encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
                if self.path != "/.well-known/jwks.json":
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                """Silence the per-request line; the rehearsal prints its own steps."""

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self._server.server_port}"

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()

    def sign(
        self,
        subject: str,
        issuer: str,
        *,
        audience: str | None = None,
        lifetime: int = 300,
    ) -> str:
        import jwt
        from cryptography.hazmat.primitives import serialization

        pem = self._private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        now = int(time.time())
        return jwt.encode(
            {
                "iss": issuer,
                "aud": audience or self.audience,
                "sub": subject,
                "iat": now,
                "exp": now + lifetime,
            },
            pem,
            algorithm="RS256",
            headers={"kid": self.kid},
        )


# -- the domain project ------------------------------------------------------------------

#: A customer domain's own vocabulary, not the template's `example_*` placeholders. The point of
#: the rehearsal is a configuration a domain would plausibly write.
DOMAIN_CONFIG = """\
domain:
  name: {domain}

retention:
  days: 365

topics:
  - id: delivery_preference
    classification: non-sensitive
    enabled: true
    allowInferred: false
    fields:
      - name: window
        valueType: string
        maxLength: 128

  - id: contact_channel
    classification: non-sensitive
    enabled: true
    allowInferred: false
    fields:
      - name: channel
        valueType: string
        maxLength: 64

  # Declared, granted and enabled, so the refusal can only come from the classification. A
  # topic that was also disabled would be refused for being disabled, and the check below would
  # pass without ever reaching the rule it claims to cover.
  - id: payment_detail
    classification: restricted
    enabled: true

  - id: legacy_preference
    classification: non-sensitive
    enabled: false

callers:
  - id: ordering-agent
    subject: ordering-agent@{domain}.invalid
    operations: [remember, recall]
    topics: [delivery_preference, contact_channel, payment_detail, legacy_preference]
    maxRequestsPerMinute: 60

  - id: lookup-agent
    subject: lookup-agent@{domain}.invalid
    operations: [recall]
    topics: [delivery_preference]
    maxRequestsPerMinute: 60

identity:
  issuer: {issuer}
  jwksUri: {issuer}/.well-known/jwks.json
  audience: {audience}

extensions:
  piiClassifier: extensions.sample_classifier.SampleClassifier
  policyProvider: extensions.sample_policy.SamplePolicyProvider

quota:
  maxWritesPerMinute: 60

observability:
  logLevel: INFO
"""


def build_project(root: Path, domain: str, issuer: str, audience: str) -> Path:
    """Lay out a domain project from the shipped template, with its own configuration."""
    project = root / "domain-project"
    shutil.copytree(
        TEMPLATE,
        project,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    (project / "config" / "domain-config.yaml").write_text(
        DOMAIN_CONFIG.format(domain=domain, issuer=issuer, audience=audience)
    )
    return project


# -- HTTP --------------------------------------------------------------------------------


def call(
    base: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    agent_id: str | None = None,
    body: dict | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, dict | str]:
    request = urllib.request.Request(
        f"{base.rstrip('/')}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if agent_id:
        request.add_header("X-Agent-ID", agent_id)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    if idempotency_key:
        request.add_header("Idempotency-Key", idempotency_key)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, (json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        return 0, f"unreachable: {exc.reason}"


def wait_for_ready(base: str, process: subprocess.Popen[bytes], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        status, _ = call(base, "GET", "/healthz")
        if status == 200:
            return True
        time.sleep(0.5)
    return False


# -- the environment the service runs in -------------------------------------------------


def ensure_venv(path: Path) -> Path:
    """Create the virtualenv the service runs in, and return its interpreter.

    Installs the pattern from this checkout with the `provider` extra, which is what a domain
    gets from its vendored copy. Reused across runs; delete the directory to rebuild it.
    """
    python = path / "bin" / "python"
    if not python.exists():
        print(f"creating {path}")
        subprocess.run(
            ["uv", "venv", "--python", "3.12", str(path)], check=True, capture_output=True
        )
    print("installing memory-manager[provider] ...")
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), "-q", f"{PATTERN}[provider]"],
        check=True,
    )
    return python


def reexec_inside(python: Path) -> int:
    """Re-run this script under `python`, so it can mint tokens and reach the SDK."""
    env = dict(os.environ, **{REEXEC_FLAG: "1"})
    return subprocess.run([str(python), "-I", __file__, *sys.argv[1:]], env=env).returncode


# -- cleanup -----------------------------------------------------------------------------


def delete_scope(args: argparse.Namespace, domain: str, subjects: list[str], hmac_key: str) -> int:
    """Remove every memory this run wrote, through the pattern's own adapter."""
    sys.path.insert(0, str(PATTERN / "src"))
    from memory_manager.api.auth import pseudonymise, resolve_scope
    from memory_manager.providers.vertex import VertexMemoryBank

    bank = VertexMemoryBank(
        project=args.project, location=args.location, bank=args.bank
    )
    removed = 0
    for subject in subjects:
        scope = resolve_scope(domain, pseudonymise(subject, hmac_key))
        for memory in bank.retrieve(scope):
            bank.delete(memory.name)
            removed += 1
    return removed


# -- the rehearsal -------------------------------------------------------------------------


def rehearse(args: argparse.Namespace, base: str, issuer: ThrowawayIssuer, issuer_url: str) -> None:
    alice = f"alice-{args.run_id}@{args.domain}.invalid"
    bob = f"bob-{args.run_id}@{args.domain}.invalid"
    alice_token = issuer.sign(alice, issuer_url)
    bob_token = issuer.sign(bob, issuer_url)

    status, _ = call(base, "GET", "/readyz")
    check("readiness", status == 200, f"status {status}")

    # Authentication, before anything is written. Both of these must fail for the rest of the
    # run to mean anything: a service that accepts an unsigned request is not isolating anyone.
    status, payload = call(base, "GET", "/v1/memories", agent_id="ordering-agent")
    check(
        "a request with no token is refused",
        status == 401,
        f"status {status}, code {payload.get('code') if isinstance(payload, dict) else payload}",
    )

    wrong = issuer.sign(alice, issuer_url, audience="some-other-service")
    status, payload = call(
        base, "GET", "/v1/memories", token=wrong, agent_id="ordering-agent"
    )
    check(
        "a token for another audience is refused",
        status == 401,
        f"status {status}, code {payload.get('code') if isinstance(payload, dict) else payload}",
    )

    expired = issuer.sign(alice, issuer_url, lifetime=-60)
    status, payload = call(
        base, "GET", "/v1/memories", token=expired, agent_id="ordering-agent"
    )
    check(
        "an expired token is refused",
        status == 401,
        f"status {status}, code {payload.get('code') if isinstance(payload, dict) else payload}",
    )

    # A clean write. This is the whole path: JWT verified against the JWKS endpoint, subject
    # pseudonymised, scope derived, policy run, fact written to the bank and read back.
    window = f"weekday evenings (run {args.run_id})"
    key = str(uuid.uuid4())
    body = {
        "facts": [
            {
                "topic": "delivery_preference",
                "field": "window",
                "value": window,
                "fact": f"The customer prefers delivery {window}.",
            }
        ]
    }
    started = time.monotonic()
    status, written = call(
        base,
        "POST",
        "/v1/memories",
        token=alice_token,
        agent_id="ordering-agent",
        body=body,
        idempotency_key=key,
    )
    elapsed = time.monotonic() - started
    stored_ok = (
        status == 200
        and isinstance(written, dict)
        and written.get("outcome") in {"written", "written_unverified"}
        and written.get("stored") == 1
    )
    check(
        "a clean fact is written to the real bank",
        stored_ok,
        f"status {status}, outcome {written.get('outcome') if isinstance(written, dict) else written}, {elapsed:.2f} s",
    )

    # Recall over the same scope. The adapter lists the scope rather than running a similarity
    # search, so this is the real listing, not a nearest-neighbour guess.
    status, recalled = call(
        base, "GET", "/v1/memories", token=alice_token, agent_id="ordering-agent"
    )
    values = recalled.get("values", []) if isinstance(recalled, dict) else []
    check(
        "recall returns the fact that was just written",
        status == 200 and any(window in str(v.get("fact", "")) for v in values),
        f"status {status}, {len(values)} value(s), withheld {recalled.get('withheld') if isinstance(recalled, dict) else '?'}",
    )

    # S-8. Bob's token over the same agent and the same bank must see nothing of Alice's. This
    # is the check that would catch a scope derived from anything the caller controls.
    status, bobs = call(
        base, "GET", "/v1/memories", token=bob_token, agent_id="ordering-agent"
    )
    bobs_values = bobs.get("values", []) if isinstance(bobs, dict) else []
    check(
        "a second end user sees none of the first user's memories (S-8)",
        status == 200 and not bobs_values,
        f"status {status}, {len(bobs_values)} value(s)",
    )

    # Replaying the same idempotency key with the same body returns the recorded response
    # rather than writing twice.
    status, replay = call(
        base,
        "POST",
        "/v1/memories",
        token=alice_token,
        agent_id="ordering-agent",
        body=body,
        idempotency_key=key,
    )
    check(
        "replaying the idempotency key returns the recorded response",
        status == 200 and replay == written,
        f"status {status}, identical: {replay == written}",
    )

    # The domain's own classifier, running on a real request. An email address in the narrative
    # is refused even though the topic is eligible and the caller is permitted.
    status, denied = call(
        base,
        "POST",
        "/v1/memories",
        token=alice_token,
        agent_id="ordering-agent",
        body={
            "facts": [
                {
                    "topic": "contact_channel",
                    "field": "channel",
                    "value": "email",
                    "fact": f"Reach the customer at alice.{args.run_id}@example.invalid.",
                }
            ]
        },
        idempotency_key=str(uuid.uuid4()),
    )
    check(
        "the domain's classifier refuses a fact carrying an email address",
        status == 200
        and isinstance(denied, dict)
        and denied.get("outcome") == "noop"
        and denied.get("stored") == 0,
        f"status {status}, outcome {denied.get('outcome') if isinstance(denied, dict) else denied}",
    )

    # Classification, and nothing else. The topic is declared, enabled and granted to this
    # caller, so TOPIC_RESTRICTED is the only reason left — which is what makes the check mean
    # what its name says.
    def refusal(topic: str) -> tuple[int, int | None, list[str | None]]:
        status, payload = call(
            base,
            "POST",
            "/v1/memories",
            token=alice_token,
            agent_id="ordering-agent",
            body={
                "facts": [
                    {
                        "topic": topic,
                        "value": "stored-card",
                        "fact": "The customer keeps a card on file.",
                    }
                ]
            },
            idempotency_key=str(uuid.uuid4()),
        )
        if not isinstance(payload, dict):
            return status, None, []
        return (
            status,
            payload.get("stored"),
            [r.get("reasonCode") for r in payload.get("results", [])],
        )

    status, stored, reasons = refusal("payment_detail")
    check(
        "a restricted topic stores nothing, and says so truthfully",
        status == 200 and stored == 0 and reasons == ["TOPIC_RESTRICTED"],
        f"status {status}, stored {stored}, reason {reasons}",
    )

    status, stored, reasons = refusal("legacy_preference")
    check(
        "a disabled topic stores nothing",
        status == 200 and stored == 0 and reasons == ["TOPIC_DISABLED"],
        f"status {status}, stored {stored}, reason {reasons}",
    )

    # A recall-only caller cannot write, whatever it sends.
    status, forbidden = call(
        base,
        "POST",
        "/v1/memories",
        token=alice_token,
        agent_id="lookup-agent",
        body=body,
        idempotency_key=str(uuid.uuid4()),
    )
    check(
        "a recall-only caller cannot write",
        status == 403,
        f"status {status}, code {forbidden.get('code') if isinstance(forbidden, dict) else forbidden}",
    )

    # An idempotency key is mandatory on a write.
    status, nokey = call(
        base,
        "POST",
        "/v1/memories",
        token=alice_token,
        agent_id="ordering-agent",
        body=body,
    )
    check(
        "a write without an idempotency key is refused",
        status == 400
        and isinstance(nokey, dict)
        and nokey.get("code") == "IDEMPOTENCY_KEY_MISSING",
        f"status {status}, code {nokey.get('code') if isinstance(nokey, dict) else nokey}",
    )

    args.subjects = [alice, bob]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", default="us-central1")
    ap.add_argument("--bank", required=True, help="full reasoningEngines resource name")
    ap.add_argument("--domain", default="orders-demo")
    ap.add_argument("--port", type=int, default=8137)
    ap.add_argument(
        "--venv",
        default=str(Path.home() / ".cache" / "geap" / "live-rehearsal-venv"),
        help="virtualenv the service runs in; reused across runs",
    )
    ap.add_argument("--keep", action="store_true", help="keep the memories and the project")
    args = ap.parse_args()
    args.run_id = os.environ.get("GEAP_RUN_ID") or uuid.uuid4().hex[:8]

    # Outer pass: build the environment, then run everything else inside it.
    if not os.environ.get(REEXEC_FLAG):
        try:
            python = ensure_venv(Path(args.venv))
        except subprocess.CalledProcessError as exc:
            print(f"cannot start: building the virtualenv failed: {exc}")
            return 2
        os.environ["GEAP_RUN_ID"] = args.run_id
        return reexec_inside(python)

    print(
        f"live domain rehearsal | run {args.run_id} | domain {args.domain}\n"
        f"bank {args.bank}"
    )

    issuer = ThrowawayIssuer(audience=f"{args.domain}-memory-manager")
    issuer_url = issuer.start()
    step(f"throwaway issuer on {issuer_url} (key generated this run, never written to disk)")

    root = Path(tempfile.mkdtemp(prefix="geap-live-"))
    base = f"http://127.0.0.1:{args.port}"
    hmac_key = uuid.uuid4().hex
    log_path = root / "service.log"
    process: subprocess.Popen[bytes] | None = None
    args.subjects = []

    try:
        project = build_project(root, args.domain, issuer_url, issuer.audience)
        step(f"domain project at {project} (from templates/domain-consumer)")

        step("booting memory_manager.asgi:create against the real bank")
        env = dict(
            os.environ,
            CONFIG_PATH=str(project / "config" / "domain-config.yaml"),
            # Not 'local'. This is what makes bootstrap choose the real bank AND real token
            # verification — the two cannot be separated, which is why the issuer exists.
            ENVIRONMENT="production",
            GOOGLE_CLOUD_PROJECT=args.project,
            GOOGLE_CLOUD_LOCATION=args.location,
            MEMORY_BANK_ID=args.bank,
            SUBJECT_HMAC_KEY=hmac_key,
            MAX_INSTANCES="1",
            PYTHONPATH=str(project),
        )
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "memory_manager.asgi:create",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                ],
                cwd=project,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            if not wait_for_ready(base, process, 60.0):
                print(f"\n{RED}the service did not become ready{RESET}")
                print(log_path.read_text()[-4000:])
                return 2

            step("running the rehearsal over HTTP")
            try:
                rehearse(args, base, issuer, issuer_url)
            except Exception as exc:  # noqa: BLE001 - recorded, so cleanup still runs
                check(
                    "the rehearsal ran to completion",
                    False,
                    f"{type(exc).__name__}: {str(exc)[:200]}",
                )
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
        issuer.stop()

    # S-4, against a real run rather than a unit test: nothing the service logged may carry the
    # fact, the raw subject or the token. Checked after shutdown so the log is complete.
    logs = log_path.read_text(errors="replace") if log_path.exists() else ""
    leaked = [
        label
        for label, needle in (
            ("the fact text", f"run {args.run_id}"),
            ("the raw end-user subject", f"alice-{args.run_id}"),
            ("the HMAC key", hmac_key),
        )
        if needle in logs
    ]
    check(
        "nothing prohibited reaches the logs (S-4)",
        not leaked,
        f"{len(logs.splitlines())} log line(s); leaked: {leaked or 'none'}",
    )

    if args.keep:
        print(f"\n--keep: memories left in the bank; project and log under {root}")
    else:
        step("removing the memories this run wrote")
        try:
            removed = delete_scope(args, args.domain, args.subjects, hmac_key)
            print(f"  deleted {removed} memory(ies)")
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            print(f"  {RED}cleanup FAILED{RESET}: {type(exc).__name__}: {str(exc)[:200]}")
            print(f"  memories remain under domain '{args.domain}' for {args.subjects}")
        shutil.rmtree(root, ignore_errors=True)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
