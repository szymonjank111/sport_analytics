from functools import cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GcpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gcp_project_id: str
    gcp_location: str = "us-central1"


class IngestionSettings(GcpSettings):
    football_data_api_key: SecretStr
    gcs_raw_bucket: str
    bq_raw_dataset: str = "raw"


@cache
def get_ingestion_settings() -> IngestionSettings:
    # Fields are read from the environment, which pyright cannot see.
    return IngestionSettings()  # pyright: ignore[reportCallIssue]


class AppSettings(GcpSettings):
    app_dataset: str


@cache
def get_app_settings() -> AppSettings:
    # As above, the fields come from the environment.
    return AppSettings()  # pyright: ignore[reportCallIssue]
