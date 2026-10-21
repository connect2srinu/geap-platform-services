## What and why

<!-- One paragraph. Link the design folder: design/NNN-slug/ -->

**Design folder:** `design/NNN-slug/`
**Track:** full / light

## SDLC gates

<!-- A checked box means the artifact's front matter says `status: approved` with a named human
     approver. Checking a box you have not verified defeats the whole process. -->

- [ ] Gate A — `intent.md` approved
- [ ] Gate B — `design.md` approved
- [ ] Gate C — `controls-check.md` approved
- [ ] Gate D — `tasks.md` approved
- [ ] Light track — `change.md` present and the four light-track conditions hold

## Design conformance

<!-- Does the implementation match the approved design? List every deviation with who approved it.
     "No deviations" is a valid answer; silence is not. -->

## Verification

<!-- Report each check with its REAL status. "unavailable" is not "passed". -->

| Check | Command | Result |
|---|---|---|
| Design artifacts | `python3 scripts/validate_design_artifacts.py` | |
| Pattern manifest | `python3 scripts/validate_pattern_manifest.py` | |
| Boundary checks | `python3 scripts/check_platform_domain_boundary.py` | |
| Lint | `make lint` | |
| Tests | `make test` | |
| Terraform | `make terraform-validate` | |
| Conformance | `python3 scripts/run_conformance.py --pattern <name>` | |

Live managed-service verification: performed / **not performed**

## Security

- [ ] Controls assessment is current for what was actually implemented
- [ ] No new log, trace attribute or error response carries memory content, PII or secrets
- [ ] Any new permission is least privilege; no primitive roles
- [ ] Any new dependency is pinned and scanned
- [ ] No mandatory control can be disabled by configuration

## Compatibility

- [ ] No breaking contract change, **or** it is covered by an approved ADR and a major version bump
- [ ] `CHANGELOG.md` updated
- [ ] Upgrade guidance updated

## Platform / domain boundary

- [ ] No business-domain logic added to `patterns/*/src/`
- [ ] No real enterprise identifiers in code, manifests, templates or examples
- [ ] Domain behaviour arrives through configuration or a declared extension point

## Risks and follow-ups

<!-- Unresolved risks, deferred work, anything a reviewer should look at closely. -->

## Reviewer notes

<!-- Where to look first. -->

---

<!-- Human review (Gate E) is required and is not satisfied by any automated check in this
     repository. Merge (Gate F) requires explicit authorization. -->
