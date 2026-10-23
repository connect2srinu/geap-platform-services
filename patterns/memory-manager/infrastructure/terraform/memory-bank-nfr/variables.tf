variable "project_id" {
  description = "The platform-owned project. Every domain's bank and service lives here."
  type        = string
}

variable "region" {
  description = "Region. Memory Bank quota is per project PER REGION and is shared across every domain here."
  type        = string
  default     = "us-central1"
}

variable "domain_name" {
  description = "The domain this bank belongs to. One bank per domain."
  type        = string
}

variable "memory_manager_service_account" {
  description = <<-EOT
    The domain's Memory Manager service account, from its own Terraform output.

    This is the whole point of the module: the bank is reachable by this identity and nothing else.
    An agent is never granted direct access, because an agent with direct access bypasses every
    policy, classification and audit control the domain configured.
  EOT
  type        = string
}

variable "retention_days" {
  description = <<-EOT
    ONE retention period for the whole domain.

    Per-topic retention is not possible: TTL is a bank-level setting and each domain has one bank
    (verified against the provider on 2026-10-22). A domain with mixed data must choose its
    shortest acceptable period. Per-topic retention is deferred to v0.2.0.
  EOT
  type        = number

  validation {
    condition     = var.retention_days >= 1 && var.retention_days <= 3650
    error_message = "retention_days must be between 1 and 3650."
  }
}

variable "audit_sink_dataset" {
  description = "BigQuery dataset for the central audit sink. A domain cannot suppress this; it is configured outside their application."
  type        = string
}

variable "quota_alert_notification_channels" {
  description = "Notification channels for quota and throttling alerts."
  type        = list(string)
  default     = []
}

variable "max_writes_per_minute" {
  description = "This domain's agreed share of the shared project quota. Declared here so the alert threshold and the domain's configured budget come from one place."
  type        = number
}
