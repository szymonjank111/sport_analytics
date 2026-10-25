resource "google_project_service" "apis" {
  for_each = toset([
    "bigquery.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ])

  service = each.key
  # Turning an API off would break whatever else in the project still uses it.
  disable_on_destroy = false
}
