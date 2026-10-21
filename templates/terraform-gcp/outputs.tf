output "api_url" {
  description = "The tool API endpoint. The domain publishes this to its agent teams."
  value       = google_cloud_run_v2_service.api.uri
}

output "api_service_account" {
  description = "Provide this to the platform team: it is the identity the platform-owned memory bank IAM binding grants access to."
  value       = google_service_account.api.email
}

output "worker_service_account" {
  description = "Provide this to the platform team for the memory bank IAM binding."
  value       = google_service_account.worker.email
}

output "writes_topic" {
  description = "Retry queue topic."
  value       = google_pubsub_topic.writes.name
}

output "dead_letter_subscription" {
  description = "Dead-letter subscription, for operator triage and selective replay."
  value       = google_pubsub_subscription.dead_letter.name
}
