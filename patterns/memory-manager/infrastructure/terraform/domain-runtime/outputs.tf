output "service_url" {
  description = "The tool API endpoint. The domain publishes this to its agent teams."
  value       = google_cloud_run_v2_service.api.uri
}

output "service_account" {
  description = "Give this to the platform team: it is the identity the platform-owned memory bank IAM binding grants access to. Nothing works until that binding exists."
  value       = google_service_account.api.email
}

output "writes_per_instance" {
  description = "The per-instance write budget the service enforces, for checking against the agreed share."
  value       = floor(var.max_writes_per_minute / var.max_instances)
}
