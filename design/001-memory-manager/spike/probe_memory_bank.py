#!/usr/bin/env python3
"""Tier 1 live probe for design/001-memory-manager: checks L1-L9 and L11.

Answers the provider assumptions in design.md "Live verification" (Tier 1) against a real Memory
Bank, with no pattern code. Each check prints PASS, FAIL or UNAVAILABLE with its evidence.
UNAVAILABLE means the check could not run (missing input, no permission, an SDK surface that
differs from the pinned one, a throttled or failing provider). It is never a pass. INFO lines are
observations, not verdicts.

This is a design-stage spike, written 2026-10-22 before Gate D at the requester's instruction. It
is not pattern code, and the pattern never imports it.

Requirements
    Python 3.10+ and the SDK pinned provisionally in tasks.md DEC-11:
        pip install 'google-cloud-aiplatform[agent_engines]==2.3.0'   # provides `agentplatform`
    Application Default Credentials for a principal that can generate, get, list, retrieve, roll
    back and delete memories on --bank. --create-scratch-banks also needs permission to create,
    read and delete memory banks. For L11 the Memory Bank service agent needs encrypt and decrypt
    on --kms-key.

Inputs
    --bank                  an existing bank provisioned for this spike (full resource name). The
                            probe writes only into its own scopes.
    --create-scratch-banks  create two short-lived banks, deleted at the end: one with generate
                            TTLs for L7, one with --kms-key for L11. Their memory configuration is
                            copied from --bank when it can be read.
    --ttl-bank              instead: a bank whose ttl_config.granular_ttl_config sets
                            generate_created_ttl and generate_updated_ttl to --ttl-seconds.
    --cmek-bank             instead: a bank created with --kms-key.

Data
    Every fact is synthetic ("[topic=probe_...][field=...] ..."), and every scope is
    {"user_id": "probe-<run>-<check>"}. Nothing real is written. Memories the probe wrote are
    deleted at the end unless --keep. Printed resource names have the project segment replaced by
    <project>.

Example
    python3 probe_memory_bank.py --project <project-id> --location us-central1 \\
        --bank <bank resource name> --create-scratch-banks \\
        --kms-key projects/<project-id>/locations/us-central1/keyRings/<ring>/cryptoKeys/<key> \\
        --l9-trials 100 --json tier1.json

Exit status: 0 no FAIL, 1 at least one FAIL, 2 the probe could not start.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.metadata
import json
import math
import platform
import re
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

PINNED_SDK = "2.3.0"
TIER1 = ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L11"]
TITLES = {
    "L1": "GenerateMemories + direct_memories_source stores facts verbatim and still consolidates",
    "L2": "The operation result lists affected memories by name with an action",
    "L3": "get immediately after the operation reflects the consolidated content",
    "L4": "Revisions listable; rollback restores; rollback and delete leave no prohibited revision",
    "L5": "An identical fact submitted twice consolidates into one memory",
    "L6": "The bracketed fact prefix survives consolidation",
    "L7": "A TTL applies to generated memories, survives consolidation, and expires them",
    "L8": "Scope-only retrieve returns every memory in the scope, across pages",
    "L9": "Read-after-write bound for AC13",
    "L11": "The bank accepts a customer-managed key and reports it as its encryption key",
}
PREFIX = re.compile(r"^\[topic=[a-z0-9_]+\]\[field=[a-z0-9_]+\] \S")
PASS, FAIL, UNAVAILABLE, INFO = "PASS", "FAIL", "UNAVAILABLE", "INFO"
ACTIONS = {"CREATED", "UPDATED", "DELETED"}


@dataclass
class Result:
    check: str
    status: str
    title: str
    evidence: list[str] = field(default_factory=list)


class Unavailable(Exception):
    """The check could not run. Never a pass."""


def redact(text: object) -> str:
    return re.sub(r"projects/[^/\s'\"]+", "projects/<project>", str(text))


def classify(exc: BaseException) -> tuple[str, str]:
    """UNAVAILABLE when the check could not run; FAIL when the provider answered no."""
    name = type(exc).__name__
    message = redact(exc)[:300]
    code = getattr(exc, "code", None)
    if isinstance(exc, Unavailable):
        return UNAVAILABLE, message
    if isinstance(exc, (ImportError, AttributeError, TypeError)):
        return UNAVAILABLE, f"SDK surface differs from {PINNED_SDK}: {name}: {message}"
    if code in (401, 403) or name in ("DefaultCredentialsError", "RefreshError"):
        return UNAVAILABLE, f"no permission or credentials: {name} {code}: {message}"
    if code in (429, 500, 502, 503, 504) or isinstance(
        exc, (TimeoutError, ConnectionError)
    ):
        return (
            UNAVAILABLE,
            f"provider throttled or unavailable: {name} {code}: {message}",
        )
    return FAIL, f"{name} {code}: {message}"


def is_not_found(exc: BaseException) -> bool:
    return getattr(exc, "code", None) == 404


def action(item: Any) -> str:
    value = getattr(item, "action", None)
    return str(getattr(value, "value", value) or "")


def memory_name(item: Any) -> str:
    return getattr(getattr(item, "memory", None), "name", None) or ""


def memory_fact(item: Any) -> str | None:
    return getattr(getattr(item, "memory", None), "fact", None)


def last_segment(name: str) -> str:
    return name.rstrip("/").rsplit("/", 1)[-1]


def as_datetime(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


class Probe:
    def __init__(self, args: argparse.Namespace, client: Any) -> None:
        self.args = args
        self.client = client
        self.memories = client.memory_banks.memories
        self.run = uuid.uuid4().hex[:8]
        self.results: list[Result] = []
        self.written: set[tuple[str, str]] = set()
        self.scratch_banks: list[str] = []
        self.ttl_bank: str | None = args.ttl_bank

    # ---- output -------------------------------------------------------------------------------

    def emit(self, result: Result) -> None:
        result.evidence = [redact(e) for e in result.evidence]
        self.results.append(result)
        print(f"{result.check:<4} {result.status:<11} {result.title}")
        for line in result.evidence:
            print(f"     - {line}")
        sys.stdout.flush()

    def info(self, check: str, text: str) -> None:
        self.emit(Result(check, INFO, "observation", [text]))

    def recorded(self, check: str) -> bool:
        return any(r.check == check and r.status != INFO for r in self.results)

    def wanted(self, check: str) -> bool:
        return check in self.args.only

    def group(self, checks: list[str], body: Callable[[], None]) -> None:
        """Run checks that share setup. If setup or a step raises, the first check not yet
        recorded takes the classified status and the rest are UNAVAILABLE: they depend on it."""
        if not any(self.wanted(c) for c in checks):
            return
        try:
            body()
        except Exception as exc:  # noqa: BLE001 - every failure is classified and reported
            status, message = classify(exc)
            pending = [c for c in checks if self.wanted(c) and not self.recorded(c)]
            for index, check in enumerate(pending):
                if index == 0:
                    self.emit(Result(check, status, TITLES[check], [message]))
                else:
                    self.emit(
                        Result(
                            check,
                            UNAVAILABLE,
                            TITLES[check],
                            [f"depends on {pending[0]}"],
                        )
                    )

    # ---- provider calls (the pinned 2.3.0 surface) --------------------------------------------

    def scope(self, check: str) -> dict[str, str]:
        return {"user_id": f"probe-{self.run}-{check.lower()}"}

    def fact(self, topic: str, field_name: str, value: str) -> str:
        return f"[topic=probe_{topic}][field={field_name}] {value}"

    def generate(
        self, bank: str, scope: dict[str, str], facts: list[str], **config: Any
    ) -> list[Any]:
        self.written.add((bank, scope["user_id"]))
        operation = self.memories.generate(
            name=bank,
            direct_memories_source={"direct_memories": [{"fact": f} for f in facts]},
            scope=scope,
            config={"wait_for_completion": True, **config},
        )
        if getattr(operation, "error", None):
            raise RuntimeError(f"GenerateMemories operation error: {operation.error}")
        if not getattr(operation, "done", False):
            raise Unavailable(
                "GenerateMemories operation not done after wait_for_completion"
            )
        response = getattr(operation, "response", None)
        return list(getattr(response, "generated_memories", None) or [])

    def get(self, name: str) -> Any:
        return self.memories.get(name=name)

    def in_scope(
        self, bank: str, scope: dict[str, str], page_size: int | None = None
    ) -> list[Any]:
        params = {"page_size": page_size} if page_size else {}
        items = self.memories.retrieve(
            name=bank, scope=scope, simple_retrieval_params=params
        )
        return [getattr(item, "memory", item) for item in items]

    def revisions(self, name: str) -> list[Any]:
        try:
            return list(self.memories.revisions.list(name=name))
        except Exception as exc:
            if is_not_found(exc):
                return []
            raise

    def revision_exists(self, revision_name: str) -> bool:
        try:
            self.memories.revisions.get(name=revision_name)
            return True
        except Exception as exc:
            if is_not_found(exc):
                return False
            raise

    def wait_gone(self, name: str, timeout: float, interval: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.get(name)
            except Exception as exc:
                if is_not_found(exc):
                    return True
                raise
            if time.monotonic() > deadline:
                return False
            time.sleep(interval)

    def created_names(self, items: list[Any]) -> list[str]:
        return [
            memory_name(i) for i in items if action(i) == "CREATED" and memory_name(i)
        ]

    def create_bank(
        self, purpose: str, ttl: int | None = None, kms_key: str | None = None
    ) -> Any:
        semantic: dict[str, Any] = {}
        try:
            base = self.client.memory_banks.get(name=self.args.bank)
            config = getattr(base, "managed_semantic_memory_config", None)
            if config is not None:
                semantic = config.model_dump(exclude_none=True)
        except Exception as exc:  # noqa: BLE001 - copying is best effort and reported
            self.info(purpose, f"--bank configuration not copied: {classify(exc)[1]}")
        if ttl is not None:
            seconds = f"{ttl}s"
            semantic["ttl_config"] = {
                "granular_ttl_config": {
                    "create_ttl": seconds,
                    "generate_created_ttl": seconds,
                    "generate_updated_ttl": seconds,
                }
            }
        config_args: dict[str, Any] = {
            "display_name": f"probe-{self.run}-{purpose.lower()}"
        }
        if kms_key:
            config_args["encryption_spec"] = {"kms_key_name": kms_key}
        bank = self.client.memory_banks.create(
            managed_semantic_memory_config=semantic or None, config=config_args
        )
        self.scratch_banks.append(bank.name)
        return bank

    # ---- checks -------------------------------------------------------------------------------

    def run_all(self) -> None:
        self.group(["L1", "L2", "L3", "L6"], self.check_write_path)
        self.group(["L5"], self.check_dedup)
        self.group(["L4"], self.check_revisions)
        self.group(["L8"], self.check_pagination)
        self.group(["L9"], self.check_read_after_write)
        self.group(["L7"], self.check_ttl)
        self.group(["L11"], self.check_cmek)

    def check_write_path(self) -> None:
        """L1, L2, L3 and L6 share two writes into one scope."""
        bank, scope = self.args.bank, self.scope("l1")
        first = [
            self.fact("pref", "brand", f"Acme Widgets {self.run}"),
            self.fact("pref", "size", "medium"),
        ]
        items1 = self.generate(bank, scope, first)
        stored = {name: self.get(name).fact for name in self.created_names(items1)}
        verbatim = sorted(stored.values()) == sorted(first)

        items2 = self.generate(bank, scope, [self.fact("pref", "size", "large")])
        # L3 reads straight after the operation completes, before anything else touches the scope.
        l3_checked, l3_problems, l3_notes = 0, [], []
        for item in items2:
            if action(item) not in ("CREATED", "UPDATED"):
                continue
            name, expected = memory_name(item), memory_fact(item)
            got = self.get(name).fact
            l3_checked += 1
            if expected is not None and got != expected:
                l3_problems.append(
                    f"{name}: get {got!r} != operation result {expected!r}"
                )
            if action(item) == "UPDATED" and name in stored and got == stored[name]:
                l3_problems.append(
                    f"{name}: get still returns the pre-update fact {got!r}"
                )
            if expected is None:
                l3_notes.append(
                    f"{name}: the operation result carries no fact; get succeeded"
                )

        touched = {memory_name(i): action(i) for i in items2}
        consolidated = any(
            act in ("UPDATED", "DELETED") and name in stored
            for name, act in touched.items()
        )
        if self.wanted("L1"):
            evidence = [
                f"first write: actions {[action(i) for i in items1]}",
                f"stored facts equal the input exactly (no extraction): {verbatim}",
                f"conflicting second write (size medium -> large): actions {touched}",
                f"consolidation acted on a first-write memory: {consolidated}",
                "consolidation is model-judged: FAIL here means not observed for this input",
            ]
            if not verbatim:
                evidence.append(
                    f"input {sorted(first)} -> stored {sorted(stored.values())}"
                )
            self.emit(
                Result(
                    "L1",
                    PASS if verbatim and consolidated else FAIL,
                    TITLES["L1"],
                    evidence,
                )
            )

        if self.wanted("L2"):
            all_items = items1 + items2
            bad = [
                (memory_name(i), action(i))
                for i in all_items
                if not memory_name(i) or action(i) not in ACTIONS
            ]
            evidence = [
                f"{len(all_items)} item(s) across both operations; malformed: {bad}"
            ]
            ok = bool(all_items) and not bad
            self.emit(Result("L2", PASS if ok else FAIL, TITLES["L2"], evidence))

        if self.wanted("L3"):
            if l3_checked == 0:
                self.emit(
                    Result(
                        "L3",
                        UNAVAILABLE,
                        TITLES["L3"],
                        ["the second write touched no memory"],
                    )
                )
            else:
                evidence = [f"read back {l3_checked} memory(ies) immediately"]
                evidence += l3_problems + l3_notes
                status = FAIL if l3_problems else PASS
                self.emit(Result("L3", status, TITLES["L3"], evidence))

        if self.wanted("L6"):
            if not consolidated:
                self.emit(
                    Result(
                        "L6",
                        UNAVAILABLE,
                        TITLES["L6"],
                        ["no consolidated memory to inspect (see L1)"],
                    )
                )
                return
            facts = [m.fact or "" for m in self.in_scope(bank, scope)]
            broken = [
                f for f in facts if not PREFIX.match(f) or f.count("[topic=") != 1
            ]
            evidence = [f"{len(facts)} memory(ies) in scope after consolidation"]
            evidence += [f"prefix lost or duplicated: {f!r}" for f in broken]
            self.emit(Result("L6", FAIL if broken else PASS, TITLES["L6"], evidence))

    def check_dedup(self) -> None:
        bank, scope = self.args.bank, self.scope("l5")
        marker = f"teal {self.run}"
        fact = self.fact("pref", "colour", marker)
        items1 = self.generate(bank, scope, [fact])
        items2 = self.generate(bank, scope, [fact])
        memories = self.in_scope(bank, scope)
        matching = [m for m in memories if marker in (m.fact or "")]
        created_again = [action(i) for i in items2].count("CREATED")
        evidence = [
            f"first submission: actions {[action(i) for i in items1]}",
            f"second, identical submission: actions {[action(i) for i in items2]}",
            f"memories in scope: {len(memories)}; holding the fact: {len(matching)}",
        ]
        ok = len(memories) == 1 and len(matching) == 1 and created_again == 0
        self.emit(Result("L5", PASS if ok else FAIL, TITLES["L5"], evidence))

    def check_revisions(self) -> None:
        bank, scope = self.args.bank, self.scope("l4")
        clean_marker = f"clean value {self.run}"
        sentinel = f"PROHIBITED-SENTINEL-{self.run}"
        names = self.created_names(
            self.generate(bank, scope, [self.fact("note", "note", clean_marker)])
        )
        if not names:
            raise Unavailable("the clean write created no memory")
        name = names[0]
        items2 = self.generate(bank, scope, [self.fact("note", "note", sentinel)])
        updated = [
            i for i in items2 if memory_name(i) == name and action(i) == "UPDATED"
        ]
        if not updated:
            raise Unavailable(
                "consolidation did not update the memory, so no revision was superseded: "
                f"actions {[(memory_name(i), action(i)) for i in items2]}"
            )

        revisions = self.revisions(name)
        bad = [r.name for r in revisions if sentinel in (r.fact or "")]
        clean = [r.name for r in revisions if clean_marker in (r.fact or "")]
        a_listable = len(revisions) >= 2 and bool(bad) and bool(clean)
        previous = getattr(updated[0], "previous_revision", None)
        target = (
            last_segment(previous)
            if previous
            else (last_segment(clean[0]) if clean else None)
        )
        evidence = [
            f"(a) revisions listed: {len(revisions)}; prohibited {len(bad)}, clean {len(clean)}"
        ]
        if target is None:
            raise Unavailable("no clean revision to roll back to")

        self.memories.rollback(
            name=name, target_revision_id=target, config={"wait_for_completion": True}
        )
        restored = self.get(name).fact or ""
        b_restored = clean_marker in restored and sentinel not in restored
        evidence.append(
            f"(b) rollback to {target}: current fact restored: {b_restored}"
        )

        listed_after = [
            r.name for r in self.revisions(name) if sentinel in (r.fact or "")
        ]
        retrievable = [r for r in bad if self.revision_exists(r)]
        c_purged = not listed_after and not retrievable
        evidence.append(
            "(c) prohibited revision after rollback: "
            f"listed {len(listed_after)}, retrievable {len(retrievable)} -> purged: {c_purged}"
        )

        self.memories.delete(name=name)
        gone = self.wait_gone(name, timeout=60)
        leftover = [r for r in bad + clean if self.revision_exists(r)] + [
            r.name for r in self.revisions(name)
        ]
        d_purged = gone and not leftover
        evidence.append(
            f"(d) after delete: memory gone {gone}; revisions still retrievable {len(leftover)}"
        )
        evidence.append(
            "decision map: (c) false -> DEC-3 delete-only; (d) false -> Stage 2 (C-05 (a))"
        )
        ok = a_listable and b_restored and c_purged and d_purged
        self.emit(Result("L4", PASS if ok else FAIL, TITLES["L4"], evidence))

        try:
            scope_e = self.scope("l4e")
            items = self.generate(
                bank,
                scope_e,
                [self.fact("note", "note", f"no revisions {self.run}")],
                disable_memory_revisions=True,
            )
            for created in self.created_names(items):
                self.info(
                    "L4",
                    "with disable_memory_revisions=True, revisions listed: "
                    f"{len(self.revisions(created))}",
                )
        except Exception as exc:  # noqa: BLE001 - an observation, reported either way
            self.info(
                "L4", f"disable_memory_revisions not observed: {classify(exc)[1]}"
            )

    def check_pagination(self) -> None:
        bank, scope = self.args.bank, self.scope("l8")
        facts = [
            self.fact("list", f"item_{i:02d}", f"value {i} {self.run}")
            for i in range(12)
        ]
        created = set(self.created_names(self.generate(bank, scope, facts)))
        page_size = 5
        if len(created) <= page_size:
            raise Unavailable(
                f"only {len(created)} memories created; fewer than two pages of {page_size}"
            )
        seen = {m.name for m in self.in_scope(bank, scope, page_size=page_size)}
        missing = created - seen
        evidence = [
            f"created {len(created)}; page_size {page_size}; returned {len(seen)}; "
            f"missing {len(missing)}"
        ]
        self.emit(Result("L8", FAIL if missing else PASS, TITLES["L8"], evidence))

    def check_read_after_write(self) -> None:
        bank, trials, ceiling = self.args.bank, self.args.l9_trials, 30.0
        latencies: list[float] = []
        timeouts = 0
        for k in range(trials):
            scope = self.scope(f"l9-{k}")
            items = self.generate(
                bank, scope, [self.fact("raw", "probe", f"trial {k} {self.run}")]
            )
            started = time.monotonic()
            names = set(self.created_names(items))
            if not names:
                raise Unavailable(f"trial {k}: the write created no memory")
            while True:
                if names <= {m.name for m in self.in_scope(bank, scope)}:
                    latencies.append(time.monotonic() - started)
                    break
                if time.monotonic() - started > ceiling:
                    timeouts += 1
                    break
                time.sleep(0.25)
        if not latencies:
            raise RuntimeError(f"no trial became visible within {ceiling:.0f} s")
        if len(latencies) >= 100:
            bound, label = percentile(latencies, 0.99), "p99"
        else:
            bound, label = (
                max(latencies),
                f"max of {len(latencies)} (p99 needs >= 100 trials)",
            )
        evidence = [
            f"trials {trials}; visible {len(latencies)}; not visible within {ceiling:.0f} s: "
            f"{timeouts}",
            f"p50 {statistics.median(latencies):.2f} s; p95 {percentile(latencies, 0.95):.2f} s; "
            f"max {max(latencies):.2f} s",
            f"bound used: {label} = {bound:.2f} s against N = {self.args.n_seconds} s",
        ]
        ok = timeouts == 0 and bound <= self.args.n_seconds
        self.emit(Result("L9", PASS if ok else FAIL, TITLES["L9"], evidence))

    def check_ttl(self) -> None:
        ttl = self.args.ttl_seconds
        self.info(
            "L7",
            f"SDK {PINNED_SDK}: GenerateMemoriesConfig has no per-request ttl and Memories has no "
            "update method, so this check uses the bank-level ttl_config.granular_ttl_config",
        )
        if self.ttl_bank is None:
            if not self.args.create_scratch_banks:
                raise Unavailable(
                    "no TTL bank: pass --ttl-bank or --create-scratch-banks"
                )
            self.ttl_bank = self.create_bank("L7", ttl=ttl).name
        bank, scope = self.ttl_bank, self.scope("l7")

        names = self.created_names(
            self.generate(bank, scope, [self.fact("pref", "size", "medium")])
        )
        if not names:
            raise Unavailable("the first write created no memory")
        name = names[0]
        first = self.get(name)
        expire1, created_at = (
            as_datetime(first.expire_time),
            as_datetime(first.create_time),
        )
        applied: bool | None = None
        if expire1 is not None and created_at is not None:
            applied = abs((expire1 - created_at).total_seconds() - ttl) <= 60
        elif expire1 is None:
            applied = False
        evidence = [
            f"(a) expire_time on a generated memory: {expire1}; matches {ttl} s: {applied}"
        ]

        time.sleep(min(30, max(ttl // 4, 5)))  # long enough to tell "reset" from "kept"
        items2 = self.generate(bank, scope, [self.fact("pref", "size", "large")])
        survives: bool | None = None
        expire2: dt.datetime | None = None
        if any(memory_name(i) == name and action(i) == "UPDATED" for i in items2):
            expire2 = as_datetime(self.get(name).expire_time)
            if expire2 is None:
                outcome, survives = "dropped", False
            elif expire1 is not None and abs((expire2 - expire1).total_seconds()) < 5:
                outcome, survives = "kept", True
            elif expire1 is not None and expire2 > expire1:
                outcome, survives = "reset", True
            else:
                outcome, survives = "shortened", True
            evidence.append(f"(b) after a consolidation update the TTL was {outcome}")
        else:
            evidence.append(
                "(b) not observable: consolidation did not update the memory "
                f"(actions {[(memory_name(i), action(i)) for i in items2]})"
            )

        target = expire2 or expire1
        expired: bool | None = None
        if target is None:
            expired = False
            evidence.append("(c) no expire_time, so no expiry to observe")
        else:
            needed = (target - dt.datetime.now(dt.timezone.utc)).total_seconds() + 120
            if needed > self.args.l7_wait:
                evidence.append(
                    f"(c) not waited: needs {needed:.0f} s, --l7-wait {self.args.l7_wait}"
                )
            else:
                expired = self.wait_gone(name, timeout=needed, interval=15)
                evidence.append(
                    f"(c) memory gone within 120 s of expire_time: {expired}"
                )

        verdicts = [applied, survives, expired]
        if False in verdicts:
            status = FAIL
        elif None in verdicts:
            status = UNAVAILABLE
        else:
            status = PASS
        self.emit(Result("L7", status, TITLES["L7"], evidence))

        try:
            self.written.add((bank, self.scope("l7c")["user_id"]))
            self.memories.create(
                name=bank,
                fact=self.fact("pref", "probe", f"create path {self.run}"),
                scope=self.scope("l7c"),
                config={"ttl": f"{ttl}s", "wait_for_completion": True},
            )
            made = self.in_scope(bank, self.scope("l7c"))
            expiry = [str(as_datetime(m.expire_time)) for m in made]
            self.info(
                "L7",
                f"create path (not the design's write path) with ttl: expire_time {expiry}",
            )
        except Exception as exc:  # noqa: BLE001 - an observation, reported either way
            self.info("L7", f"create path with ttl not observed: {classify(exc)[1]}")

    def check_cmek(self) -> None:
        key = self.args.kms_key
        if not key:
            raise Unavailable("no --kms-key")
        if self.args.cmek_bank:
            bank = self.client.memory_banks.get(name=self.args.cmek_bank)
            source = "--cmek-bank"
        elif self.args.create_scratch_banks:
            try:
                created = self.create_bank("L11", kms_key=key)
            except Exception as exc:
                status, message = classify(exc)
                if status == FAIL:
                    self.emit(
                        Result(
                            "L11",
                            FAIL,
                            TITLES["L11"],
                            [
                                f"creation with encryption_spec rejected (counts as no): {message}"
                            ],
                        )
                    )
                    return
                raise
            bank = self.client.memory_banks.get(name=created.name)
            source = "a scratch bank created with the key"
        else:
            raise Unavailable("pass --create-scratch-banks or --cmek-bank")
        reported = getattr(getattr(bank, "encryption_spec", None), "kms_key_name", None)
        if reported == key:
            status, verdict = PASS, "reported key equals --kms-key"
        elif reported is None:
            status, verdict = (
                FAIL,
                "no encryption key reported: the field was ignored (counts as no)",
            )
        else:
            status, verdict = FAIL, f"a different key is reported: {reported}"
        self.emit(
            Result("L11", status, TITLES["L11"], [f"read back {source}: {verdict}"])
        )

    # ---- cleanup ------------------------------------------------------------------------------

    def cleanup(self) -> None:
        if self.args.keep:
            print(
                "\n--keep: nothing deleted. Scopes:", sorted(u for _, u in self.written)
            )
            print("Scratch banks:", [redact(b) for b in self.scratch_banks])
            return
        for bank, user_id in sorted(self.written):
            if bank in self.scratch_banks:
                continue
            try:
                for memory in self.in_scope(bank, {"user_id": user_id}):
                    self.memories.delete(name=memory.name)
            except Exception as exc:  # noqa: BLE001 - cleanup reports and carries on
                print(f"cleanup: scope {user_id} not fully deleted: {classify(exc)[1]}")
        for bank in self.scratch_banks:
            try:
                self.client.memory_banks.delete(name=bank, force=True)
            except Exception as exc:  # noqa: BLE001 - cleanup reports and carries on
                print(
                    f"cleanup: scratch bank {redact(bank)} not deleted: {classify(exc)[1]}"
                )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument(
        "--bank", required=True, help="bank resource name for L1-L6, L8, L9"
    )
    parser.add_argument("--create-scratch-banks", action="store_true")
    parser.add_argument(
        "--ttl-bank", help="a bank with generate TTLs set to --ttl-seconds (L7)"
    )
    parser.add_argument("--cmek-bank", help="a bank created with --kms-key (L11)")
    parser.add_argument("--kms-key", help="Cloud KMS key resource name (L11)")
    parser.add_argument("--ttl-seconds", type=int, default=300)
    parser.add_argument(
        "--l7-wait",
        type=int,
        default=600,
        help="max seconds to wait for expiry; 0 skips (c)",
    )
    parser.add_argument("--l9-trials", type=int, default=20)
    parser.add_argument("--n-seconds", type=float, default=10.0, help="AC13 bound N")
    parser.add_argument(
        "--only", default=",".join(TIER1), help="comma-separated, e.g. L1,L5"
    )
    parser.add_argument(
        "--keep", action="store_true", help="do not delete what the probe wrote"
    )
    parser.add_argument("--json", help="also write results to this file")
    args = parser.parse_args(argv)
    args.only = [c.strip().upper() for c in args.only.split(",") if c.strip()]
    unknown = [c for c in args.only if c not in TIER1]
    if unknown:
        parser.error(f"not Tier 1 checks: {unknown}. Tier 1 is {', '.join(TIER1)}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        sdk = importlib.metadata.version("google-cloud-aiplatform")
    except importlib.metadata.PackageNotFoundError:
        sdk = "not installed"
    print(f"Tier 1 probe | {started} | Python {platform.python_version()} | SDK {sdk}")
    if sdk != PINNED_SDK:
        print(
            f"WARNING: pinned SDK is {PINNED_SDK}; results from {sdk} do not settle DEC-11"
        )

    def unavailable_all(reason: str) -> int:
        for check in args.only:
            print(
                f"{check:<4} {UNAVAILABLE:<11} {TITLES[check]}\n     - {redact(reason)}"
            )
        return 2

    try:
        import agentplatform  # noqa: PLC0415 - imported here so a missing SDK is reported, not raised
    except ImportError as exc:
        return unavailable_all(f"agentplatform not importable: {exc}")
    try:
        client = agentplatform.Client(project=args.project, location=args.location)
    except Exception as exc:  # noqa: BLE001 - reported as UNAVAILABLE for every check
        return unavailable_all(f"client not created: {classify(exc)[1]}")

    probe = Probe(args, client)
    print(f"run {probe.run}\n")
    try:
        probe.run_all()
    finally:
        probe.cleanup()

    verdicts = [r for r in probe.results if r.status != INFO]
    counts = {
        s: sum(r.status == s for r in verdicts) for s in (PASS, FAIL, UNAVAILABLE)
    }
    print(
        f"\n{counts[PASS]} passed, {counts[FAIL]} failed, {counts[UNAVAILABLE]} unavailable"
    )
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "run": probe.run,
                    "started": started,
                    "python": platform.python_version(),
                    "sdk": sdk,
                    "location": args.location,
                    "results": [asdict(r) for r in probe.results],
                },
                handle,
                indent=2,
            )
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
