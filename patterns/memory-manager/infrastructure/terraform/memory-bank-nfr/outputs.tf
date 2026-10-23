output "audit_sink_writer_identity" {
  description = "The sink's writer identity, for granting dataset access if the dataset is managed elsewhere."
  value       = google_logging_project_sink.audit.writer_identity
}

output "bank_access_condition" {
  description = "The IAM Condition limiting this domain's identity to its own bank. Useful for review and for proving S-8 in a controls assessment."
  value       = google_project_iam_member.memory_manager_bank_access.condition[0].expression
}
