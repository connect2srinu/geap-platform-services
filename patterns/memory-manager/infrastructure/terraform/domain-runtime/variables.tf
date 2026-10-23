variable "project_id" {
  description = "The platform-owned GCP project that hosts every domain's services and memory banks."
  type        = string
}

variable "region" {
  description = "Deployment region. Memory Bank quota is enforced per project PER REGION, and that quota is shared across every domain in this project."
  type        = string
  default     = "us-central1"
}

variable "domain_name" {
  description = "Neutral domain identifier, used as a resource name prefix so several domains coexist in one project."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,24}$", var.domain_name))
    error_message = "domain_name must be lowercase kebab-case, 3-25 characters."
  }
}

variable "container_image" {
  description = "The DOMAIN-OWNED image, by digest. A floating tag is not a reproducible deployment."
  type        = string

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be pinned by digest (…@sha256:…), not by tag."
  }
}

variable "memory_bank_id" {
  description = "The PLATFORM-PROVISIONED memory bank for this domain, as a full resource name (projects/<number>/locations/<region>/memoryBanks/<id>). Consumed as an input; this module never creates it."
  type        = string
}

variable "max_instances" {
  description = <<-EOT
    Maximum Cloud Run instances, and the divisor for this domain's write budget.

    One variable sets both the service's instance ceiling and the container's MAX_INSTANCES, so
    the per-instance budget cannot drift from the real instance count. Raising the ceiling without
    raising the budget is the drift this prevents.
  EOT
  type        = number
  default     = 4

  validation {
    condition     = var.max_instances >= 1 && var.max_instances <= 100
    error_message = "max_instances must be between 1 and 100."
  }
}

variable "max_writes_per_minute" {
  description = "This domain's agreed share of the SHARED project Memory Bank quota. Divided by max_instances at startup. The service refuses to start without it."
  type        = number

  validation {
    condition     = var.max_writes_per_minute >= 1 && var.max_writes_per_minute <= 10000
    error_message = "max_writes_per_minute must be between 1 and 10000."
  }
}

variable "identity_issuer" {
  description = "The issuer whose end-user tokens this domain accepts."
  type        = string
}

variable "identity_jwks_uri" {
  description = "The issuer's JWKS endpoint."
  type        = string
}

variable "identity_audience" {
  description = "The audience claim this service requires."
  type        = string
  default     = "memory-manager"
}

variable "subject_hmac_secret_id" {
  description = "Secret Manager secret holding the HMAC key that pseudonymises end-user subjects. Never the key itself."
  type        = string
}

variable "deletion_protection" {
  description = "Protect the service from accidental destruction."
  type        = bool
  default     = true
}

variable "agent_service_accounts" {
  description = "Agent service accounts granted run.invoker, one per onboarded agent team. Never allUsers or allAuthenticatedUsers."
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.agent_service_accounts, "allUsers") && !contains(var.agent_service_accounts, "allAuthenticatedUsers")
    error_message = "allUsers and allAuthenticatedUsers are not acceptable invokers."
  }
}
