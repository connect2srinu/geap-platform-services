# Upgrade guide

> No released versions yet. `spec.upgrade.from` is empty, which means **no supported upgrade path
> exists** — there is nothing to upgrade from.

Once versions are published, each entry here states: the source version, the breaking changes, the
configuration and extension changes, the security changes, the required regression tests, and the
rollback procedure.

Plan an upgrade by diffing the two tags' contracts and changelog. A version
not listed in `spec.upgrade.from` has no supported path, and the skill will say so rather than
improvise one.
