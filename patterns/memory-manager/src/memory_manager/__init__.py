"""Memory Manager — reference implementation.

Layering, per `standards/engineering.md`:

    api/        transport: validation, authn, correlation, error mapping
    policy/     authorization and classification decisions
    providers/  the managed-service boundary
    worker/     post-write verification and remediation

Dependencies point downward only.
"""
