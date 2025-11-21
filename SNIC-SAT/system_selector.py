"""Selector de sistemas disponible tras el inicio de sesión."""
from __future__ import annotations

import streamlit as st

AVAILABLE_SYSTEMS = [
    {
        "id": "snic-sat",
        "label": "Sistema de carga Planilla SNIC-SAT",
        "description": "Ingreso y administración de planillas SNIC-SAT.",
        "icon": "🗂️",
    }
]


def render_system_selector() -> None:
    """Renderiza la pantalla para elegir el sistema activo."""

    st.title("Panel de sistemas DSICCO")
    st.caption("Seleccione el sistema con el que desea trabajar.")

    for system in AVAILABLE_SYSTEMS:
        with st.container():
            st.markdown(f"### {system['icon']} {system['label']}")
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
