output "workload_identity_provider" {
  description = "Value of the GCP_WIF_PROVIDER variable in GitHub."
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

output "ci_service_account" {
  description = "Value of the GCP_CI_SERVICE_ACCOUNT variable in GitHub."
  value       = google_service_account.ci.email
}

output "pipeline_service_account" {
  value = google_service_account.pipeline.email
}

output "app_reader_service_account" {
  value = google_service_account.app_reader.email
}
