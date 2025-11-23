"""Subaplicación placeholder para Planillas Ley 2785.

Este módulo permite integrar la carpeta Planillas-Ley-2785 al
selector de sistemas de la app principal. Si en el futuro se
agregan más archivos en esta carpeta, este punto de entrada
puede importarlos o delegar la lógica necesaria.
"""
from __future__ import annotations

from typing import Iterable
import streamlit as st


def _render_unit_selector(allowed_units: Iterable[str]) -> str:
    units = list(allowed_units)
    if not units:
        return ""
    if len(units) == 1:
        st.info(f"Unidad habilitada: {units[0]}")
        return units[0]
    return st.selectbox("Seleccione la unidad con la que desea operar", units, index=0)


def run_planillas_ley_2785_app(allowed_units: list[str], configure_page: bool = True) -> None:
    """Punto de entrada para la app de Planillas Ley 2785.

    Parameters
    ----------
    allowed_units:
        Lista de unidades habilitadas para el usuario autenticado.
    configure_page:
        Si es True, configura el título y el layout de la página. Debe
        mantenerse en False cuando se llama desde la app principal.
    """

    if configure_page:
        st.set_page_config(page_title="Planillas Ley 2785", layout="wide")

    st.title("Planillas Ley 2785")
    if not allowed_units:
        st.error("No tiene unidades habilitadas para operar en Planillas Ley 2785.")
        return

    selected_unit = _render_unit_selector(allowed_units)
    if not selected_unit:
        st.stop()

    st.success(
        "Acceso habilitado. Puede operar únicamente sobre la unidad autorizada: "
        f"{selected_unit}. Si necesita modificar la lista de unidades habilitadas, contacte al administrador."
    )
    st.info(
        "Este es un punto de integración temporal mientras se agregan las planillas específicas de la Ley 2785. "
        "Incorpore aquí las pantallas necesarias dentro de esta carpeta para completar el flujo."
    )
