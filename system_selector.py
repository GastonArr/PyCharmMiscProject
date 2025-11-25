"""Selector de sistemas disponible tras el inicio de sesión."""
from __future__ import annotations

import streamlit as st

AVAILABLE_SYSTEMS = [
    {
        "id": "snic-sat",
        "label": "Planillas SNIC-SAT.",
        "description": "Ingreso y administración de planillas.",
        "icon": "🗂️",
    },
    {
        "id": "operativos-verano",
        "label": "Planillas Operativo Verano",
        "description": "Carga de Operativos Verano DSICCO.",
        "icon": "🌞",
    },
    {
        "id": "planillas-ley-2785",
        "label": "Planillas Ley 2785",
        "description": "Carga de planillas LEY 2785 por unidad habilitada.",
        "icon": "📄",
    },
]


def render_system_selector() -> None:
    """Renderiza la pantalla para elegir el sistema activo."""

    st.title("Panel de sistemas DSICCO")
    st.caption("Seleccione el sistema con el que desea trabajar.")

    col_header, col_logout = st.columns([4, 1])
    with col_header:
        st.empty()
    with col_logout:
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    allowed_systems = st.session_state.get("allowed_systems")

    for system in AVAILABLE_SYSTEMS:
        if allowed_systems and system.get("id") not in allowed_systems:
            continue
        with st.container():
            st.caption(system.get("description", ""))
            if st.button(
                f"{system['icon']} {system['label']}",
                key=f"system-btn-{system['id']}",
                use_container_width=True,
            ):
                st.session_state.selected_system = system["id"]
                st.session_state.selected_system_label = system["label"]
                st.rerun()

    if not st.session_state.get("selected_system"):
        st.info("Para continuar, elija un sistema disponible.")
