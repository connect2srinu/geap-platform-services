# Platform-owned. A domain does not apply this module.
#
# This is the only control that survives a domain forking the pattern source. The conformance
# suite, the boundary checks and the lock verification all run in a domain's own CI, which the
# platform cannot observe. These resources sit outside their application:
#
#   * the bank's IAM binding, scoped to the domain's Memory Manager identity and nothing else;
#   * the audit sink, which a domain cannot switch off;
#   * quota alerting with per-domain attribution.
#
# So the platform controls what a domain's service account may do to a bank. It does not control
# what their code does before it gets there. Nothing here should be described as more than that.
#
# The bank itself is NOT created here. A memory bank is one Agent Engine carrying a
# context_spec.memory_bank_config, so its resource name is reasoningEngines/<id> — verified against
# a live project by the spike on 2026-10-22, and against the SDK's own request paths on 2026-10-23.
# The newer agentplatform client calls the sub-client `memory_banks`, but that is a naming change
# in the client, not a new API resource; the condition below must match what the server actually
# names, not what the client calls it.
#
# google provider 7.45 does have google_vertex_ai_reasoning_engine and its IAM resources, but they
# do not express the memory bank configuration, so the bank is created out of band and passed in.
#
# Consequence for CMEK (control C-20): the customer-managed encryption key can only be set when the
# bank is created, via CreateMemoryBankConfig.encryption_spec.kms_key_name. There is no way to add
# one to an existing bank, so CMEK is a property of the out-of-band creation step, not of this
# module, and it has to be decided before a domain's bank exists.

locals {
  name = "${var.domain_name}-memory-bank"
}

data "google_project" "platform" {
  project_id = var.project_id
}

# The binding that matters. Granted to the Memory Manager identity, with an IAM Condition limiting
# it to this domain's bank, so a compromised service account in one domain cannot read another's.
resource "google_project_iam_member" "memory_manager_bank_access" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${var.memory_manager_service_account}"

  condition {
    title       = "${var.domain_name} bank only"
    description = "Limits this identity to its own domain's memory bank. Without the condition, one domain's service account could reach every bank in the shared project."
    expression  = "resource.name.startsWith(\"projects/${data.google_project.platform.number}/locations/${var.region}/reasoningEngines/\") && resource.name.endsWith(\"/${var.domain_name}\")"
  }
}

# The central audit sink. Configured outside the domain's application, so a domain cannot suppress
# its own audit trail by changing configuration or code.
resource "google_logging_project_sink" "audit" {
  project                = var.project_id
  name                   = "${local.name}-audit"
  destination            = "bigquery.googleapis.com/projects/${var.project_id}/datasets/${var.audit_sink_dataset}"
  unique_writer_identity = true

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.domain_name}-memory-manager"
    jsonPayload.event=~"^memory_(write|remediation|denial)"
  EOT
}

resource "google_bigquery_dataset_iam_member" "audit_writer" {
  project    = var.project_id
  dataset_id = var.audit_sink_dataset
  role       = "roles/bigquery.dataEditor"
  member     = google_logging_project_sink.audit.writer_identity
}

# Quota alerting, per domain. The project's Memory Bank quota is shared, so without per-domain
# attribution a contention incident cannot be triaged: you can see that writes are failing but not
# whose traffic caused it.
resource "google_monitoring_alert_policy" "provider_throttled" {
  project      = var.project_id
  display_name = "${local.name} provider throttled"
  combiner     = "OR"

  documentation {
    content = <<-EOT
      The memory store is throttling writes for ${var.domain_name}.

      The project quota is shared across every domain in this project, so this may not be caused by
      ${var.domain_name}'s own traffic. Check quota_consumed by domain before asking this team to
      reduce load - and do not raise one domain's budget to push through, which moves the outage to
      another domain.
    EOT
  }

  conditions {
    display_name = "provider_throttled rising"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/provider_throttled\" AND resource.labels.service_name=\"${var.domain_name}-memory-manager\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.quota_alert_notification_channels
}

resource "google_monitoring_alert_policy" "remediations" {
  project      = var.project_id
  display_name = "${local.name} remediations"
  combiner     = "OR"

  documentation {
    content = <<-EOT
      A stored memory failed re-classification after provider consolidation and was rolled back or
      deleted.

      A non-zero rate is expected occasionally and is the control working. A sustained rate means
      consolidation is regularly producing content the domain's classifier refuses, which is a
      design question rather than an incident.
    EOT
  }

  conditions {
    display_name = "remediations rising"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"logging.googleapis.com/user/remediations\" AND resource.labels.service_name=\"${var.domain_name}-memory-manager\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "600s"

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.quota_alert_notification_channels
}
