import streamlit as st
from openpyxl import load_workbook, Workbook
import os
import datetime
import direcciones          # módulo externo para pantalla de direcciones
import Robos_Hurtos         # subflujo para delitos Robos/Hurtos
import otros                # subflujo para Lesiones / Desaparición

# ===========================
# Config de rutas (en el repo)
# ===========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DIR = os.path.join(BASE_DIR, "excel")  # carpeta local en el repo
os.makedirs(EXCEL_DIR, exist_ok=True)

# Bases SIN extensión (usamos resolve_excel_path para elegir .xlsm/.xlsx/.xls)
excel_base_comisaria_14 = os.path.join(EXCEL_DIR, "comisaria 14")
excel_base_comisaria_15 = os.path.join(EXCEL_DIR, "comisaria 15")
excel_base_comisaria_6  = os.path.join(EXCEL_DIR, "comisaria 6")

# ---------------------------
# Utilidades
# ---------------------------

def is_xlsm(path: str) -> bool:
    return path.lower().endswith(".xlsm")

def resolve_excel_path(base_without_ext: str) -> str:
    """
    Devuelve el archivo existente entre: .xlsm, .xlsx, .xls (en ese orden).
    Si no existe ninguno, devuelve base + '.xlsm'.
    """
    for ext in (".xlsm", ".xlsx", ".xls"):
        cand = base_without_ext + ext
        if os.path.exists(cand):
            return cand
    return base_without_ext + ".xlsm"

def asegurar_excel(path: str):
    """
    Crea el archivo si no existe (xlsx o xlsm según la extensión).
    No crea macros; si el archivo ya tiene macros, se conservarán con keep_vba=True al cargar/guardar.
    """
    carpeta = os.path.dirname(path)
    if carpeta and not os.path.exists(carpeta):
        os.makedirs(carpeta, exist_ok=True)
    if not os.path.exists(path):
        wb = Workbook()
        ws = wb.active
        ws.title = "Hoja1"
        wb.save(path)

def cargar_libro(path: str):
    """
    Carga el libro respetando macros si es .xlsm.
    """
    asegurar_excel(path)
    return load_workbook(path, keep_vba=is_xlsm(path))

def obtener_siguiente_fila_por_fecha(path: str, col_fecha: str = "C") -> int:
    """
    Busca la primera fila vacía en la columna de fecha (C por defecto) a partir de la fila 3.
    """
    wb = cargar_libro(path)
    ws = wb.active
    fila = 3
    while True:
        val = ws[f"{col_fecha}{fila}"].value
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return fila
        fila += 1

def unwrap_quotes(v):
    if not isinstance(v, str):
        return v
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v

def fecha_a_texto_curvo(fecha: datetime.date) -> str:
    if not isinstance(fecha, datetime.date):
        return None
    return fecha.strftime("%d/%m/%y")

def escribir_registro(path: str, fila: int, hecho, delito,
                      actuacion, fecha_denuncia_txt, fecha_hecho_txt,
                      hora_hecho_txt, hora_fin_txt, preventivo_txt,
                      denunciante_txt, motivo_txt):
    """
    Escribe datos en: C,D,E,F,H,Q,AF,BL,X,R (sin tocar A).
    """
    wb = cargar_libro(path)
    ws = wb.active
    try:
        ws[f"C{fila}"].value  = fecha_denuncia_txt
        ws[f"D{fila}"].value  = fecha_hecho_txt
        ws[f"E{fila}"].value  = hora_hecho_txt
        ws[f"F{fila}"].value  = hora_fin_txt
        ws[f"H{fila}"].value  = unwrap_quotes(preventivo_txt)
        ws[f"Q{fila}"].value  = unwrap_quotes(denunciante_txt)
        ws[f"AF{fila}"].value = unwrap_quotes(motivo_txt)
        ws[f"BL{fila}"].value = unwrap_quotes(hecho)
        ws[f"X{fila}"].value  = unwrap_quotes(delito)
        ws[f"R{fila}"].value  = unwrap_quotes(actuacion)
        wb.save(path)
        return True
    except PermissionError:
        st.error("⚠️ No se pudo guardar porque el archivo está abierto en Excel con bloqueo de escritura. Cerrá el archivo y probá de nuevo.")
        return False
    except Exception as e:
        st.error(f"⚠️ No se pudo escribir en {path}: {e}")
        return False

