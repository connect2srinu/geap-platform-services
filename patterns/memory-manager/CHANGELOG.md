# Changelog

All notable changes to this pattern are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every entry states what changed, whether it is **breaking**, the migration steps, and any
security-relevant change explicitly.

## [Unreleased]

### Added

- Pattern manifest, directory structure and declared contract surface. No implementation —
  the design is not yet approved and the pattern status is `proposed`.

### Security

- Declared non-overridable controls: `C-01`, `C-02`, `C-05`, `C-06`, `C-07`, `C-08`, `C-11`, `C-16`.
- Both required extension points default to `deny-all` with `failureMode: deny`, so that an
  unconfigured deployment stores nothing.
