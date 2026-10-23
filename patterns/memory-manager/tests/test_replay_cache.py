"""The replay cache behind the Idempotency-Key contract.

The contract promised two behaviours and the service implemented neither; a post-deployment smoke
test found it. These tests cover the mechanism. The case that matters most for safety is
`TestScopeIsPartOfIdentity`: a cache keyed on the client's chosen string alone is a way to hand
one end user another's memory id.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PATTERN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PATTERN / "src"))

from memory_manager.api.replay import (  # noqa: E402
    KeyReused,
    ReplayCache,
    fingerprint,
)

SCOPE_A = (("organization_id", "example-domain"), ("user_id", "a" * 32))
SCOPE_B = (("organization_id", "example-domain"), ("user_id", "b" * 32))
BODY = {"facts": [{"topic": "preferred_brands", "field": "brand", "value": "Horizon"}]}


def fp(
    caller: str = "writer-agent", scope: tuple = SCOPE_A, body: object = BODY
) -> str:
    return fingerprint(caller, scope, body)


class TestTheContract:
    def test_an_unseen_key_is_a_miss(self) -> None:
        assert ReplayCache().lookup("key-0000001", fp()) is None

    def test_the_same_key_and_payload_returns_the_recorded_response(self) -> None:
        cache = ReplayCache()
        response = {"outcome": "written", "stored": 1}
        cache.record("key-0000001", fp(), response)
        assert cache.lookup("key-0000001", fp()) == response

    def test_the_same_key_with_a_different_payload_raises(self) -> None:
        """This is what becomes 422 IDEMPOTENCY_KEY_REUSED."""
        cache = ReplayCache()
        cache.record("key-0000001", fp(), {"outcome": "written"})
        with pytest.raises(KeyReused):
            cache.lookup("key-0000001", fp(body={"facts": [{"value": "Other"}]}))

    def test_different_keys_with_the_same_payload_are_independent(self) -> None:
        """The key is the identity of a write, not the body."""
        cache = ReplayCache()
        cache.record("key-0000001", fp(), {"outcome": "written"})
        assert cache.lookup("key-0000002", fp()) is None

    def test_a_reused_key_raises_rather_than_reporting_a_miss(self) -> None:
        """A sentinel would let a caller treat reuse as a miss and write anyway."""
        cache = ReplayCache()
        cache.record("key-0000001", fp(), {"outcome": "written"})
        try:
            cache.lookup("key-0000001", fp(body={"different": True}))
        except KeyReused:
            return
        pytest.fail("a reused key must raise, never return None")


class TestScopeIsPartOfIdentity:
    """Security rule S-8. The worst thing this cache could do is a cross-scope read."""

    def test_two_end_users_sharing_a_key_do_not_see_each_others_response(self) -> None:
        cache = ReplayCache()
        cache.record("shared-key-1", fp(scope=SCOPE_A), {"memoryId": "belongs-to-a"})
        with pytest.raises(KeyReused):
            cache.lookup("shared-key-1", fp(scope=SCOPE_B))

    def test_two_callers_sharing_a_key_do_not_see_each_others_response(self) -> None:
        cache = ReplayCache()
        cache.record("shared-key-1", fp(caller="writer-agent"), {"memoryId": "one"})
        with pytest.raises(KeyReused):
            cache.lookup("shared-key-1", fp(caller="other-agent"))

    def test_the_fingerprint_changes_with_caller_scope_and_body(self) -> None:
        base = fp()
        assert fp(caller="other-agent") != base
        assert fp(scope=SCOPE_B) != base
        assert fp(body={"facts": []}) != base

    def test_the_fingerprint_is_stable_across_key_order(self) -> None:
        """A client reordering JSON keys is the same request, and must replay as one."""
        assert fp(body={"a": 1, "b": 2}) == fp(body={"b": 2, "a": 1})

    def test_the_fingerprint_carries_no_payload(self) -> None:
        """It is stored and may be logged as a reason; it must be a digest, not content."""
        value = "Prefers the organic brand Horizon"
        digest = fp(body={"fact": value})
        assert value not in digest
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


class TestBounds:
    def test_an_entry_expires(self) -> None:
        cache = ReplayCache(retention_seconds=1)
        cache.record("key-0000001", fp(), {"outcome": "written"})
        assert cache.lookup("key-0000001", fp()) is not None
        time.sleep(1.1)
        assert cache.lookup("key-0000001", fp()) is None

    def test_an_expired_key_can_be_reused_with_a_different_payload(self) -> None:
        """Once forgotten, the key is simply unknown — not permanently poisoned."""
        cache = ReplayCache(retention_seconds=1)
        cache.record("key-0000001", fp(), {"outcome": "written"})
        time.sleep(1.1)
        assert cache.lookup("key-0000001", fp(body={"other": True})) is None

    def test_a_flood_of_unique_keys_cannot_grow_without_limit(self) -> None:
        """Expiry alone does not bound memory; a burst arrives faster than anything ages out."""
        cache = ReplayCache(max_entries=50)
        for i in range(500):
            cache.record(f"key-{i:07d}", fp(body={"n": i}), {"outcome": "written"})
        assert len(cache) == 50

    def test_eviction_drops_the_oldest_first(self) -> None:
        cache = ReplayCache(max_entries=2)
        for name in ("first", "second", "third"):
            cache.record(name, fp(body={"n": name}), {"outcome": "written"})
        assert cache.lookup("first", fp(body={"n": "first"})) is None
        assert cache.lookup("third", fp(body={"n": "third"})) is not None

    def test_a_replayed_key_is_kept_over_an_idle_one(self) -> None:
        """A key being retried is the one most likely to be retried again."""
        cache = ReplayCache(max_entries=2)
        cache.record("busy", fp(body={"n": 1}), {"outcome": "written"})
        cache.record("idle", fp(body={"n": 2}), {"outcome": "written"})
        cache.lookup("busy", fp(body={"n": 1}))
        cache.record("new", fp(body={"n": 3}), {"outcome": "written"})
        assert cache.lookup("busy", fp(body={"n": 1})) is not None
        assert cache.lookup("idle", fp(body={"n": 2})) is None

    @pytest.mark.parametrize(
        ("retention", "entries"), [(0, 10), (-1, 10), (10, 0), (10, -1)]
    )
    def test_a_nonsensical_size_is_refused(self, retention: int, entries: int) -> None:
        with pytest.raises(ValueError):
            ReplayCache(retention_seconds=retention, max_entries=entries)


class TestConcurrency:
    def test_concurrent_writers_do_not_corrupt_the_cache(self) -> None:
        """Cloud Run serves requests concurrently in one instance."""
        import threading

        cache = ReplayCache(max_entries=1000)
        errors: list[Exception] = []

        def worker(start: int) -> None:
            try:
                for i in range(start, start + 100):
                    key = f"key-{i:07d}"
                    cache.record(key, fp(body={"n": i}), {"outcome": "written", "n": i})
                    assert cache.lookup(key, fp(body={"n": i})) == {
                        "outcome": "written",
                        "n": i,
                    }
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n * 100,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        assert len(cache) == 800