def mostrar_hecho():
    if st.session_state.get("hecho"):
        st.subheader("Hecho ingresado para referencia:")
        st.write(st.session_state.hecho)

def excel_path_por_comisaria(nombre_comisaria: str) -> str:
    """
    Devuelve el path del Excel (con extensión) según la comisaría seleccionada,
    resolviendo la extensión existente o creando .xlsm si no hay.
    """
    if nombre_comisaria == "Comisaria 14":
        base = excel_base_comisaria_14
    elif nombre_comisaria == "Comisaria 15":
        base = excel_base_comisaria_15
    else:
        base = excel_base_comisaria_6
    return resolve_excel_path(base)

# ---------------------------
# Estado de sesión
# ---------------------------

def _init_state():
    d = st.session_state
    d.setdefault("step", 1)
    d.setdefault("comisaria", None)
    d.setdefault("delito", None)
    d.setdefault("hecho", None)
    d.setdefault("actuacion", None)
    d.setdefault("excel_path", None)
    d.setdefault("fila", None)
    d.setdefault("fecha_denuncia", None)
    d.setdefault("fecha_hecho", None)
    d.setdefault("hora_hecho", None)
    d.setdefault("hora_fin", None)
    d.setdefault("preventivo", "")
    d.setdefault("denunciante", "")
    d.setdefault("motivo", "")
    # Subflujos
    d.setdefault("rh_done", False)
    d.setdefault("rh_preview", None)       # resumen Robos/Hurtos
    d.setdefault("others_done", False)
    d.setdefault("others_preview", None)   # resumen Otros (Lesiones/Desap)

_init_state()

# ---------------------------
# UI por pasos
# ---------------------------

if st.session_state.step == 1:
    st.title("CARGA DE SNIC")
    st.subheader("Seleccione la comisaría en la que desea trabajar:")

    comisaria = st.selectbox(
        "Seleccione la comisaría",
        ["Comisaria 14", "Comisaria 15", "Comisaria 6"]
    )

    # --- Botón Descargar Excel + Uploader con validación de nombre ---
    col_dl, col_next = st.columns([1,1])

    with col_dl:
        excel_path_preview = excel_path_por_comisaria(comisaria)
        asegurar_excel(excel_path_preview)

        # Detectar MIME según extensión
        _ext = os.path.splitext(excel_path_preview)[1].lower()
        if _ext == ".xlsm":
            mime = "application/vnd.ms-excel.sheet.macroEnabled.12"
        elif _ext == ".xlsx":
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:  # .xls u otro
            mime = "application/vnd.ms-excel"

        try:
            with open(excel_path_preview, "rb") as f:
                excel_bytes = f.read()
            st.download_button(
                label="📥 Descargar Excel",
                data=excel_bytes,
                file_name=os.path.basename(excel_path_preview),
                mime=mime,
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"⚠️ No se pudo preparar la descarga: {e}")

        # Uploader: exige que el nombre del archivo subido sea EXACTAMENTE el esperado
        st.markdown("— o —")
        expected_name = os.path.basename(excel_path_preview)
        uploaded = st.file_uploader(
            f"Subir/Reemplazar Excel (nombre requerido: **{expected_name}**)",
            type=["xlsm", "xlsx", "xls"],
            key="uploader_excel"
        )
        if uploaded is not None:
            if uploaded.name != expected_name:
                st.error(f"El archivo debe llamarse **{expected_name}**. Renombralo y volvé a subirlo para evitar conflictos.")
            else:
                # Guardar lo subido SOBRE el archivo target
                try:
                    with open(excel_path_preview, "wb") as f:
                        f.write(uploaded.getbuffer())
                    st.success(f"Se reemplazó el Excel de {comisaria}: {expected_name}")
                except Exception as e:
                    st.error(f"No se pudo guardar el archivo: {e}")

    with col_next:
        if st.button("Siguiente", use_container_width=True):
            st.session_state.comisaria = comisaria
            st.session_state.excel_path = excel_path_por_comisaria(comisaria)
            st.session_state.fila = obtener_siguiente_fila_por_fecha(st.session_state.excel_path, col_fecha="C")

            # reset subflujos
            st.session_state.rh_done = False
            st.session_state.rh_preview = None
            st.session_state.others_done = False
            st.session_state.others_preview = None

            st.session_state.step = 2
            st.rerun()

