resource "google_service_account" "pipeline" {
  account_id   = "pipeline"
  display_name = "Pipeline: loads raw data and builds the warehouse"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "app_reader" {
  account_id   = "app-reader"
  display_name = "App: reads the public marts"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "ci" {
  account_id   = "github-ci"
  display_name = "CI: builds dbt models in datasets of its own"

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "pipeline_raw" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.pipeline.member
}

resource "google_bigquery_dataset_iam_member" "pipeline" {
  for_each = google_bigquery_dataset.layers

  dataset_id = each.value.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline.member
}

# The app sees the public marts only, which keeps data without the right to share it private.
resource "google_bigquery_dataset_iam_member" "app_reader_marts_public" {
  dataset_id = google_bigquery_dataset.layers["marts_public"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.app_reader.member
}

resource "google_bigquery_dataset_iam_member" "ci_raw" {
  dataset_id = google_bigquery_dataset.layers["raw"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.ci.member
}

resource "google_project_iam_member" "job_user" {
  for_each = {
    pipeline   = google_service_account.pipeline.member
    app_reader = google_service_account.app_reader.member
  }

  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = each.value
}

# BigQuery User runs jobs and creates datasets, which CI owns and so may fill and drop.
resource "google_project_iam_member" "ci_bigquery_user" {
  project = var.project_id
  role    = "roles/bigquery.user"
  member  = google_service_account.ci.member
}
