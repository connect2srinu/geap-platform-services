# Domain-owned reference deployment.
#
# OWNERSHIP BOUNDARY - read this before editing.
#
#   DOMAIN-OWNED (this module): the Cloud Run service, its service account, the secret access
#   binding, and this domain's own alerting.
#
#   PLATFORM-OWNED (../memory-bank-nfr): the memory bank, the IAM binding that grants access to
#   it, the central audit sink, and quota alerting. Consumed here as inputs.
#
# That split is deliberate: it is the only control that survives a domain forking the pattern
# source. See standards/security.md.
#
# There is no Pub/Sub and no worker. v0.1.0 writes synchronously; async returns in v0.2.0.

locals {
  name = "${var.domain_name}-memory-manager"

  # The per-instance write budget. Each instance enforces max_writes_per_minute / max_instances,
  # so the domain's total stays within its agreed share however many instances are running.
  env = {
    DOMAIN_NAME           = var.domain_name
    GOOGLE_CLOUD_PROJECT  = var.project_id
    GOOGLE_CLOUD_LOCATION = var.region
    MEMORY_BANK_ID        = var.memory_bank_id
    MAX_WRITES_PER_MINUTE = tostring(var.max_writes_per_minute)
    MAX_INSTANCES         = tostring(var.max_instances)
    IDENTITY_ISSUER       = var.identity_issuer
    IDENTITY_JWKS_URI     = var.identity_jwks_uri
    IDENTITY_AUDIENCE     = var.identity_audience
    ENVIRONMENT           = "production"
  }
}

# One service account for the one component. No primitive roles anywhere (S-6).
resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = local.name
  display_name = "${var.domain_name} Memory Manager"
  description  = "Serves the governed memory tool API. The platform grants this identity, and only this identity, access to the domain's memory bank."
}

# A custom role rather than a predefined one: the predefined Vertex AI roles carry far more than
# this service needs, and least privilege is a control, not a preference (S-6).
resource "google_project_iam_custom_role" "memory_manager" {
  project     = var.project_id
  role_id     = replace("${local.name}_role", "-", "_")
  title       = "${var.domain_name} Memory Manager"
  description = "The narrowest set of permissions the Memory Manager needs. Memory bank access itself is granted separately, by platform-owned Terraform."

  permissions = [
    "logging.logEntries.create",
    "monitoring.timeSeries.create",
    "cloudtrace.traces.patch",
  ]
}

resource "google_project_iam_member" "api" {
  project = var.project_id
  role    = google_project_iam_custom_role.memory_manager.id
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Exactly one secret, read by exactly one identity.
resource "google_secret_manager_secret_iam_member" "subject_hmac" {
  project   = var.project_id
  secret_id = var.subject_hmac_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_cloud_run_v2_service" "api" {
  project             = var.project_id
  location            = var.region
  name                = local.name
  deletion_protection = var.deletion_protection

  # Internal only. An agent reaches this over the private path; nothing is exposed publicly.
  # If an agent runtime cannot reach an internal-only service, that is live check L12 and the
  # fallback is a recorded exception, not a quiet switch to public ingress.
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.api.email
    timeout         = "60s"

    # Session affinity gives the per-instance idempotency cache a better hit rate. It is a
    # mitigation, not a guarantee: cross-instance idempotency rests on provider consolidation.
    session_affinity = true

    scaling {
      min_instance_count = 1
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle = true
      }

      dynamic "env" {
        for_each = local.env
        content {
          name  = env.key
          value = env.value
        }
      }

      # The HMAC key arrives as a secret reference, never as a variable value (S-5).
      env {
        name = "SUBJECT_HMAC_KEY"
        value_source {
          secret_key_ref {
            secret  = var.subject_hmac_secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        initial_delay_seconds = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/healthz"
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.subject_hmac]
}

# No allUsers or allAuthenticatedUsers invoker. Agent service accounts are granted invoke
# individually, by the domain, as each agent team is onboarded.
resource "google_cloud_run_v2_service_iam_member" "agents" {
  for_each = toset(var.agent_service_accounts)

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value}"
}
