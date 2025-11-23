# paso3.py
import streamlit as st

def render_paso3(
    VINCULO_OPTIONS,
    CONVIVENCIA_OPTIONS,
    TIPO_OPTIONS,
    MODALIDAD_OPTIONS,
    TIEMPO_OPTIONS,
    FRECUENCIA_OPTIONS,
):
    st.subheader("Paso 3: Datos de la situación de violencia")

    st.selectbox(
        "Vínculo con el agresor (columna R)",
        VINCULO_OPTIONS,
        key="vinculo",
    )

    # Campo ahora persistente y obligatorio (controlado desde main.py)
    otro_v = st.text_input(
        "Otro vínculo (columna S)",
        value=st.session_state.get("otro_vinculo", ""),
    )
    st.session_state["otro_vinculo"] = otro_v

    st.selectbox(
        "Convivencia con el agresor (columna T)",
        CONVIVENCIA_OPTIONS,
        key="convivencia",
    )

    cols1 = st.columns(4)
    with cols1[0]:
        st.selectbox(
            "Violencia física (columna U)",
            TIPO_OPTIONS,
            key="viol_fisica",
        )
    with cols1[1]:
        st.selectbox(
            "Violencia psicológica (columna V)",
            TIPO_OPTIONS,
            key="viol_psico",
        )
    with cols1[2]:
        st.selectbox(
            "Violencia económica (columna W)",
            TIPO_OPTIONS,
            key="viol_econ",
        )
    with cols1[3]:
        st.selectbox(
            "Violencia sexual (columna X)",
            TIPO_OPTIONS,
            key="viol_sexual",
        )

    cols2 = st.columns(3)
    with cols2[0]:
        st.selectbox(
            "Modalidad de la violencia (columna Y)",
            MODALIDAD_OPTIONS,
            key="modalidad",
        )
    with cols2[1]:
        st.selectbox(
            "Tiempo del maltrato (columna Z)",
            TIEMPO_OPTIONS,
            key="tiempo",
        )
    with cols2[2]:
        st.selectbox(
            "Frecuencia de la violencia (columna AA)",
            FRECUENCIA_OPTIONS,
            key="frecuencia",
        )
