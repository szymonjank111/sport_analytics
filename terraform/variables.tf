variable "project_id" {
  description = "ID of the Google Cloud project."
  type        = string
}

variable "location" {
  description = "Location of the bucket and the datasets, which BigQuery needs to be the same."
  type        = string
  default     = "us-central1"
}

variable "raw_bucket_name" {
  description = "Name of the bucket for raw source files."
  type        = string
}

variable "github_repository" {
  description = "GitHub repository whose workflows may act as the CI service account."
  type        = string
  default     = "szymonjank111/sport_analytics"
}
