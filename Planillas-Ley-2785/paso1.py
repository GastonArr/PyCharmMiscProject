# paso1.py
import streamlit as st
import datetime as dt

def render_paso1(UNIDADES_JURISDICCION, DOCUMENTO_OPTIONS):
    st.subheader("Paso 1: Unidad y datos básicos")

    # ==========================
    # Unidad / Institución (columna F)
    # ==========================
    current_institucion = st.session_state.get("institucion", UNIDADES_JURISDICCION[0])
    try:
        institucion_index = UNIDADES_JURISDICCION.index(current_institucion)
    except ValueError:
        institucion_index = 0

    selected_unidad = st.selectbox(
        "Unidad / Institución (columna F)",
        UNIDADES_JURISDICCION,
        index=institucion_index,
        help="Solo se muestran las unidades de la jurisdicción.",
    )
    st.session_state["institucion"] = selected_unidad

    # ==========================
    # Tipo de documento (columna C)
    # ==========================
    current_tipo_doc = st.session_state.get("tipo_documento", DOCUMENTO_OPTIONS[0])
    try:
        tipo_doc_index = DOCUMENTO_OPTIONS.index(current_tipo_doc)
    except ValueError:
        tipo_doc_index = 0

    selected_tipo_doc = st.selectbox(
        "Tipo de documento (columna C)",
        DOCUMENTO_OPTIONS,
        index=tipo_doc_index,
    )
    st.session_state["tipo_documento"] = selected_tipo_doc

    # ==========================
    # Identificación / N° documento (columna E)
    # ==========================
    identificacion = st.text_input(
        "Identificación / N° documento (columna E)",
        value=st.session_state.get("identificacion", ""),
    )
    st.session_state["identificacion"] = identificacion

    # ==========================
    # Fecha de consulta (columna G)
    # ==========================
    st.date_input(
        "Fecha de consulta (columna G)",
        key="fecha_consulta",
        value=st.session_state.get("fecha_consulta", dt.date.today()),
    )