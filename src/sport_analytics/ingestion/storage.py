# google-cloud-storage ships no type information, and this thin adapter is the only code that
# calls it.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
from typing import Protocol

from google.cloud import storage


class Storage(Protocol):
    def write(self, path: str, data: bytes, content_type: str) -> None: ...

    def uri(self, path: str) -> str: ...


class GcsStorage:
    def __init__(self, project: str, bucket: str) -> None:
        self._bucket = storage.Client(project=project).bucket(bucket)
        self._name = bucket

    def write(self, path: str, data: bytes, content_type: str) -> None:
        self._bucket.blob(path).upload_from_string(data, content_type=content_type)

    def uri(self, path: str) -> str:
        return f"gs://{self._name}/{path}"
