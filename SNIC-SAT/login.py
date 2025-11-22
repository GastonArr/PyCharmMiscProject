"""Login helpers and user configuration for the Streamlit SNIC app."""
from __future__ import annotations

import streamlit as st

COMISARIA_OPTIONS = [
    "Comisaria 14",
    "Comisaria 15",
    "Comisaria 6",
    "Comisaria 42",
    "Comisaria 9",
    "CENAF 4",
    "DTCCO-PH",
]

DEFAULT_SYSTEMS = ["snic-sat"]

USERS = {
    "Gaston": {
        "password": "10Capo555",
        "comisarias": COMISARIA_OPTIONS,
        "systems": ["snic-sat", "operativos-verano"],
    },
    "comisaria14": {
        "password": "comisaria14@",
        "comisarias": ["Comisaria 14"],
        "systems": DEFAULT_SYSTEMS,
    },
    "comisaria6": {
        "password": "comisaria6@",
        "comisarias": ["Comisaria 6"],
        "systems": DEFAULT_SYSTEMS,
    },
    "comisaria15": {
        "password": "comisaria15@",
        "comisarias": ["Comisaria 15"],
        "systems": DEFAULT_SYSTEMS,
    },
    "comisaria9": {
        "password": "comisaria9@",
        "comisarias": ["Comisaria 9"],
        "systems": ["snic-sat", "operativos-verano"],
    },
    "CENAF 4": {
        "password": "CENAF 4@",
        "comisarias": ["CENAF 4"],
        "systems": DEFAULT_SYSTEMS,
    },
    "comisaria42": {
        "password": "comisaria42@",
        "comisarias": ["Comisaria 42"],
        "systems": ["snic-sat", "operativos-verano"],
    },
    "DTCCO-PH": {
        "password": "DTCCO-PH@",
        "comisarias": ["DTCCO-PH"],
        "systems": ["operativos-verano"],
    },
}


def _comisaria_display(allowed: list[str] | None, current: str | None = None) -> str:
    if current:
        return current
    allowed = allowed or []
    if set(allowed) == set(COMISARIA_OPTIONS):
        return "Todas las comisarías"
    if allowed:
        return allowed[0]
    return "Sin comisaría asignada"


def render_login() -> None:
    """Draw the login form and authenticate valid users."""

    st.title("Ingreso al sistema DSI-CCO")
    st.subheader("Ingrese sus credenciales para continuar")
    with st.form("login_form"):
        username_input = st.text_input("Usuario")
        password_input = st.text_input("Clave", type="password")
        submitted = st.form_submit_button("Ingresar")

    if submitted:
        username = username_input.strip()
        user_data = USERS.get(username)
        if user_data and password_input == user_data.get("password"):
            allowed = list(user_data.get("comisarias", []))
            systems = list(user_data.get("systems") or DEFAULT_SYSTEMS)
            st.session_state.clear()
            st.session_state.authenticated = True
            st.session_state.username = username
            st.session_state.allowed_comisarias = allowed
            st.session_state.allowed_systems = systems
            st.session_state.step = 1
            st.session_state.selected_system = None
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos. Verifique e intente nuevamente.")


def render_user_header() -> None:
    """Show the active user banner with logout support."""

    allowed = st.session_state.get("allowed_comisarias") or []
    current = st.session_state.get("comisaria")
    comisaria_label = _comisaria_display(allowed, current=current)
    system_label = st.session_state.get("selected_system_label") or "Sin sistema seleccionado"
    col_info, col_logout = st.columns([4, 1])
    with col_info:
        st.success(
            f"👮 Usuario: {st.session_state.get('username', 'Desconocido')} — Comisaría: {comisaria_label} — Sistema: {system_label}"
        )
    with col_logout:
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()
