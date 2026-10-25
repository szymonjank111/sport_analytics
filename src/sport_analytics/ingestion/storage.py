# google-cloud-storage ships no type information, and this thin adapter is the only code that
# calls it.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
from typing import Protocol, cast

from google.cloud import storage


class Storage(Protocol):
    def write(self, path: str, data: bytes, content_type: str) -> None: ...

    def read(self, path: str) -> bytes: ...

    def list_paths(self, prefix: str) -> list[str]: ...

    def uri(self, path: str) -> str: ...


class GcsStorage:
    def __init__(self, project: str, bucket: str) -> None:
        self._bucket = storage.Client(project=project).bucket(bucket)
        self._name = bucket

    def write(self, path: str, data: bytes, content_type: str) -> None:
        self._bucket.blob(path).upload_from_string(data, content_type=content_type)

    def read(self, path: str) -> bytes:
        return self._bucket.blob(path).download_as_bytes()

    def list_paths(self, prefix: str) -> list[str]:
        names = [cast(str, blob.name) for blob in self._bucket.list_blobs(prefix=prefix)]
        # A folder made in the console is an empty object whose name ends with a slash.
        return [name for name in names if not name.endswith("/")]

    def uri(self, path: str) -> str:
        return f"gs://{self._name}/{path}"
