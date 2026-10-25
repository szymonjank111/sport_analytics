terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }

  # The bucket comes from `terraform init -backend-config="bucket=..."`, so no name is hardcoded.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.location
}