elif st.session_state.step == 2:
    mostrar_hecho()
    st.subheader(f"Usted seleccionó la {st.session_state.comisaria}")
    st.caption(f"Próximo registro: fila {st.session_state.fila}")

    hecho = st.text_area(
        "Indique el hecho (copie tal cual del MEMORANDUM):",
        height=150,
        value=st.session_state.hecho or ""
    )
    preventivo = st.text_input(
        "Ingrese el número de preventivo (máx 20 caracteres)",
        value=st.session_state.preventivo or "",
        max_chars=20
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Volver"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Siguiente"):
            if not hecho or hecho.strip() == "":
                st.warning("Por favor, ingrese el hecho antes de continuar.")
                st.stop()
            if not preventivo or preventivo.strip() == "":
                st.warning("Por favor, ingrese el número de preventivo.")
                st.stop()
            st.session_state.hecho = hecho
            st.session_state.preventivo = preventivo
            st.session_state.step = 3
            st.rerun()

elif st.session_state.step == 3:
    mostrar_hecho()
    st.subheader("Indique el delito que desea cargar")

    delitos = [
        "ROBO SIMPLE ",
        "HURTO SIMPLE ",
        "A CONSIDERACION",
        "ABUSO DE ARMAS CON LESIONES",
        "ABUSO DE ARMAS SIN LESIONES" + " ",
        "AMENAZAS CALIFICADA POR EL USO DE ARMAS",
        "AMENAZAS OTRAS",
        "AMENAZAS SIMPLE (ALARMAR O AMEDRENTAR)",
        "DAÑOS (NO INCLUYE INFORMATICOS)",
        "DESOBEDIENCIA DE UNA ORDEN JUDICIAL",
        "ENCUBRIMIENTO" + " ",
        "ESTAFAS Y DEFRAUDACIONES VIRTUALES",
        "ESTAFAS, DEFRAUDACIONES,USURA y USURPACION (NO INCLUYE VIRTUALES)",
        "FALSIFICACION DE MONEDA, BILLETES DE BANCO, TITULO AL PORTADOR Y DOCUMENTOS DE CREDITO",
        "HOMICIDIO EN GRADO DE TENTATIVA",
        "HOMICIDIO SIMPLE",
        "HURTO EN GRADO DE TENTATIVA" + " ",
        "LESIONES GRAVES",
        "LESIONES LEVES",
        "LESIONES GRAVISIMAS",
        "OTROS DELITOS CONTRA LA LIBERTAD INDIVIDUAL" + " ",
        "OTROS INCENDIOS O ESTRAGOS",
        "ROBO ABIGEATO" + " ",
        "ROBO AGRAVADO POR EL USO DE ARMA DE ARMA BLANCA",
        "ROBO AGRAVADO POR EL USO DE ARMA DE FUEGO",
        "ROBO EN GRADO TENTATIVA" + " ",
        "SUICIDIO_(CONSUMADO)",
        "TENENCIA ILEGAL DE ARMAS DE FUEGO",
        "VIOLACION DE DOMICILIO SIMPLE" + " ",
        "ABUSO SEXUAL CON ACCESO CARNAL (VIOLACION)" + " ",
        "ABUSO SEXUAL SIMPLE",
        "DESAPARICION DE PERSONA",
    ]
    delitos = sorted(delitos, key=lambda s: s.casefold())
    delito = st.selectbox(
        "Seleccione el delito",
        delitos,
        index=(delitos.index(st.session_state.delito) if st.session_state.delito in delitos else 0),
    )

    denunciante = st.text_input(
        "Indique el nombre y apellido del denunciante o víctima",
        value=st.session_state.denunciante or "",
        max_chars=100
    )
    motivos = [
        "DENUNCIA PARTICULAR",
        "INTERVENCIÓN POLICIAL",
        "ORDEN JUDICIAL",
        "OTROS/ NO CONSTA",
    ]
    motivo_sel = st.selectbox(
        "Motivo que origina el registro del hecho",
        motivos,
        index=(motivos.index(st.session_state.motivo) if st.session_state.motivo in motivos else 0),
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Volver"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("Siguiente"):
            if not denunciante or denunciante.strip() == "":
                st.warning("Por favor, ingrese el nombre y apellido del denunciante o víctima.")
                st.stop()
            st.session_state.delito = delito
            st.session_state.denunciante = denunciante
            st.session_state.motivo = motivo_sel
            st.session_state.step = 4
            st.rerun()

elif st.session_state.step == 4:
    mostrar_hecho()
    st.subheader("Indique el tipo de actuación")

    delito_actual = (st.session_state.delito or "").strip()
    if delito_actual == "A CONSIDERACION":
        opciones_actuacion = ["A CONSIDERACION"]
        st.session_state.actuacion = "A CONSIDERACION"
        st.caption("Por haber seleccionado el delito 'A CONSIDERACION', la actuación queda fijada en 'A CONSIDERACION'.")
    else:
        opciones_actuacion = ["ABREVIADA", "CONVENCIONAL"]
        if st.session_state.actuacion not in opciones_actuacion:
            st.session_state.actuacion = "ABREVIADA"

    actuacion = st.radio(
        "Seleccione una opción",
        opciones_actuacion,
        index=(opciones_actuacion.index(st.session_state.actuacion)
               if st.session_state.actuacion in opciones_actuacion else 0),
        key="actuacion_radio"
    )
    st.session_state.actuacion = actuacion

    st.subheader("Ingrese el día y hora")

    st.markdown("**Fecha de denuncia/intervención:**")
    fecha_denuncia = st.date_input(
        "Fecha de denuncia/intervención",
        value=st.session_state.fecha_denuncia or datetime.date.today(),
        key="fecha_denuncia_input"
    )
    st.session_state.fecha_denuncia = fecha_denuncia

    st.markdown("**Fecha del hecho:**")
    fecha_hecho = st.date_input(
        "Fecha del hecho",
        value=st.session_state.fecha_hecho or datetime.date.today(),
        key="fecha_hecho_input"
    )
    st.session_state.fecha_hecho = fecha_hecho

    opciones_hora = [f"{h:02d}:00" for h in range(24)]
    opciones_hora_con_ind = ["INDETERMINADO"] + opciones_hora

    col_h1, col_h2 = st.columns(2)
    with col_h1:
        st.markdown("**Horario del hecho:**")
        hora_hecho = st.selectbox(
            "Horario del hecho",
            opciones_hora_con_ind,
            index=(opciones_hora_con_ind.index(st.session_state.hora_hecho)
                   if st.session_state.hora_hecho in opciones_hora_con_ind else 0),
            key="hora_hecho_select"
        )
        st.session_state.hora_hecho = hora_hecho

    with col_h2:
        st.markdown("**Horario fin del hecho:**")
        hora_fin = st.selectbox(
            "Horario fin del hecho",
            opciones_hora_con_ind,
            index=(opciones_hora_con_ind.index(st.session_state.hora_fin)
                   if st.session_state.hora_fin in opciones_hora_con_ind else 0),
            key="hora_fin_select"
        )
        st.session_state.hora_fin = hora_fin

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Volver"):
            st.session_state.step = 3
            st.rerun()
    with col2:
        if st.button("Siguiente"):
            st.session_state.step = 5
            st.rerun()

elif st.session_state.step == 5:
    # Direcciones SIEMPRE
    mostrar_hecho()
    direcciones.render_direcciones_ui(
        st.session_state.excel_path,
        st.session_state.fila,
        st.session_state.comisaria
    )
    # La función interna maneja volver (step=4) y continuar (step=6).

elif st.session_state.step == 6:
    # --- Subflujo: Lesiones / Desaparición de Persona (otros.py) ---
    delitos_otros = {
        "LESIONES GRAVES", "LESIONES LEVES", "LESIONES GRAVISIMAS",
        "DESAPARICION DE PERSONA",
        "ABUSO SEXUAL CON ACCESO CARNAL (VIOLACION)",
        "ABUSO SEXUAL SIMPLE",
    }
    delito_norm_otros = (st.session_state.delito or "").strip()
    if (delito_norm_otros in delitos_otros) and not st.session_state.get("others_done", False):
        otros.render(
            excel_path=st.session_state.excel_path,
            fila=st.session_state.fila,
            delito_x3=st.session_state.delito
        )
        st.stop()

    # --- Subflujo: Robos / Hurtos (Robos_Hurtos.py) ---
    delitos_rh = {
        "ROBO SIMPLE ",
        "HURTO SIMPLE ",
        "ROBO AGRAVADO POR EL USO DE ARMA DE ARMA BLANCA",
        "ROBO AGRAVADO POR EL USO DE ARMA DE FUEGO",
        "ROBO ABIGEATO ",
        "ROBO AGRAVADO POR LESION ",
    }
    if ((st.session_state.delito in delitos_rh) or ((st.session_state.delito or "").strip() in {d.strip() for d in delitos_rh})) \
       and not st.session_state.get("rh_done", False):
        Robos_Hurtos.render(
            excel_path=st.session_state.excel_path,
            fila=st.session_state.fila,
            delito_x3=st.session_state.delito
        )
        st.stop()

    # ----- Vista previa antes de guardar -----
    mostrar_hecho()
    st.subheader("Vista previa de lo ingresado")

    # Bloque general
    st.markdown("**Datos generales**")
    st.write(f"- Comisaría: {st.session_state.comisaria}")
    st.write(f"- Fila de escritura: {st.session_state.fila}")
    st.write(f"- Delito: {st.session_state.delito}")
    st.write(f"- Actuación: {st.session_state.actuacion}")
    st.write(f"- Fecha denuncia/intervención: {st.session_state.fecha_denuncia}")
    st.write(f"- Fecha del hecho: {st.session_state.fecha_hecho}")
    st.write(f"- Hora del hecho: {st.session_state.hora_hecho}")
    st.write(f"- Hora fin del hecho: {st.session_state.hora_fin}")
    st.write(f"- N° de preventivo: {st.session_state.preventivo}")
    st.write(f"- Denunciante/Víctima: {st.session_state.denunciante}")
    st.write(f"- Motivo: {st.session_state.motivo}")

    # Bloque Lesiones / Desaparición (si hay)
    otros_preview = st.session_state.get("others_preview")
    if otros_preview:
        st.markdown("---")
        st.markdown("**Datos adicionales (Lesiones / Desaparición)**")
        vict_rows_o = otros_preview.get("vict_rows") or []
        if vict_rows_o:
            st.write("• Víctimas por sexo:")
            for r in vict_rows_o:
                st.write(f"  - {r.get('sexo')}: {r.get('cant')}")
            st.write(f"  - **Total (AO)**: {otros_preview.get('vict_total')}")
        st.write(f"• Vulnerabilidad (AP): {otros_preview.get('vulnerabilidad')}")
        if otros_preview.get("aparecio") is not None:
            st.write(f"• ¿Apareció? (BA): {otros_preview.get('aparecio')}")

        # Botón para editar subflujo Otros
        if st.button("Editar Lesiones/Desaparición"):
            st.session_state.others_done = False
            st.rerun()

    # Bloque Robos/Hurtos (si hay)
    rh_preview = st.session_state.get("rh_preview")
    if rh_preview:
        st.markdown("---")
        st.markdown("**Datos adicionales (Robos/Hurtos)**")
        # Víctimas
        vict_rows = rh_preview.get("vict_rows") or []
        vict_total = rh_preview.get("vict_total")
        if vict_rows:
            st.write("• Víctimas por sexo:")
            for r in vict_rows:
                st.write(f"  - {r.get('sexo')}: {r.get('cant')}")
            st.write(f"  - **Total (AO)**: {vict_total}")
        # Vulnerabilidad, arma
        st.write(f"• Vulnerabilidad: {rh_preview.get('vulnerab')}")
        st.write(f"• Tipo de arma (AR): {rh_preview.get('tipo_arma')}")
        # Inculpados
        if rh_preview.get("inc_sn") == "SI":
            st.write("• Inculpados: SI")
            st.write(f"  - Rango etario: {rh_preview.get('rango_etario')} ({rh_preview.get('cant_rango')})")
            sex_rows = rh_preview.get("sex_rows") or []
            if sex_rows:
                st.write(f"  - Distribución por sexo:")
                for r in sex_rows:
                    st.write(f"    · {r.get('sexo')}: {r.get('cant')}")
        else:
            st.write("• Inculpados: NO")
        # Tipo de lugar y detalle
        st.write(f"• Tipo de lugar (AD): {rh_preview.get('tipo_lugar')}")
        if rh_preview.get("detalle_est"):
            st.write(f"  - Detalle establecimiento (AE): {rh_preview.get('detalle_est')}")
        # Elementos sustraídos y subdetalles
        st.write(f"• Elementos sustraídos (BB): {rh_preview.get('elem')}")
        if rh_preview.get("subcat"):
            st.write(f"  - Subcategoría (BC): {rh_preview.get('subcat')}")
        if rh_preview.get("denom"):
            st.write(f"  - Denominación (BD): {rh_preview.get('denom')}")
        if rh_preview.get("anio") or rh_preview.get("modelo"):
            st.write(f"  - Año (BE) / Modelo (BF): {rh_preview.get('anio')} / {rh_preview.get('modelo')}")
        # Modus y especialidad
        st.write(f"• Modus operandi (BJ): {rh_preview.get('modus')}")
        if rh_preview.get("especialidad"):
            st.write(f"  - Especialidad (BK): {rh_preview.get('especialidad')}")

        # Botón para editar Robos/Hurtos
        if st.button("Editar Robos/Hurtos"):
            st.session_state.rh_done = False
            st.rerun()

    st.markdown("---")
    st.subheader("Guardar y finalizar")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Atrás"):
            # Reabrir subflujos si ya fueron completados
            if (delito_norm_otros in delitos_otros) and st.session_state.get("others_done", False):
                st.session_state.others_done = False
                st.rerun()
            elif ((st.session_state.delito in delitos_rh) or ((st.session_state.delito or "").strip() in {d.strip() for d in delitos_rh})) \
                 and st.session_state.get("rh_done", False):
                st.session_state.rh_done = False
                st.rerun()
            else:
                st.session_state.step = 4
                st.rerun()

    with col2:
        if st.button("Finalizar y guardar ✅"):
            fila = obtener_siguiente_fila_por_fecha(st.session_state.excel_path, col_fecha="C")

            fecha_den_txt = fecha_a_texto_curvo(st.session_state.fecha_denuncia) if st.session_state.fecha_denuncia else None
            fecha_hecho_txt = fecha_a_texto_curvo(st.session_state.fecha_hecho) if st.session_state.fecha_hecho else None
            hora_hecho_txt = st.session_state.hora_hecho or "INDETERMINADO"
            hora_fin_txt   = st.session_state.hora_fin or "INDETERMINADO"

            ok = escribir_registro(
                st.session_state.excel_path,
                fila,
                st.session_state.hecho,
                st.session_state.delito,
                st.session_state.actuacion,
                fecha_den_txt,
                fecha_hecho_txt,
                hora_hecho_txt,
                hora_fin_txt,
                st.session_state.preventivo,   # H
                st.session_state.denunciante,  # Q
                st.session_state.motivo        # AF
            )

            if ok:
                st.success(f"Datos guardados en {st.session_state.comisaria} (fila {fila}) ✅")
                # Reset total
                st.session_state.step = 1
                st.session_state.hecho = None
                st.session_state.delito = None
                st.session_state.actuacion = None
                st.session_state.fila = None
                st.session_state.fecha_denuncia = None
                st.session_state.fecha_hecho = None
                st.session_state.hora_hecho = None
                st.session_state.hora_fin = None
                st.session_state.preventivo = None
                st.session_state.denunciante = None
                st.session_state.motivo = None
                st.session_state.rh_done = False
                st.session_state.rh_preview = None
                st.session_state.others_done = False
                st.session_state.others_preview = None
                st.rerun()
            else:
                st.error("Hubo un problema al guardar. Revise el mensaje de error arriba.")