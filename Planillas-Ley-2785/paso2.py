# paso2.py
import streamlit as st

def render_paso2(
    SEXO1_OPTIONS,
    TRANS1_OPTIONS,
    EDUCACION1_OPTIONS,
    COMPLITUD1_OPTIONS,
    OCUPADA1_OPTIONS,
    ACTIVIDAD1_OPTIONS,
):
    st.subheader("Paso 2: Datos de la persona consultante")

    # Tipo de documento (C) y Identificación (E) se movieron al Paso 1
    # Columna D (Otro documento) se elimina del formulario

    cols1 = st.columns(2)
    with cols1[0]:
        st.selectbox("Sexo (columna H)", SEXO1_OPTIONS, key="sexo1")
    with cols1[1]:
        st.selectbox("Identidad trans (columna I)", TRANS1_OPTIONS, key="trans1")

    cols2 = st.columns(2)
    with cols2[0]:
        edad = st.number_input(
            "Edad (columna J)",
            min_value=0,
            max_value=120,
            step=1,
            value=st.session_state.get("edad", 0),
        )
        st.session_state["edad"] = edad
    with cols2[1]:
        provincia = st.text_input(
            "Provincia (columna K)",
            value=st.session_state.get("provincia", ""),
        )
        st.session_state["provincia"] = provincia

    cols3 = st.columns(3)
    with cols3[0]:
        localidad = st.text_input(
            "Localidad (columna M)",
            value=st.session_state.get("localidad", ""),
        )
        st.session_state["localidad"] = localidad
    with cols3[1]:
        st.selectbox(
            "Nivel educativo (columna N)",
            EDUCACION1_OPTIONS,
            key="nivel_educativo1",
        )
    with cols3[2]:
        st.selectbox(
            "Complitud del nivel educativo (columna O)",
            COMPLITUD1_OPTIONS,
            key="complitud1",
        )

    cols4 = st.columns(2)
    with cols4[0]:
        st.selectbox(
            "Situación ocupacional (columna P)",
            OCUPADA1_OPTIONS,
            key="ocupada1",
        )
    with cols4[1]:
        st.selectbox(
            "Actividad (columna Q)",
            ACTIVIDAD1_OPTIONS,
            key="actividad1",
        )
