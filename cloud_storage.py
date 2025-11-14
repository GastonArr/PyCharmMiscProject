"""Utilities to mirror critical files to Google Drive when credentials are available."""
from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

import streamlit as st

try:  # External optional dependency, configured via requirements.
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
except Exception:  # pragma: no cover - gracefully degrade when libs missing.
    service_account = None  # type: ignore[assignment]
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment]
    MediaIoBaseDownload = None  # type: ignore[assignment]
    MediaIoBaseUpload = None  # type: ignore[assignment]


LOGGER = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Tabla opcional que permite mapear cada archivo local a su metadata remota.
#
# Ejemplo de uso:
# COMISARIA_REMOTE_FILES = {
#     "excel/comisaria 14.xlsm": {
#         "file_id": "1AbCdEfGhIjKlMnOp",  # ID del archivo compartido en Drive
#         # "remote_name": "Comisaria 14.xlsm",  # opcional, por defecto se usa el basename local
#     },
# }
#
# Se puede dejar vacía si todavía no se conoce el ID de un archivo.
COMISARIA_REMOTE_FILES: Dict[str, Dict[str, str]] = {}
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


@dataclass
class StorageConfig:
    service_account_info: Dict[str, object]
    folder_id: str


class StorageBackend:
    """Abstract storage backend."""

    def ensure_local_file(
        self, local_path: str, remote_name: str, file_id: Optional[str]
    ) -> None:
        raise NotImplementedError

    def sync_local_to_remote(
        self, local_path: str, remote_name: str, file_id: Optional[str]
    ) -> None:
        raise NotImplementedError


class LocalBackend(StorageBackend):
    """No-op backend when Google Drive credentials are not configured."""

    def ensure_local_file(  # pragma: no cover - trivial
        self, local_path: str, remote_name: str, file_id: Optional[str]
    ) -> None:
        LOGGER.debug("Local backend in use; skipping download for %s", remote_name)

    def sync_local_to_remote(  # pragma: no cover - trivial
        self, local_path: str, remote_name: str, file_id: Optional[str]
    ) -> None:
        LOGGER.debug("Local backend in use; skipping upload for %s", remote_name)


class GoogleDriveBackend(StorageBackend):
    """Persist files inside a shared Google Drive folder."""

    def __init__(self, config: StorageConfig):
        if service_account is None or build is None:
            raise RuntimeError(
                "Google API client libraries are required but missing. Install google-api-python-client."
            )
        credentials = service_account.Credentials.from_service_account_info(
            config.service_account_info, scopes=SCOPES
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._folder_id = config.folder_id
        self._file_cache: Dict[str, Optional[str]] = {}

    def _cache_key(self, remote_name: str) -> str:
        return f"name:{remote_name}"

    # --------------- Internal helpers ---------------
    def _find_file_id(self, remote_name: str) -> Optional[str]:
        cache_key = self._cache_key(remote_name)
        if cache_key in self._file_cache:
            return self._file_cache[cache_key]
        escaped_name = remote_name.replace("'", "\\'")
        query = f"name = '{escaped_name}' and '{self._folder_id}' in parents and trashed = false"
        result = (
            self._service.files()
            .list(q=query, spaces="drive", fields="files(id,name)", pageSize=1)
            .execute()
        )
        files = result.get("files", [])
        file_id = files[0]["id"] if files else None
        self._file_cache[cache_key] = file_id
        return file_id

    def _download_bytes(self, file_id: str) -> bytes:
        request = self._service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    def _guess_mime_type(self, local_path: str) -> str:
        ext = os.path.splitext(local_path)[1].lower()
        return {
            ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".json": "application/json",
            ".txt": "text/plain",
        }.get(ext, "application/octet-stream")

    def _upload_bytes(
        self, file_id: Optional[str], remote_name: str, data: bytes, mime_type: str
    ) -> None:
        media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=False)
        if file_id:
            self._service.files().update(fileId=file_id, media_body=media).execute()
        else:
            metadata = {"name": remote_name, "parents": [self._folder_id]}
            file = self._service.files().create(body=metadata, media_body=media, fields="id").execute()
            self._file_cache[self._cache_key(remote_name)] = file.get("id")

    # --------------- Public API ---------------
    def ensure_local_file(
        self, local_path: str, remote_name: str, file_id: Optional[str]
    ) -> None:
        try:
            effective_id = file_id or self._find_file_id(remote_name)
            if not effective_id:
                return
            data = self._download_bytes(effective_id)
            if file_id:
                self._file_cache[self._cache_key(remote_name)] = effective_id
        except HttpError as exc:  # pragma: no cover - depends on network
            LOGGER.warning("No se pudo descargar %s desde Google Drive: %s", remote_name, exc)
            return
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(data)

    def sync_local_to_remote(
        self, local_path: str, remote_name: str, file_id: Optional[str]
    ) -> None:
        if not os.path.exists(local_path):
            return
        try:
            with open(local_path, "rb") as fh:
                data = fh.read()
            effective_id = file_id or self._find_file_id(remote_name)
            mime_type = self._guess_mime_type(local_path)
            self._upload_bytes(effective_id, remote_name, data, mime_type)
            if file_id and effective_id:
                self._file_cache[self._cache_key(remote_name)] = effective_id
        except HttpError as exc:  # pragma: no cover - depends on network
            LOGGER.warning("No se pudo subir %s a Google Drive: %s", remote_name, exc)


