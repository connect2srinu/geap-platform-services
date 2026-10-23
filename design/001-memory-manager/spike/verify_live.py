#!/usr/bin/env python3
"""Run the Memory Manager against a real Vertex AI Memory Bank.

Pre-release verification for design/001-memory-manager. Every test in the pattern runs against the
fake bank, which proves the code calls the fake correctly and nothing more. This drives the actual
service — endpoints, policy pipeline, adapter, read-back verification — against the provider, which
is the only way to learn whether the adapter's assumptions survive contact.

Not pattern code, and not a test: it writes to a real bank and costs real quota.

Usage
    verify_live.py --project P --location L --bank <full reasoningEngines resource name>
    verify_live.py ... --keep        # leave the written memories behind for inspection

Writes are confined to one scope carrying a random run id, and removed afterwards unless --keep.

Exit status: 0 every check passed, 1 a check failed, 2 the script could not start.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

PATTERN = Path(__file__).resolve().parents[3] / "patterns" / "memory-manager"
sys.path.insert(0, str(PATTERN / "src"))

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(
        f"  {'PASS' if passed else 'FAIL'}  {name}" + (f" — {detail}" if detail else "")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", default="us-central1")
    ap.add_argument("--bank", required=True, help="full reasoningEngines resource name")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    from fastapi.testclient import TestClient

    from memory_manager.api.auth import IdentityConfig, LocalHeaderVerifier
    from memory_manager.api.main import Caller, Deployment, create_app
    from memory_manager.extensions import (
        CallerContext,
        Classification,
        ClassificationResult,
        Fact,
        PolicyDecision,
        Topic,
        TopicField,
    )
    from memory_manager.observability import LoggingMetrics, WriteBudget
    from memory_manager.providers.vertex import VertexMemoryBank

    run_id = uuid.uuid4().hex[:8]
    print(f"run {run_id}  bank {args.bank}\n")

    class AllowAll:
        """Stands in for the domain's classifier and policy. The point here is the provider.

        The signatures must match the protocols exactly. The first run of this script got
        `decide` wrong and every fact was refused with TOPIC_NOT_APPROVED — the pipeline treats a
        broken extension as a denial, which is correct, and is worth seeing once.
        """

        def classify(self, fact: Fact, caller: CallerContext) -> ClassificationResult:
            return ClassificationResult(allowed=True)

        def decide(
            self, caller: CallerContext, operation: str, topic: str
        ) -> PolicyDecision:
            return PolicyDecision(allowed=True)

    topics = {
        "preferred_brands": Topic(
            id="preferred_brands",
            classification=Classification.NON_SENSITIVE,
            enabled=True,
            fields=(TopicField(name="brand", value_type="string", max_length=128),),
        ),
        "health_conditions": Topic(
            id="health_conditions",
            classification=Classification.SENSITIVE,
            enabled=True,
        ),
    }

    bank = VertexMemoryBank(
        project=args.project,
        location=args.location,
        bank=args.bank,
        metrics=LoggingMetrics(domain="example-domain"),
    )

    deployment = Deployment(
        domain=f"example-domain-{run_id}",  # isolates this run's scope from anything else
        topics=topics,
        callers={
            "writer-agent": Caller(
                caller_id="writer-agent",
                operations=frozenset({"remember", "recall"}),
                granted_topics=frozenset(topics),
            )
        },
        bank=bank,
        classifier=AllowAll(),
        policy=AllowAll(),
        identity=IdentityConfig(
            issuer="https://issuer.example-domain.invalid",
            jwks_uri="https://issuer.example-domain.invalid/.well-known/jwks.json",
            audience="memory-manager",
            subject_hmac_key=os.environ.get(
                "SUBJECT_HMAC_KEY", "live-verification-key"
            ),
        ),
        verifier=LocalHeaderVerifier(environment="local"),
        metrics=LoggingMetrics(domain="example-domain"),
        budget=WriteBudget(writes_per_minute=60, max_instances=1),
        auth_enabled=False,
    )
    client = TestClient(create_app(deployment, environment="local"))
    headers = {
        "X-Agent-ID": "writer-agent",
        "Authorization": f"Bearer end-user-{run_id}",
    }

    def fact(value: str, text: str, topic: str = "preferred_brands") -> dict[str, str]:
        return {"topic": topic, "field": "brand", "value": value, "fact": text}

    written_names: list[str] = []
    try:
        print("1. remember — a valid fact reaches the provider")
        t0 = time.monotonic()
        r = client.post(
            "/v1/memories",
            json={"facts": [fact("Horizon", "Prefers the organic brand Horizon.")]},
            headers={**headers, "Idempotency-Key": f"live-{run_id}-1"},
        )
        elapsed = time.monotonic() - t0
        body = r.json() if r.status_code == 200 else {}
        check(
            "remember returns 200",
            r.status_code == 200,
            f"got {r.status_code} {r.text[:160]}",
        )
        check(
            "outcome is written",
            body.get("outcome") == "written",
            str(body.get("outcome")),
        )
        check("one fact stored", body.get("stored") == 1, str(body.get("stored")))
        first = (body.get("results") or [{}])[0]
        check(
            "reason code ACCEPTED",
            first.get("reasonCode") == "ACCEPTED",
            str(first.get("reasonCode")),
        )
        check(
            "a memory id came back",
            bool(first.get("memoryId")),
            str(first.get("memoryId"))[:80],
        )
        check("round trip under 10 s", elapsed < 10, f"{elapsed:.2f} s")
        if first.get("memoryId"):
            written_names.append(first["memoryId"])

        print("\n2. read-back verification ran against the real bank")
        check(
            "outcome is not written_unverified",
            body.get("outcome") != "written_unverified",
            "the service could not re-read what it wrote"
            if body.get("outcome") == "written_unverified"
            else "",
        )

        print("\n3. recall — the fact comes back in this scope")
        r = client.get("/v1/memories", headers=headers)
        # The contract calls them `values`, not `memories` — getting this wrong is how the first
        # run of this script reported a failure that was entirely its own.
        values = r.json().get("values", []) if r.status_code == 200 else []
        check("recall returns 200", r.status_code == 200, f"got {r.status_code}")
        check("the written fact is listed", len(values) >= 1, f"{len(values)} value(s)")
        check(
            "nothing was withheld",
            r.json().get("withheld") == 0,
            str(r.json().get("withheld")),
        )
        if values:
            check(
                "the topic prefix was decoded",
                values[0].get("topic") == "preferred_brands",
                str(values[0].get("topic")),
            )
            check(
                "the field prefix was decoded",
                values[0].get("field") == "brand",
                str(values[0].get("field")),
            )
            check(
                "content survived consolidation",
                "Horizon" in str(values[0].get("fact", "")),
                str(values[0].get("fact"))[:80],
            )

        print("\n4. a sensitive topic never reaches the provider")
        r = client.post(
            "/v1/memories",
            json={
                "facts": [
                    fact("x", "Has a health condition.", topic="health_conditions")
                ]
            },
            headers={**headers, "Idempotency-Key": f"live-{run_id}-2"},
        )
        b2 = r.json()
        check("outcome is noop", b2.get("outcome") == "noop", str(b2.get("outcome")))
        check("nothing stored", b2.get("stored") == 0, str(b2.get("stored")))

        print("\n5. consolidation — a conflicting fact updates rather than duplicating")
        r = client.post(
            "/v1/memories",
            json={
                "facts": [
                    fact(
                        "Meadowlark",
                        "Prefers the organic brand Meadowlark, not Horizon.",
                    )
                ]
            },
            headers={**headers, "Idempotency-Key": f"live-{run_id}-3"},
        )
        b3 = r.json()
        check(
            "second write accepted",
            r.status_code == 200 and b3.get("outcome") in {"written", "noop"},
            f"{r.status_code} {b3.get('outcome')}",
        )
        for res in b3.get("results", []):
            if res.get("memoryId"):
                written_names.append(res["memoryId"])
        r = client.get("/v1/memories", headers=headers)
        after = r.json().get("values", [])
        check("the update is visible", len(after) >= 1, f"{len(after)} value(s)")
        check(
            "scope did not accumulate duplicates",
            len(after) <= 2,
            f"{len(after)} value(s) in scope",
        )

        print("\n6. scope isolation — another end user sees nothing of this one")
        other = {
            "X-Agent-ID": "writer-agent",
            "Authorization": f"Bearer other-user-{run_id}",
        }
        r = client.get("/v1/memories", headers=other)
        leaked = r.json().get("values") or []
        check(
            "a different subject gets an empty scope",
            leaked == [],
            f"{len(leaked)} memory(ies) leaked",
        )

    finally:
        # The response's memoryId is a bare id by design — the full resource name carries the
        # project number — so cleanup goes through the adapter's scope listing, not the response.
        from memory_manager.api.auth import pseudonymise, resolve_scope

        scope = resolve_scope(
            deployment.domain,
            pseudonymise(f"end-user-{run_id}", deployment.identity.subject_hmac_key),
        )
        try:
            leftovers = [m.name for m in bank.retrieve(scope)]
        except Exception as exc:
            leftovers = []
            print(
                f"\ncould not list this run's scope for cleanup: {type(exc).__name__}"
            )
        if args.keep:
            print(
                f"\n--keep: leaving {len(leftovers)} memory(ies) in scope {dict(scope)}"
            )
        else:
            print(f"\ncleanup: removing {len(leftovers)} memory(ies)")
            for name in leftovers:
                try:
                    bank.delete(name)
                except Exception as exc:
                    print(
                        f"  could not delete {name.split('/')[-1]}: {type(exc).__name__}"
                    )

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print("failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # pragma: no cover - spike tooling
        print(f"could not run: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
