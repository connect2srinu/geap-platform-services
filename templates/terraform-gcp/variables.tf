variable "project_id" {
  description = "The platform-owned GCP project that hosts every domain's services and memory banks."
  type        = string
}

variable "region" {
  description = "Deployment region. Memory Bank quota is enforced per project PER REGION."
  type        = string
  default     = "us-central1"
}

variable "domain_name" {
  description = "Neutral domain identifier, e.g. 'example-domain'. Used as a resource name prefix so that several domains coexist in one project."
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
  description = "The PLATFORM-PROVISIONED memory bank for this domain. Consumed as an input; this module never creates it."
  type        = string
}

variable "audit_sink_topic" {
  description = "The PLATFORM-OWNED audit sink topic. Consumed as an input; the domain cannot suppress it."
  type        = string
}

variable "max_writes_per_minute" {
  description = "This domain's allocated share of the shared project Memory Bank quota. Enforced by the worker's rate governor. See standards/architecture.md on shared quota."
  type        = number

  validation {
    condition     = var.max_writes_per_minute > 0 && var.max_writes_per_minute <= 10000
    error_message = "max_writes_per_minute must be between 1 and 10000."
  }
}

variable "min_instances" {
  description = "Minimum Cloud Run instances. Set above zero to avoid cold starts on the read path."
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum Cloud Run instances. Bounds the blast radius of a traffic spike against shared quota."
  type        = number
  default     = 10
}

variable "ingress" {
  description = "Cloud Run ingress. Internal by default (control C-10); public requires an approved exception."
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  validation {
    condition     = contains(["INGRESS_TRAFFIC_INTERNAL_ONLY", "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER", "INGRESS_TRAFFIC_ALL"], var.ingress)
    error_message = "ingress must be one of the three supported Cloud Run values."
  }
}

variable "deletion_protection" {
  description = "Protect the service from accidental destruction."
  type        = bool
  default     = true
}