# --------------- Configuration helpers ---------------


def _load_config_from_secrets() -> Optional[StorageConfig]:
    try:
        gdrive_section = st.secrets.get("gdrive")  # type: ignore[attr-defined]
    except Exception:
        gdrive_section = None
    if gdrive_section and isinstance(gdrive_section, dict):
        service_info = gdrive_section.get("service_account")
        folder_id = gdrive_section.get("folder_id")
        if isinstance(service_info, dict) and isinstance(folder_id, str):
            return StorageConfig(service_info, folder_id)
    env_json = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
    env_folder = os.getenv("GDRIVE_FOLDER_ID")
    if env_json and env_folder:
        try:
            info = json.loads(env_json)
        except json.JSONDecodeError:
            LOGGER.error("GDRIVE_SERVICE_ACCOUNT_JSON no contiene JSON válido")
        else:
            return StorageConfig(info, env_folder)
    return None


def _create_backend() -> StorageBackend:
    config = _load_config_from_secrets()
    if not config:
        LOGGER.info("Google Drive no configurado; se utilizará almacenamiento local.")
        return LocalBackend()
    try:
        backend = GoogleDriveBackend(config)
        LOGGER.info("Google Drive configurado correctamente. Los archivos se sincronizarán con la nube.")
        return backend
    except Exception as exc:  # pragma: no cover - depende de entorno
        LOGGER.warning("No se pudo inicializar Google Drive (%s). Se continuará en modo local.", exc)
        return LocalBackend()


_BACKEND: Optional[StorageBackend] = None


def _get_backend() -> StorageBackend:
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = _create_backend()
    return _BACKEND


def _normalize_local_key(local_path: str) -> str:
    rel = os.path.relpath(local_path, BASE_DIR)
    return rel.replace(os.sep, "/")


def _lookup_remote_entry(local_path: str) -> Dict[str, str]:
    key = _normalize_local_key(local_path)
    return COMISARIA_REMOTE_FILES.get(key, {})


def _remote_name_for(local_path: str, override: Optional[str]) -> str:
    if override:
        return override
    entry = _lookup_remote_entry(local_path)
    if "remote_name" in entry:
        return entry["remote_name"]
    return os.path.basename(local_path)


def _file_id_for(local_path: str, override: Optional[str]) -> Optional[str]:
    if override:
        return override
    entry = _lookup_remote_entry(local_path)
    return entry.get("file_id")


def ensure_local_file(
    local_path: str,
    remote_name: Optional[str] = None,
    file_id: Optional[str] = None,
) -> None:
    remote = _remote_name_for(local_path, remote_name)
    resolved_id = _file_id_for(local_path, file_id)
    _get_backend().ensure_local_file(local_path, remote, resolved_id)


def sync_local_to_remote(
    local_path: str,
    remote_name: Optional[str] = None,
    file_id: Optional[str] = None,
) -> None:
    remote = _remote_name_for(local_path, remote_name)
    resolved_id = _file_id_for(local_path, file_id)
    _get_backend().sync_local_to_remote(local_path, remote, resolved_id)


def get_remote_file_id(local_path: str) -> Optional[str]:
    """Devuelve el file_id configurado para el archivo local (si existe)."""

    return _file_id_for(local_path, None)


def get_remote_name(local_path: str) -> str:
    """Devuelve el nombre remoto configurado para el archivo local."""

    return _remote_name_for(local_path, None)


def get_remote_params(local_path: str) -> Dict[str, str]:
    """Devuelve kwargs listos para pasar a ensure/sync con nombre e ID."""

    params: Dict[str, str] = {"remote_name": get_remote_name(local_path)}
    file_id = get_remote_file_id(local_path)
    if file_id:
        params["file_id"] = file_id
    return params
