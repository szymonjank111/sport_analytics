resource "google_bigquery_dataset" "layers" {
  for_each = toset(["raw", "staging", "intermediate", "marts_public", "marts_private"])

  dataset_id = each.key
  location   = var.location

  depends_on = [google_project_service.apis]
}
