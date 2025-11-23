# paso4.py
import streamlit as st

def render_paso4(
    SEXO2_OPTIONS,
    TRANS2_OPTIONS,
    EDUCACION2_OPTIONS,
    COMPLITUD2_OPTIONS,
    ACTIVIDAD2_OPTIONS,
    OTRA2_OPTIONS,
    STEP_REQUIRED,
    REQUIRED_FIELDS,
    FIELD_LABELS,
    find_missing_in_state,
    build_form_data_from_state,
    save_to_excel,
    reset_form,
    agenda_context=None,
):
    st.subheader("Paso 4: Datos del agresor y observaciones")

    referencia = ""
    if isinstance(agenda_context, dict):
        referencia = agenda_context.get("referencia") or ""
    if referencia:
        st.info(
            f"Referencia del hecho (Información específica AI): {referencia}",
            icon="🗂️",
        )

    cols = st.columns(3)
    with cols[0]:
        st.selectbox("Sexo agresor (AB)", SEXO2_OPTIONS, key="sexo2")
    with cols[1]:
        st.selectbox("Trans agresor (AC)", TRANS2_OPTIONS, key="trans2")
    with cols[2]:
        edadA = st.number_input(
            "Edad agresor (AD)",
            min_value=0, max_value=120, step=1,
            value=st.session_state.get("edad_agresor", 0)
        )
        st.session_state["edad_agresor"] = edadA

    cols2 = st.columns(3)
    with cols2[0]:
        st.selectbox("Educación agresor (AE)", EDUCACION2_OPTIONS, key="nivel_educativo2")
    with cols2[1]:
        st.selectbox("Complitud agresor (AF)", COMPLITUD2_OPTIONS, key="complitud2")
    with cols2[2]:
        st.selectbox("Actividad agresor (AG)", ACTIVIDAD2_OPTIONS, key="actividad2")

    st.selectbox("Otra actividad agresor (AH)", OTRA2_OPTIONS, key="otra_actividad2")
    st.text_area("Información específica (AI)", key="info_especifica", height=150)
    st.text_input("Fecha modificación (AJ)", key="fecha_modificacion")

    st.markdown("---")

    if st.button("💾 Guardar registro"):
        required = STEP_REQUIRED[4]
        missing = find_missing_in_state(required)

        if missing:
            labels = [FIELD_LABELS[k] for k in missing]
            st.error("Faltan:\n- " + "\n- ".join(labels))
            return

        missing2 = find_missing_in_state(REQUIRED_FIELDS)
        if missing2:
            labels = [FIELD_LABELS.get(k, k) for k in missing2]
            st.error("No se puede guardar, faltan:\n- " + "\n- ".join(labels))
            return

        data = build_form_data_from_state()
        unidad = data["institucion"]

        try:
            num, archivo = save_to_excel(unidad, data)
            st.success(f"Registro guardado con Nº {num}\nArchivo: {archivo}")
            if isinstance(agenda_context, dict) and agenda_context.get("registrar"):
                registrar = agenda_context.get("registrar")
                fecha = agenda_context.get("fecha")
                hecho_id = agenda_context.get("hecho_id")
                ok_agenda, msg_agenda, _ = registrar(unidad, fecha, hecho_id)
                if not ok_agenda:
                    st.warning(msg_agenda or "No se pudo actualizar el almanaque del día.")
            reset_form()
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
