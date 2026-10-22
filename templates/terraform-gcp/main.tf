# Domain-owned reference deployment on Cloud Run.
#
# OWNERSHIP BOUNDARY — read this before editing.
#
#   DOMAIN-OWNED (this module): the Cloud Run service, its service account, and the domain's
#   own alerting.
#
#   No queue and no worker: v0.1.0 writes synchronously (design/001-memory-manager/design.md,
#   D1). When asynchronous writes return in v0.2.0, the queue must be created with a
#   customer-managed key (proposed control C-20, design/006-*).
#
#   PLATFORM-OWNED (NOT this module): the memory bank itself, the IAM binding that grants
#   access to it, the central audit sink, and quota alerting. Those are provisioned by the
#   platform's own Terraform and are consumed here as inputs. This is deliberate: it is the
#   one control that survives a domain forking the pattern source.
#   See standards/pattern-contract.md.

locals {
  name = "${var.domain_name}-memory-manager"

  common_env = {
    DOMAIN_NAME           = var.domain_name
    GOOGLE_CLOUD_PROJECT  = var.project_id
    GOOGLE_CLOUD_LOCATION = var.region
    MEMORY_BANK_ID        = var.memory_bank_id
    AUDIT_SINK_TOPIC      = var.audit_sink_topic
    MAX_WRITES_PER_MINUTE = tostring(var.max_writes_per_minute)
  }
}

# ---------------------------------------------------------------------------
# Service accounts — one per component, least privilege (control C-11).
# ---------------------------------------------------------------------------

resource "google_service_account" "api" {
  project      = var.project_id
  account_id   = "${local.name}-api"
  display_name = "${var.domain_name} Memory Manager API"
  description  = "Serves the tool API and writes approved facts to the memory bank."
}

resource "google_pubsub_topic_iam_member" "audit_publish" {
  project = var.project_id
  topic   = var.audit_sink_topic
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# ---------------------------------------------------------------------------
# Cloud Run — API.
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "api" {
  project             = var.project_id
  location            = var.region
  name                = "${local.name}-api"
  ingress             = var.ingress
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.api.email
    timeout         = "60s"

    scaling {
      min_instance_count = var.min_instances
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
        for_each = merge(local.common_env, { COMPONENT = "api" })
        content {
          name  = env.key
          value = env.value
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
}
