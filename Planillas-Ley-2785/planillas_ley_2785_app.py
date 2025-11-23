"""Módulo de Streamlit para gestionar las planillas de la Ley 2785."""
from __future__ import annotations

import datetime
from typing import Iterable

import streamlit as st

from planillas_ley_config import PLANILLAS_LEY_UNIDADES
from gcs_utils import download_blob_bytes, upload_blob_bytes

APP_TITLE = "Planillas Ley 2785"
BLOB_PREFIX = "ley-2785"


def _slugify(value: str) -> str:
    return value.lower().replace(" ", "-")


def _blob_path_for_unit(unidad: str) -> str:
    return f"{BLOB_PREFIX}/{_slugify(unidad)}/planilla.xlsx"


def _unidades_habilitadas(allowed_units: Iterable[str] | None) -> list[str]:
    unidades_validas: list[str] = []
    for unidad in allowed_units or []:
        if unidad in PLANILLAS_LEY_UNIDADES and unidad not in unidades_validas:
            unidades_validas.append(unidad)
    return unidades_validas


def _seleccionar_unidad(unidades_disponibles: list[str]) -> str | None:
    if not unidades_disponibles:
        st.error("No tiene unidades habilitadas para Planillas Ley 2785. Contacte al administrador.")
        return None

    if len(unidades_disponibles) == 1:
        unidad = unidades_disponibles[0]
        st.info(f"Unidad asignada: **{unidad}**")
        return unidad

    return st.selectbox(
        "Seleccione la unidad con la que quiere trabajar:",
        unidades_disponibles,
        format_func=lambda u: f"Unidad {u}",
    )


def _render_descarga(blob_path: str, unidad: str) -> None:
    contenido = download_blob_bytes(blob_path)
    if contenido:
        nombre = f"planilla-ley-2785-{_slugify(unidad)}.xlsx"
        st.download_button(
            "📥 Descargar planilla actual",
            data=contenido,
            file_name=nombre,
            use_container_width=True,
        )
    else:
        st.info(
            "Todavía no hay una planilla disponible para esta unidad en el almacenamiento. "
            "Cargue una planilla para comenzar a trabajar."
        )


def _render_subida(blob_path: str, unidad: str) -> None:
    archivo = st.file_uploader(
        "Subir planilla actualizada (Excel)",
        type=["xlsx", "xlsm", "xls"],
        accept_multiple_files=False,
        key=f"ley2785-uploader-{_slugify(unidad)}",
    )

    if archivo:
        contenido = archivo.read()
        upload_blob_bytes(
            blob_path,
            contenido,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.success(
            "Planilla actualizada correctamente en el almacenamiento central. "
            "Puede descargarla nuevamente para verificar los cambios."
        )


def run_planillas_ley_2785_app(
    allowed_units: Iterable[str] | None = None,
    configure_page: bool = True,
) -> None:
    if configure_page:
        st.set_page_config(page_title=APP_TITLE, layout="wide")

    unidades_disponibles = _unidades_habilitadas(allowed_units)
    unidad = _seleccionar_unidad(unidades_disponibles)
    if not unidad:
        return

    st.title(APP_TITLE)
    st.caption("Gestión centralizada de planillas por unidad autorizada.")

    st.subheader(f"Unidad: {unidad}")
    st.write(
        "Los archivos cargados se guardan en el bucket usando una ruta única por unidad. "
        "Solo la unidad asignada puede acceder a su planilla."
    )

    blob_path = _blob_path_for_unit(unidad)
    st.markdown(f"Ruta de almacenamiento: `{blob_path}`")

    col_descarga, col_subida = st.columns(2)
    with col_descarga:
        _render_descarga(blob_path, unidad)

    with col_subida:
        _render_subida(blob_path, unidad)

    st.markdown("---")
    st.caption(
        "Última actualización de la sesión: "
        f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
