# `src/` is a build root, not a package

Do **not** put `__init__.py` here. Create exactly one package beneath it, named after the pattern
with underscores — `src/<pattern_name>/` — and rename `pattern_package/` to that.

Two patterns that both ship a top-level package called `src` cannot be installed side by side: in
`site-packages` whichever lands second silently wins, and `pip uninstall` of one takes files the
other needs. A domain adopting two patterns would hit this immediately.

`scripts/validate_pattern_manifest.py` enforces the layout, so a pattern that gets it wrong fails
`make verify` rather than failing in a domain's container months later.

The pattern's own `config.schema.json` lives inside the package, because it is the pattern's
artifact and has to travel in the wheel. `config/` at the pattern root holds only the example
domain configuration.
