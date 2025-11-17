import base64
import json
import os
import tempfile
from typing import Optional

from google.api_core import exceptions
from google.cloud import storage

DEFAULT_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "proyecto-operaciones-storage")


def _load_service_account(raw_info, *, source: str) -> dict:
    """Parsea un diccionario de credenciales con errores claros."""

    try:
        return json.loads(raw_info) if isinstance(raw_info, str) else dict(raw_info)
    except (TypeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"No se pudieron leer las credenciales de GCS desde {source}: formato JSON inválido"
        ) from exc


def _client() -> storage.Client:
    # 1) Streamlit secrets (desplegado en Streamlit Cloud)
    try:
        import streamlit as st

        if "gcs_service_account" in st.secrets:
            info = _load_service_account(st.secrets["gcs_service_account"], source="st.secrets")
            project = info.get("project_id")
            return storage.Client.from_service_account_info(info, project=project)
    except ModuleNotFoundError:
        # streamlit no está instalado en ejecución local
        pass

    # 2) Credencial JSON en texto plano
    key_json = os.getenv("GCS_SERVICE_ACCOUNT_JSON")
    if key_json:
        info = _load_service_account(key_json, source="GCS_SERVICE_ACCOUNT_JSON")
        project = info.get("project_id")
        return storage.Client.from_service_account_info(info, project=project)

    key_b64 = os.getenv("GCS_SERVICE_ACCOUNT_JSON_B64")
    if key_b64:
        try:
            decoded = base64.b64decode(key_b64)
        except (base64.binascii.Error, ValueError) as exc:
            raise RuntimeError(
                "No se pudieron decodificar las credenciales de GCS desde GCS_SERVICE_ACCOUNT_JSON_B64:"
                " cadena base64 inválida"
            ) from exc

        info = _load_service_account(decoded, source="GCS_SERVICE_ACCOUNT_JSON_B64")
        project = info.get("project_id")
        return storage.Client.from_service_account_info(info, project=project)

    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if key_path and os.path.exists(key_path):
        return storage.Client.from_service_account_file(key_path)

    project = os.getenv("GCS_PROJECT_ID")
    return storage.Client(project=project)


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

