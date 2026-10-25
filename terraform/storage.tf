resource "google_storage_bucket" "raw" {
  name                        = var.raw_bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.apis]
}
