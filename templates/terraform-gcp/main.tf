# Domain-owned reference deployment on Cloud Run.
#
# OWNERSHIP BOUNDARY — read this before editing.
#
#   DOMAIN-OWNED (this module): the Cloud Run services, their service accounts, the Pub/Sub
#   topic and subscriptions, secret access bindings, and the domain's own alerting.
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
  description  = "Serves the tool API. Publishes accepted writes to the retry queue."
}

resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "${local.name}-worker"
  display_name = "${var.domain_name} Memory Manager worker"
  description  = "Consumes the retry queue and writes approved facts to the memory bank."
}

# ---------------------------------------------------------------------------
# Retry queue.
#
# Pub/Sub carries durability, bounded retry and dead-lettering. It does NOT carry
# aggregate rate control: the subscription below is a PULL subscription precisely so the
# worker governs its own consumption rate against the shared project quota. A push
# subscription would surrender that control. See design/001-memory-manager/design.md.
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "writes" {
  project = var.project_id
  name    = "${local.name}-writes"

  message_retention_duration = "604800s" # 7 days
}

resource "google_pubsub_topic" "dead_letter" {
  project = var.project_id
  name    = "${local.name}-writes-dlq"

  message_retention_duration = "604800s"
}

resource "google_pubsub_subscription" "writes" {
  project = var.project_id
  name    = "${local.name}-writes-sub"
  topic   = google_pubsub_topic.writes.id

  # Pull: the worker controls the rate. Do not convert this to push_config.
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"
  enable_message_ordering    = false

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = "" # never expire
  }
}

resource "google_pubsub_subscription" "dead_letter" {
  project = var.project_id
  name    = "${local.name}-writes-dlq-sub"
  topic   = google_pubsub_topic.dead_letter.id

  # Retained for operator triage and selective replay. See docs/runbook.md.
  ack_deadline_seconds       = 60
  message_retention_duration = "604800s"

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_topic_iam_member" "api_publish" {
  project = var.project_id
  topic   = google_pubsub_topic.writes.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_pubsub_subscription_iam_member" "worker_subscribe" {
  project      = var.project_id
  subscription = google_pubsub_subscription.writes.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_pubsub_topic_iam_member" "audit_publish" {
  for_each = {
    api    = google_service_account.api.email
    worker = google_service_account.worker.email
  }

  project = var.project_id
  topic   = var.audit_sink_topic
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${each.value}"
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

# ---------------------------------------------------------------------------
# Cloud Run — worker.
#
# A Cloud Run service (not a Job) with min_instance_count >= 1, because a pull
# subscription needs a continuously running consumer. Cloud Run Jobs were considered for
# batch replay; see the design document for the trade-off.
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "worker" {
  project             = var.project_id
  location            = var.region
  name                = "${local.name}-worker"
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = var.deletion_protection

  template {
    service_account = google_service_account.worker.email
    timeout         = "3600s"

    scaling {
      min_instance_count = 1
      max_instance_count = var.max_instances
    }

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        # The worker pulls continuously; it must not be throttled when idle.
        cpu_idle = false
      }

      dynamic "env" {
        for_each = merge(local.common_env, {
          COMPONENT         = "worker"
          SUBSCRIPTION_NAME = google_pubsub_subscription.writes.name
        })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }
}
