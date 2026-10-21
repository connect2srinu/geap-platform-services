# `memory-bank-nfr`

Empty. The Memory Manager design has not been approved, so no Terraform exists yet.

## Ownership — platform

This module is **platform-owned** and provisions, per ADR-0003:

- the per-domain memory bank, in the platform-owned GCP project;
- the IAM binding granting access to the domain's Memory Manager service account **only** —
  never to an agent directly — with IAM Conditions on scope (control `C-16`);
- the central audit sink the domain cannot suppress (control `C-07`);
- quota alerting and per-domain attribution (controls `C-18`, `C-19`).

**This is the only control that survives a domain forking the pattern source.** A domain's Terraform
consumes these as inputs and must not create them. See `standards/pattern-contract.md`.
