# The bucket and the raw dataset were created by hand in Phase 1.
import {
  to = google_storage_bucket.raw
  id = "${var.project_id}/${var.raw_bucket_name}"
}

import {
  to = google_bigquery_dataset.layers["raw"]
  id = "projects/${var.project_id}/datasets/raw"
}
