"""Utilities to persist Excel workbooks and agenda JSON in Google Drive."""
from __future__ import annotations

import io
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from typing import Callable, Dict, Optional, Tuple, Union

import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload


MIME_TYPES: Dict[str, str] = {
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".json": "application/json",
}

_CACHE_DIR = os.path.join(tempfile.gettempdir(), "streamlit_drive_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)


def guess_mime_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return MIME_TYPES.get(ext, "application/octet-stream")


class DriveStorage:
    """Small helper around Google Drive API for file persistence."""

    def __init__(self, service, folder_id: str) -> None:
        self.service = service
        self.folder_id = folder_id
        self._name_to_id: Dict[str, str] = {}
        self._local_cache: Dict[str, Tuple[str, str, Callable[[], bytes]]] = {}

    # ---------- Construction ----------
    @classmethod
    def from_streamlit_secrets(cls) -> "DriveStorage":
        config = st.secrets.get("drive")
        if not config:
            raise RuntimeError(
                "Falta la configuración de Google Drive en st.secrets['drive']. "
                "Defina al menos 'service_account' y 'folder_id'."
            )

        service_account_info = config.get("service_account")
        if service_account_info is None:
            raise RuntimeError("La configuración de Google Drive debe incluir 'service_account'.")
        if isinstance(service_account_info, str):
            service_account_info = json.loads(service_account_info)

        scopes = config.get(
            "scopes",
            ["https://www.googleapis.com/auth/drive"],
        )
        credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        service = build("drive", "v3", credentials=credentials)

        folder_id = config.get("folder_id")
        if not folder_id:
            raise RuntimeError("La configuración de Google Drive debe incluir 'folder_id'.")

        return cls(service, folder_id)

    # ---------- Low level helpers ----------
    def _escape_name(self, name: str) -> str:
        return name.replace("'", "\\'")

    def _find_file_id(self, filename: str) -> Optional[str]:
        if filename in self._name_to_id:
            return self._name_to_id[filename]

        query = (
            f"name = '{self._escape_name(filename)}' and '{self.folder_id}' in parents and trashed = false"
        )
        try:
            response = (
                self.service.files()
                .list(q=query, spaces="drive", fields="files(id, name)", pageSize=1)
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"No se pudo consultar Google Drive: {exc}") from exc

        files = response.get("files", [])
        if not files:
            return None
        file_id = files[0]["id"]
        self._name_to_id[filename] = file_id
        return file_id

    def _create_file(self, filename: str, data: bytes, mime_type: str) -> str:
        metadata = {"name": filename, "parents": [self.folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=False)
        try:
            response = (
                self.service.files()
                .create(body=metadata, media_body=media, fields="id")
                .execute()
            )
        except HttpError as exc:
            raise RuntimeError(f"No se pudo crear el archivo {filename} en Google Drive: {exc}") from exc
        file_id = response["id"]
        self._name_to_id[filename] = file_id
        return file_id

    def _download_existing(self, file_id: str) -> bytes:
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status and status.total_size:
                # No usamos el progreso pero avanzar el loop permite descargas grandes.
                pass
        return fh.getvalue()

    def file_exists(self, filename: str) -> bool:
        return self._find_file_id(filename) is not None

    def _default_factory(self, default) -> Callable[[], bytes]:
        if default is None:
            return lambda: b""
        if callable(default):
            return default
        return lambda: default

    # ---------- Public helpers ----------
    def ensure_local_file(
        self,
        filename: str,
        *,
        default: Optional[Union[Callable[[], bytes], bytes]] = None,
        mime_type: Optional[str] = None,
        force_download: bool = False,
    ) -> str:
        """Ensure a local cached copy exists and return its path."""

        mime = mime_type or guess_mime_type(filename)
        default_factory = self._default_factory(default)
        local_path = os.path.join(_CACHE_DIR, filename)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        needs_download = force_download or not os.path.exists(local_path)
        if needs_download:
            file_id = self._find_file_id(filename)
            if file_id is None:
                data = default_factory()
                file_id = self._create_file(filename, data, mime)
            else:
                data = self._download_existing(file_id)
            with open(local_path, "wb") as fh:
                fh.write(data)
        self._local_cache[local_path] = (filename, mime, default_factory)
        return local_path

    def ensure_local_path(self, path: str) -> None:
        info = self._local_cache.get(path)
        if not info:
            raise RuntimeError(
                "El archivo local no está registrado en la caché. Use ensure_local_file() primero."
            )
        filename, mime, default_factory = info
        if not os.path.exists(path):
            file_id = self._find_file_id(filename)
            if file_id is None:
                data = default_factory()
                file_id = self._create_file(filename, data, mime)
            else:
                data = self._download_existing(file_id)
            with open(path, "wb") as fh:
                fh.write(data)

    def upload_local_path(self, path: str) -> None:
        info = self._local_cache.get(path)
        if not info:
            raise RuntimeError(
                "No se puede subir un archivo que no se registró previamente."
            )
        filename, mime, _ = info
        with open(path, "rb") as fh:
            data = fh.read()
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
        file_id = self._find_file_id(filename)
        if file_id is None:
            self._create_file(filename, data, mime)
        else:
            try:
                self.service.files().update(fileId=file_id, media_body=media).execute()
            except HttpError as exc:
                raise RuntimeError(f"No se pudo actualizar {filename} en Google Drive: {exc}") from exc

    @contextmanager
    def temporary_copy(self, filename: str, *, default=None, mime_type: Optional[str] = None):
        path = self.ensure_local_file(filename, default=default, mime_type=mime_type)
        try:
            yield path
            self.upload_local_path(path)
        finally:
            if os.path.exists(path):
                os.remove(path)
            self._local_cache.pop(path, None)


_storage_instance: Optional[DriveStorage] = None
_storage_lock = threading.Lock()


def get_storage() -> DriveStorage:
    global _storage_instance
    if _storage_instance is None:
        with _storage_lock:
            if _storage_instance is None:
                _storage_instance = DriveStorage.from_streamlit_secrets()
    return _storage_instance
