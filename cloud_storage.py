import base64
import json
import os
import tempfile
from typing import Optional

from google.api_core import exceptions
from google.cloud import storage

DEFAULT_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "proyecto-operaciones-storage")


def _client() -> storage.Client:
    key_b64 = os.getenv("GCS_SERVICE_ACCOUNT_JSON_B64")
    if key_b64:
        info = json.loads(base64.b64decode(key_b64))
        return storage.Client.from_service_account_info(info)

    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path and os.path.exists(key_path):
        return storage.Client.from_service_account_file(key_path)

    return storage.Client()


def _bucket(bucket_name: Optional[str] = None) -> storage.Bucket:
    name = bucket_name or DEFAULT_BUCKET_NAME
    return _client().bucket(name)


def blob_exists(blob_name: str, bucket_name: Optional[str] = None) -> bool:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    try:
        return blob.exists(_client())
    except exceptions.GoogleAPIError:
        return False


def download_blob_to_tempfile(blob_name: str, *, bucket_name: Optional[str] = None, suffix: str = "") -> Optional[str]:
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    try:
        blob.download_to_filename(temp_path)
        return temp_path
    except exceptions.NotFound:
        os.remove(temp_path)
        return None
    except Exception:
        os.remove(temp_path)
        raise


def upload_file_to_blob(blob_name: str, file_path: str, *, bucket_name: Optional[str] = None, content_type: Optional[str] = None) -> None:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(file_path, content_type=content_type)


def upload_bytes_to_blob(blob_name: str, data: bytes, *, bucket_name: Optional[str] = None, content_type: Optional[str] = None) -> None:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type=content_type)


def read_text_blob(blob_name: str, *, bucket_name: Optional[str] = None) -> Optional[str]:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    try:
        return blob.download_as_text()
    except exceptions.NotFound:
        return None


def write_json_blob(blob_name: str, data, *, bucket_name: Optional[str] = None) -> None:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(data, ensure_ascii=False, indent=2), content_type="application/json")

