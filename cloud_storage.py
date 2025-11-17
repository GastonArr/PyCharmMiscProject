import json
import os
import tempfile
from typing import List

import streamlit as st
from google.cloud import storage


def _client() -> storage.Client:
    info = json.loads(st.secrets["gcs_service_account"])
    return storage.Client.from_service_account_info(info)


def read_text_blob(blob_name: str, bucket_name: str) -> str:
    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    return blob.download_as_text(encoding="utf-8")


def write_text_blob(blob_name: str, text: str, bucket_name: str) -> None:
    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(text, content_type="application/json")


def download_blob_to_tempfile(blob_name: str, bucket_name: str, suffix: str) -> str:
    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    blob.download_to_filename(path)
    return path


def upload_file_to_blob(local_path: str, blob_name: str, bucket_name: str) -> None:
    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)


def list_blobs(bucket_name: str) -> List[str]:
    client = _client()
    bucket = client.bucket(bucket_name)
    return [blob.name for blob in bucket.list_blobs()]
