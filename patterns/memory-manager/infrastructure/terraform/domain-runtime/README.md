# `domain-runtime`

Empty. The Memory Manager design has not been approved, so no Terraform exists yet.

## Ownership — domain

Reference Terraform the **domain** owns and applies: the Cloud Run API and worker services, their
per-component service accounts, the Pub/Sub retry queue and dead-letter topic, and secret access
bindings.

A working starting point already exists at `templates/terraform-gcp/`, which validates today. This
directory will hold the pattern-specific version once the design is approved.
