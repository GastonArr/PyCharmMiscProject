import streamlit as st
from openpyxl import load_workbook, Workbook
import os

# ===== Utilidades Excel =====
def is_xlsm(path: str) -> bool:
    return path.lower().endswith(".xlsm")

def asegurar_excel(path: str):
    carpeta = os.path.dirname(path)
    if carpeta and not os.path.exists(carpeta):
        os.makedirs(carpeta, exist_ok=True)
    if not os.path.exists(path):
        wb = Workbook()
        ws = wb.active
        ws.title = "Hoja1"
        wb.save(path)

def cargar_libro(path: str):
    asegurar_excel(path)
    return load_workbook(path, keep_vba=is_xlsm(path))

def unwrap_quotes(v):
    """Quita SOLO comillas envolventes si existen; no toca espacios."""
    if not isinstance(v, str):
        return v
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v

# ===== Lógica de direcciones (UI + guardado + navegación) =====
def render_direcciones_ui(excel_path: str, fila: int, comisaria: str) -> None:
    """
    Pantalla de direcciones integrada al flujo principal (usa st.session_state.step).
    Guardados:
      - I{fila}: 'CUTRAL_CO' si comisaría 14/15; 'PLAZA_HUINCUL' si comisaría 6
      - J{fila}: barrio (lista según comisaría)
      - K{fila}: texto del barrio si se eligió 'OTRO'
      - L{fila}: dirección (textbox 30)
      - M{fila}: altura (textbox 30)
      - N{fila}: link de Google Maps (obligatorio, hasta 500 caracteres)
    No cambia formatos ni macros. Maneja Volver/Siguiente internamente.
    """

    # 1) Lista de barrios según comisaría
    barrios_1415 = [
        "PARQUE INDUSTRIAL","PARQUE OESTE","PARQUE ESTE","FILLI DEI","ZANI","SAN MARTIN",
        "AEROPARQUE","COOPERATIVA","D. SAEZ","PAMPA","CENTRO","RUCA QUIMEY","NEUQUEN CHE",
        "BELGRANO","PENI TRAPUN","BRENTANA","PROGRESO","UNION","25 DE MAYO",
        "PUEBLO NUEVO","MONTE HERMOSO C","OTRO"
    ]
    barrios_6 = [
        "25 DE MAYO","ALTOS DEL SUR","BOSCONI","CENTENARIO","CENTRAL","NOROESTE","NORTE",
        "OTANO","PARUQE INDUSTRIAL","SOUFAL","UNIVERSITARIO","UNO","ZONA INDUSTRIAL","OTRO"
    ]

    if comisaria in ("Comisaria 14", "Comisaria 15"):
        lista_barrios = barrios_1415
        ciudad_cod = "CUTRAL_CO"
    else:
        lista_barrios = barrios_6
        ciudad_cod = "PLAZA_HUINCUL"

    # Barrio
    barrio = st.selectbox("Ingrese el barrio", lista_barrios, key="dir_barrio_select")

    otro_barrio = ""
    if barrio == "OTRO":
        otro_barrio = st.text_input("Especifique otro barrio (máx 15)", max_chars=15, key="dir_otro_barrio")

    st.markdown("---")

    # 2) Dirección y altura
    col1, col2 = st.columns(2)
    with col1:
        direccion = st.text_input("Ingrese la dirección (máx 30)", max_chars=30, key="dir_direccion")
    with col2:
        altura = st.text_input("Ingrese la altura (máx 30)", max_chars=30, key="dir_altura")

    # 2.b) Link de Google Maps (OBLIGATORIO)
    st.markdown("---")
    link_maps = st.text_input(
        "ingresa a continuación el link de la página google maps donde se ubicó el punto geográfico de la dirección dada anteriormente.",
        max_chars=500,
        key="dir_link_maps",
        placeholder="https://maps.google.com/..."
    )

    st.markdown("---")

    # 3) Botones (controlan el flujo de la app principal)
    colA, colB = st.columns(2)
    with colA:
        if st.button("Volver ⬅️", key="dir_volver_btn"):
            st.session_state.step = 4  # vuelve a "día y hora" en app.py
            st.rerun()

    with colB:
        if st.button("Siguiente ➡️", key="dir_siguiente_btn"):
            # Validaciones mínimas
            if not barrio:
                st.warning("Seleccione un barrio.")
                st.stop()
            if barrio == "OTRO" and not otro_barrio:
                st.warning("Ingrese el nombre del barrio en 'OTRO'.")
                st.stop()
            if not direccion or direccion.strip() == "":
                st.warning("Ingrese la dirección.")
                st.stop()
            if not altura or altura.strip() == "":
                st.warning("Ingrese la altura.")
                st.stop()
            # Campo obligatorio: link de Google Maps
            if not link_maps or link_maps.strip() == "":
                st.warning("Debe ingresar el link de Google Maps.")
                st.stop()

            # Guardado en Excel
            try:
                wb = cargar_libro(excel_path)
                ws = wb.active

                # I{fila}: ciudad/código según comisaría
                ws[f"I{fila}"].value = ciudad_cod

                # J{fila}: barrio (si 'OTRO', además guarda el texto en K{fila})
                ws[f"J{fila}"].value = unwrap_quotes(barrio)
                if barrio == "OTRO":
                    ws[f"K{fila}"].value = unwrap_quotes(otro_barrio)

                # L{fila}: dirección ; M{fila}: altura
                ws[f"L{fila}"].value = unwrap_quotes(direccion)
                ws[f"M{fila}"].value = unwrap_quotes(altura)

                # N{fila}: link de Google Maps (obligatorio)
                ws[f"N{fila}"].value = unwrap_quotes(link_maps.strip())

                wb.save(excel_path)

                # Continuar con la app (Paso 6 en app.py: resumen + guardar)
                st.session_state.step = 6
                st.rerun()

            except PermissionError:
                st.error("⚠️ No se pudo guardar: archivo abierto con bloqueo de escritura en Excel.")
                st.stop()
            except Exception as e:
                st.error(f"⚠️ Error al escribir direcciones: {e}")
                st.stop()
