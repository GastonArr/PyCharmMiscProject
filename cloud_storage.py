import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
from google.cloud import storage

BUCKET_NAME = "operaciones-storage"


def _client() -> storage.Client:
    """
    Crea un cliente de GCS usando la info de la cuenta de servicio
    guardada en st.secrets['gcs_service_account'].
    Ojo: st.secrets ya devuelve un dict, NO hay que usar json.loads.
    """

    info = dict(st.secrets["gcs_service_account"])
    return storage.Client.from_service_account_info(info)


def _bucket(name: Optional[str] = None) -> storage.Bucket:
    if name is None:
        name = BUCKET_NAME
    return _client().bucket(name)


# -------- helpers genéricos ----------

def read_text_blob(blob_name: str, bucket_name: Optional[str] = None) -> str:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_text(encoding="utf-8")


def write_text_blob(blob_name: str, data: str, bucket_name: Optional[str] = None) -> None:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(data, content_type="application/json; charset=utf-8")


def download_blob_to_tempfile(
    blob_name: str,
    bucket_name: Optional[str] = None,
    suffix: str = "",
) -> Path:
    """
    Descarga un blob a un archivo temporal y devuelve la ruta.
    Ideal para trabajar con Excel/ExcelWriter, etc.
    """

    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    blob.download_to_filename(tmp.name)
    return Path(tmp.name)


def upload_file_to_blob(
    local_path: Path,
    blob_name: str,
    bucket_name: Optional[str] = None,
    content_type: Optional[str] = None,
) -> None:
    bucket = _bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if content_type:
        blob.content_type = content_type
    blob.upload_from_filename(str(local_path))
