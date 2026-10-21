# Requesting a role — for agent teams

Template for an agent team requesting access to this domain's service.

The **domain** grants roles. The platform team does not broker this relationship and cannot grant
access on the domain's behalf.

## Request

| Field | Value |
|---|---|
| Agent name | |
| Owning team | |
| Service account identity | |
| Environment | dev / staging / production |
| Role requested | `<reader-agent-role>` / `<writer-agent-role>` |
| Operations needed | read · list · write · correct · forget |
| Purpose | What the agent does with the memory |
| Data categories | Which categories it needs |
| Expected volume | Requests per minute, peak and steady state |

Volume matters: this domain has an allocated share of a **shared project quota**, and a new
high-volume consumer may require the allocation to be renegotiated with the platform team before the
role is granted.

## What the domain checks

- Is the purpose consistent with the categories requested?
- Is read-only sufficient? Write access is granted only where writing is the agent's job.
- Does the expected volume fit the current quota allocation?
- Is the identity a workload identity rather than a key?

## After approval

The domain adds the binding to `config/domain-config.yaml` and deploys. The agent team receives the
endpoint and the API documentation in [`agent-api.md`](agent-api.md).

Roles are reviewed periodically. An agent that stops using its role has it revoked.
