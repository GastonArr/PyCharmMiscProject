"""Selector de sistemas disponible tras el inicio de sesión."""
from __future__ import annotations

import streamlit as st

SYSTEM_SNICSAT_ID = "snic-sat"
SYSTEM_OPERATIVOS_VERANO_ID = "operativos-verano"

AVAILABLE_SYSTEMS = [
    {
        "id": SYSTEM_SNICSAT_ID,
        "label": "Planillas SNIC-SAT.",
        "description": "Ingreso y administración de planillas.",
        "icon": "🗂️",
    },
    {
        "id": SYSTEM_OPERATIVOS_VERANO_ID,
        "label": "Planillas Operativo Verano",
        "description": "Carga de anexos y seguimiento diario de operativos.",
        "icon": "🏖️",
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

    systems_to_show = [
        system
        for system in AVAILABLE_SYSTEMS
        if not allowed_systems or system.get("id") in allowed_systems
    ]

    if not systems_to_show:
        st.warning(
            "Su usuario no tiene sistemas habilitados. Contacte al administrador del sistema."
        )
        return

    for system in systems_to_show:
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
