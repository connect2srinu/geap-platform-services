# GEAP Platform Services

This repository **publishes reusable patterns**. Domain teams adopt a pattern, own and customize the
code, build their own image, and deploy it themselves to Cloud Run in the platform-owned GCP project.
We do not operate their runtimes.

Never put a business domain's rules (Customer, Inventory, …) into reusable pattern code. Domain
behaviour arrives through configuration and declared extension points.

## The process — two documents, two gates

```
design/NNN-slug/intent.md    what and why          → human approves
design/NNN-slug/design.md    how                   → human approves
                             → implement → PR      → human approves → merge
```

That is the whole process. There are no other artifacts.

- **Do not write implementation code until `design.md` says `status: approved`.**
- Only a human sets `status: approved`. Never infer approval from a commit message or from silence.
- Fix incidental defects **in the same branch**. Don't create a second branch for a typo.
- One feature, one branch, one PR: `design/NNN-slug` for all three.

## The rules while you work

1. **Read `standards/engineering.md` before writing code**, and `standards/security.md` before
   anything touching auth, data, secrets or IAM.
2. **Follow the approved design.** If something forces a real change to it, stop and say so — don't
   improvise around it.
3. **Verify provider assumptions with a throwaway script before designing around them.** Reading the
   installed SDK beats reading the documentation. This has caught three contract-level defects.
4. **Tests ship with the code**, in the same commit. A security rule is only real if a test fails
   when you remove it.
5. **Never claim a check passed without its output.** Report passed / failed / **unavailable**
   separately — unavailable is not a pass.
6. **Don't touch unrelated components.** Report what you notice instead of fixing it.
7. **Ask before** merging, publishing, pushing an image, deleting anything, or `terraform apply`.
   This repository applies no infrastructure.

## Skills

| Skill | Use |
|---|---|
| `feature-start` | Begin a feature — writes `intent.md`, then `design.md` after you approve the intent |
| `feature-review` | Implementation done — checks it against the design, runs the checks, preps the PR |
| `pattern-release` | Prepare a version for release. Never publishes. |

## Validation

```bash
make verify
```
