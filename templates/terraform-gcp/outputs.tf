output "api_url" {
  description = "The tool API endpoint. The domain publishes this to its agent teams."
  value       = google_cloud_run_v2_service.api.uri
}

output "api_service_account" {
  description = "Provide this to the platform team: it is the identity the platform-owned memory bank IAM binding grants access to."
  value       = google_service_account.api.email
}
