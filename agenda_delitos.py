import datetime
import html
import json
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from gcs_utils import blob_exists, load_json_from_gcs, save_json_to_gcs
from login import COMISARIA_OPTIONS

# ===========================
# Configuración básica
# ===========================

AGENDA_PATH = "agenda_delitos.json"

# Usuarios administradores explícitos. Se complementa con el chequeo de comisarías completas.
ADMIN_USERS = {"Gaston"}

# Lista única de delitos disponibles. Se replica el listado de app.py para centralizarlo aquí.
DELITOS_DISPONIBLES: List[str] = sorted([
    "ROBO SIMPLE ",
    "HURTO SIMPLE ",
    "A CONSIDERACION",
    "ABUSO DE ARMAS CON LESIONES",
    "ABUSO DE ARMAS SIN LESIONES ",
    "AMENAZAS CALIFICADA POR EL USO DE ARMAS",
    "AMENAZAS OTRAS",
    "AMENAZAS SIMPLE (ALARMAR O AMEDRENTAR)",
    "DAÑOS (NO INCLUYE INFORMATICOS)",
    "DESOBEDIENCIA DE UNA ORDEN JUDICIAL",
    "ENCUBRIMIENTO ",
    "ESTAFAS Y DEFRAUDACIONES VIRTUALES",
    "ESTAFAS, DEFRAUDACIONES,USURA y USURPACION (NO INCLUYE VIRTUALES)",
    "FALSIFICACION DE MONEDA, BILLETES DE BANCO, TITULO AL PORTADOR Y DOCUMENTOS DE CREDITO",
    "HOMICIDIO EN GRADO DE TENTATIVA",
    "HOMICIDIO SIMPLE",
    "HURTO EN GRADO DE TENTATIVA ",
    "LESIONES GRAVES",
    "LESIONES LEVES",
    "LESIONES GRAVISIMAS",
    "OTROS DELITOS CONTRA LA LIBERTAD INDIVIDUAL ",
    "OTROS INCENDIOS O ESTRAGOS",
    "ROBO ABIGEATO ",
    "ROBO AGRAVADO POR EL USO DE ARMA DE ARMA BLANCA",
    "ROBO AGRAVADO POR EL USO DE ARMA DE FUEGO",
    "ROBO EN GRADO TENTATIVA ",
    "SUICIDIO_(CONSUMADO)",
    "TENENCIA ILEGAL DE ARMAS DE FUEGO",
    "VIOLACION DE DOMICILIO SIMPLE ",
    "ABUSO SEXUAL CON ACCESO CARNAL (VIOLACION) ",
    "ABUSO SEXUAL SIMPLE",
    "DESAPARICION DE PERSONA",
    "ATENTADO Y RESISTENCIA CONTRA LA AUTORIDAD ",
], key=lambda s: s.casefold())


# ===========================
# Utilidades internas
# ===========================

AgendaData = Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]


def _normalize_preventivo(value: Optional[Any]) -> Optional[str]:
    """Normaliza el texto del preventivo eliminando espacios y vacíos."""

    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def _normalize_preventivo_list(values: Optional[Any]) -> List[Optional[str]]:
    """Devuelve una lista normalizada de preventivos (puede contener None)."""

    if not isinstance(values, list):
        return []
    return [_normalize_preventivo(value) for value in values]


def _build_preventivos(
    cantidad: int,
    preferidos: Optional[Any],
    fallback_unico: Optional[Any],
) -> List[Optional[str]]:
    """Ajusta la lista de preventivos a la cantidad indicada."""

    if cantidad <= 0:
        return []

    lista = _normalize_preventivo_list(preferidos)
    if not lista and fallback_unico is not None:
        unico = _normalize_preventivo(fallback_unico)
        if unico:
            lista = [unico] * cantidad

    if len(lista) < cantidad:
        lista.extend([None] * (cantidad - len(lista)))
    else:
        lista = lista[:cantidad]

    return lista


def _primer_preventivo_valido(values: List[Optional[str]]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def es_admin(username: Optional[str], allowed_comisarias: Optional[List[str]]) -> bool:
    if not username:
        return False
    if username in ADMIN_USERS:
        return True
    allowed = allowed_comisarias or []
    return set(allowed) == set(COMISARIA_OPTIONS)


def _leer_agenda() -> AgendaData:
    data = load_json_from_gcs(AGENDA_PATH)
    if isinstance(data, dict) and data:
        return data  # type: ignore[return-value]

    agenda_vacia: AgendaData = {}
    if not blob_exists(AGENDA_PATH):
        st.caption("No se encontró el calendario en la nube. Se creará uno vacío por defecto.")
        _guardar_agenda(agenda_vacia)
        return agenda_vacia

    if isinstance(data, dict):
        return agenda_vacia

    st.error("El archivo de agenda está dañado. Se comenzó con una agenda vacía.")
    _guardar_agenda(agenda_vacia)
    return agenda_vacia


def _guardar_agenda(data: AgendaData) -> None:
    save_json_to_gcs(AGENDA_PATH, data)


def _key_fecha(fecha: datetime.date) -> str:
    if isinstance(fecha, datetime.datetime):
        fecha = fecha.date()
    return fecha.isoformat()


def _parse_fecha(fecha_str: str) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat(fecha_str)
    except ValueError:
        return None


def _ordenar_dias(dias: List[str]) -> List[str]:
    fechas = [(_parse_fecha(d), d) for d in dias]
    fechas_validas = [par for par in fechas if par[0] is not None]
    fechas_validas.sort(key=lambda par: par[0])
    return [par[1] for par in fechas_validas]


def _ensure_entry(data: AgendaData, comisaria: str, fecha: datetime.date) -> Dict[str, Dict[str, int]]:
    com_data = data.setdefault(comisaria, {})
    key = _key_fecha(fecha)
    entry = com_data.setdefault(key, {"delitos": {}})
    if "delitos" not in entry:
        entry["delitos"] = {}
    return entry


# ===========================
# API pública de datos
# ===========================


def obtener_dias_planificados(comisaria: str) -> List[datetime.date]:
    data = _leer_agenda()
    dias = data.get(comisaria, {})
    ordenados = _ordenar_dias(list(dias.keys()))
    resultado = []
    for key in ordenados:
        fecha = _parse_fecha(key)
        if fecha is not None:
            resultado.append(fecha)
    return resultado


def obtener_detalle_dia(comisaria: str, fecha: datetime.date) -> Dict[str, Dict[str, Any]]:
    data = _leer_agenda()
    entry = data.get(comisaria, {}).get(_key_fecha(fecha), {})
    delitos = entry.get("delitos", {})
    resultado: Dict[str, Dict[str, Any]] = {}
    for delito, valores in delitos.items():
        plan = int(valores.get("plan", 0))
        cargados = int(valores.get("cargados", 0))
        preventivos = _build_preventivos(plan, valores.get("preventivos"), valores.get("preventivo"))
        preventivo = _primer_preventivo_valido(preventivos)
        if preventivo is None:
            preventivo = _normalize_preventivo(valores.get("preventivo"))
        resultado[delito] = {
            "plan": max(plan, 0),
            "cargados": max(min(cargados, plan if plan > 0 else cargados), 0),
            "preventivo": preventivo,
            "preventivos": preventivos,
        }
    return resultado


def obtener_delitos_pendientes(comisaria: str, fecha: datetime.date) -> Dict[str, Dict[str, Any]]:
    detalle = obtener_detalle_dia(comisaria, fecha)
    pendientes: Dict[str, Dict[str, Any]] = {}
    for delito, valores in detalle.items():
        plan = valores.get("plan", 0)
        cargados = valores.get("cargados", 0)
        restantes = max(plan - cargados, 0)
        pendientes[delito] = {
            "plan": plan,
            "cargados": cargados,
            "restantes": restantes,
            "preventivo": valores.get("preventivo"),
            "preventivos": valores.get("preventivos", []),
        }
    return pendientes


def obtener_primer_dia_pendiente(comisaria: str) -> Optional[datetime.date]:
    for fecha in obtener_dias_planificados(comisaria):
        detalle = obtener_delitos_pendientes(comisaria, fecha)
        if any(info.get("restantes", 0) > 0 for info in detalle.values()):
            return fecha
    return None


def puede_cargar_delito(comisaria: str, fecha: datetime.date, delito: str) -> Tuple[bool, Optional[str]]:
    detalle = obtener_delitos_pendientes(comisaria, fecha)
    if delito not in detalle:
        return False, "El delito seleccionado no está asignado para este día."
    info = detalle[delito]
    if info.get("restantes", 0) <= 0:
        return False, "Ya se cargaron todos los hechos planificados para este delito."
    primer_pendiente = obtener_primer_dia_pendiente(comisaria)
    if primer_pendiente and fecha > primer_pendiente:
        msg = primer_pendiente.strftime("%d/%m/%Y")
        return False, f"Debe completar primero el día {msg} antes de avanzar a fechas posteriores."
    return True, None


def registrar_carga_delito(comisaria: str, fecha: datetime.date, delito: str) -> Tuple[bool, Optional[str], Optional[int]]:
    data = _leer_agenda()
    com_data = data.get(comisaria)
    if not com_data:
        return False, "No hay un almanaque cargado para esta comisaría.", None
    key = _key_fecha(fecha)
    dia_info = com_data.get(key)
    if not dia_info:
        return False, "El día seleccionado no tiene delitos asignados.", None
    delitos = dia_info.get("delitos", {})
    if delito not in delitos:
        return False, "El delito no pertenece al día seleccionado.", None
    registro = delitos[delito]
    plan = int(registro.get("plan", 0))
    cargados = int(registro.get("cargados", 0))
    if cargados >= plan:
        return False, "Se alcanzó el total planificado para este delito.", None
    registro["cargados"] = cargados + 1
    _guardar_agenda(data)
    restantes = max(plan - (cargados + 1), 0)
    return True, None, restantes


def asignar_delito(
    comisaria: str,
    fecha: datetime.date,
    delito: str,
    cantidad: int,
    preventivo: Optional[str] = None,
    preventivos: Optional[List[Optional[str]]] = None,
) -> Tuple[bool, Optional[str]]:
    if cantidad <= 0:
        return False, "La cantidad debe ser mayor a cero."
    data = _leer_agenda()
    entry = _ensure_entry(data, comisaria, fecha)
    delitos = entry["delitos"]
    registro = delitos.get(delito)
    if registro and registro.get("cargados", 0) > cantidad:
        return False, "No se puede reducir la cantidad por debajo de lo ya cargado."
    nuevo_registro = dict(registro or {})
    plan = int(cantidad)
    nuevo_registro["plan"] = plan
    cargados_previos = int(registro.get("cargados", 0)) if registro else 0
    nuevo_registro["cargados"] = min(max(cargados_previos, 0), plan)

    if preventivos is not None:
        preventivos_lista = _build_preventivos(plan, list(preventivos), None)
    elif preventivo is not None:
        preventivos_lista = _build_preventivos(plan, None, preventivo)
    else:
        preventivos_lista = _build_preventivos(
            plan,
            registro.get("preventivos") if registro else None,
            registro.get("preventivo") if registro else None,
        )

    # Compactar para evitar listas largas llenas de None
    preventivos_compactos = list(preventivos_lista)
    while preventivos_compactos and preventivos_compactos[-1] is None:
        preventivos_compactos.pop()

    if preventivos_compactos:
        nuevo_registro["preventivos"] = preventivos_compactos
    else:
        nuevo_registro.pop("preventivos", None)

    preventivo_final = _primer_preventivo_valido(preventivos_lista)
    if preventivo_final:
        nuevo_registro["preventivo"] = preventivo_final
    else:
        nuevo_registro.pop("preventivo", None)

    delitos[delito] = nuevo_registro
    _guardar_agenda(data)
    return True, None


def quitar_delito(comisaria: str, fecha: datetime.date, delito: str) -> Tuple[bool, Optional[str]]:
    data = _leer_agenda()
    com_data = data.get(comisaria)
    if not com_data:
        return False, "No se encontraron asignaciones para la comisaría."
    key = _key_fecha(fecha)
    dia_info = com_data.get(key)
    if not dia_info:
        return False, "El día seleccionado no tiene delitos asignados."
    delitos = dia_info.get("delitos", {})
    registro = delitos.get(delito)
    if not registro:
        return False, "El delito no está asignado en este día."
    delitos.pop(delito, None)
    if not delitos:
        com_data.pop(key, None)
    _guardar_agenda(data)
    return True, None


def resumen_dia_dataframe(comisaria: str, fecha: datetime.date) -> None:
    detalle = obtener_delitos_pendientes(comisaria, fecha)
    if not detalle:
        st.info("No hay delitos planificados para el día seleccionado.")
        return
    filas = []
    for delito, info in sorted(detalle.items(), key=lambda par: par[0].casefold()):
        preventivos = info.get("preventivos") or []
        if preventivos:
            preventivo_txt = "\n".join((p or "—") for p in preventivos)
        else:
            preventivo_txt = info.get("preventivo") or "—"
        filas.append({
            "Delito": delito.strip(),
            "Planificados": info.get("plan", 0),
            "Cargados": info.get("cargados", 0),
            "Restantes": info.get("restantes", 0),
            "N° Preventivo": preventivo_txt,
        })
    st.dataframe(filas, use_container_width=True)


# ===========================
# Componentes visuales
# ===========================


def _resumen_estados_dias(comisaria: str) -> Dict[datetime.date, Dict[str, int]]:
    """Resumen por día para colorear el almanaque."""

    data = _leer_agenda()
    com_data = data.get(comisaria, {})
    resumen: Dict[datetime.date, Dict[str, int]] = {}

    for key in _ordenar_dias(list(com_data.keys())):
        fecha = _parse_fecha(key)
        if fecha is None:
            continue

        entry = com_data.get(key, {})
        delitos = entry.get("delitos", {})
        if not isinstance(delitos, dict) or not delitos:
            continue

        total_plan = 0
        total_cargados = 0
        pendientes = False

        for valores in delitos.values():
            if not isinstance(valores, dict):
                continue

            plan = max(int(valores.get("plan", 0)), 0)
            cargados_raw = int(valores.get("cargados", 0))
            cargados = max(min(cargados_raw, plan if plan > 0 else cargados_raw), 0)

            total_plan += plan
            total_cargados += cargados
            if plan > cargados:
                pendientes = True

        estado = "pendiente" if pendientes else "completo"

        resumen[fecha] = {
            "plan": total_plan,
            "cargados": total_cargados,
            "restantes": max(total_plan - total_cargados, 0),
            "estado": estado,
        }

    return resumen


def _render_almanaque(dias: List[datetime.date], resumen: Dict[datetime.date, Dict[str, int]], seleccionada: Optional[datetime.date]) -> None:
    if not dias:
        return

    st.markdown(
        """
        <style>
        .agenda-cal-wrapper {
            position: sticky;
            top: 4rem;
            z-index: 100;
            background-color: var(--background-color, #ffffff);
            padding: 0.75rem 1rem;
            border: 1px solid rgba(49, 51, 63, 0.2);
            border-radius: 0.75rem;
            box-shadow: 0 6px 18px rgba(0, 0, 0, 0.05);
            margin-bottom: 1rem;
        }
        .agenda-cal-title {
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .agenda-calendar {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .agenda-day {
            min-width: 6.5rem;
            padding: 0.55rem 0.65rem;
            border-radius: 0.6rem;
            border: 1px solid rgba(49, 51, 63, 0.25);
            background-color: rgba(248, 249, 250, 0.8);
            text-align: center;
            font-size: 0.9rem;
            line-height: 1.1rem;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .agenda-day.seleccionado {
            box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.35);
            transform: translateY(-1px);
        }
        .agenda-day.estado-pendiente {
            background-color: #fde2e1;
            border-color: #f5c2c7;
            color: #7f1d1d;
        }
        .agenda-day.estado-completo {
            background-color: #d1f2d7;
            border-color: #badbcc;
            color: #0f5132;
        }
        .agenda-day-date {
            font-weight: 600;
            font-size: 1rem;
        }
        .agenda-day-meta {
            font-size: 0.75rem;
            opacity: 0.85;
        }
        .agenda-legend {
            display: flex;
            gap: 0.85rem;
            margin-top: 0.6rem;
            flex-wrap: wrap;
            font-size: 0.8rem;
        }
        .agenda-legend-item {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
        }
        .agenda-legend-dot {
            width: 0.75rem;
            height: 0.75rem;
            border-radius: 999px;
            display: inline-block;
        }
        .agenda-legend-dot.pendiente {
            background-color: #dc3545;
        }
        .agenda-legend-dot.completo {
            background-color: #198754;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    tarjetas: List[str] = []
    for fecha in dias:
        info = resumen.get(fecha, {})
        plan = int(info.get("plan", 0) or 0)
        cargados = int(info.get("cargados", 0) or 0)
        restantes = int(info.get("restantes", max(plan - cargados, 0)) or 0)
        estado = info.get("estado")
        if not estado:
            estado = "completo" if plan > 0 and restantes <= 0 else "pendiente"

        # Los días que ya fueron completados se ocultan del almanaque de la comisaría
        # para evitar confusiones con hechos ya cargados.
        if estado == "completo":
            continue

        clases = ["agenda-day", f"estado-{estado}"]
        if seleccionada and fecha == seleccionada:
            clases.append("seleccionado")

        fecha_txt = fecha.strftime("%d/%m")
        tooltip = f"{fecha.strftime('%d/%m/%Y')} - {cargados} cargados de {plan}"

        if plan <= 0:
            meta = "Sin delitos asignados"
        elif restantes > 0:
            meta = f"{cargados}/{plan} cargados · {restantes} restantes"
        else:
            meta = f"{cargados}/{plan} cargados"

        tarjetas.append(
            "<div class='{}' title='{}'><div class='agenda-day-date'>{}</div>"
            "<div class='agenda-day-meta'>{}</div></div>".format(
                " ".join(clases),
                html.escape(tooltip),
                html.escape(fecha_txt),
                html.escape(meta),
            )
        )

    calendario_html = "".join(tarjetas)
    st.markdown(
        f"""
        <div class="agenda-cal-wrapper">
            <div class="agenda-cal-title">Días asignados</div>
            <div class="agenda-calendar">{calendario_html}</div>
            <div class="agenda-legend">
                <span class="agenda-legend-item"><span class="agenda-legend-dot pendiente"></span>Pendiente</span>
                <span class="agenda-legend-item"><span class="agenda-legend-dot completo"></span>Completado</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ===========================
# UI para Streamlit
# ===========================


def render_admin_agenda(username: Optional[str], allowed_comisarias: Optional[List[str]]) -> None:
    if not es_admin(username, allowed_comisarias):
        return

    st.markdown("---")
    st.markdown("### 🗓️ Almanaque de asignación de delitos (Administración)")
    st.caption(
        "Programe qué delitos debe cargar cada comisaría en un día determinado."
        " Puede actualizar cantidades o quitar delitos siempre que no tengan cargas registradas."
    )

    st.markdown("#### Respaldo del calendario")
    col_backup_download, col_backup_upload = st.columns(2)

    with col_backup_download:
        st.markdown("**Guardar calendario actual**")
        agenda_actual = _leer_agenda()
        backup_bytes = json.dumps(agenda_actual, ensure_ascii=False, indent=2).encode("utf-8")
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        st.download_button(
            label="📁 Descargar respaldo",
            data=backup_bytes,
            file_name=f"agenda_delitos_{timestamp}.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption("Guarde una copia local del calendario actual para conservar un respaldo.")

    with col_backup_upload:
        st.markdown("**Cargar calendario desde archivo**")
        uploaded_backup = st.file_uploader(
            "Seleccione un archivo .json previamente guardado",
            type=["json"],
            key="agenda_admin_backup",
        )
        if uploaded_backup is not None:
            try:
                contenido = uploaded_backup.read()
                data = json.loads(contenido.decode("utf-8"))
            except UnicodeDecodeError:
                st.error("El archivo no está codificado en UTF-8 válido.")
            except json.JSONDecodeError:
                st.error("El archivo seleccionado no contiene un JSON válido.")
            else:
                if not isinstance(data, dict):
                    st.error("El respaldo debe contener un objeto JSON con el calendario completo.")
                else:
                    _guardar_agenda(data)
                    st.success("Se restauró el calendario desde el archivo subido.")
                    st.rerun()

    comisarias = allowed_comisarias or COMISARIA_OPTIONS
    comisaria_sel = st.selectbox(
        "Seleccione la comisaría a planificar",
        options=comisarias,
        key="agenda_admin_comisaria",
    )
    fecha_sel = st.date_input(
        "Día a planificar",
        value=st.session_state.get("agenda_admin_fecha") or datetime.date.today(),
        key="agenda_admin_fecha",
    )

    if not isinstance(fecha_sel, datetime.date):
        st.error("Seleccione un día válido.")
        return

    st.markdown(
        f"#### Delitos planificados para {fecha_sel.strftime('%d/%m/%Y')} — {comisaria_sel}"
    )
    detalle = obtener_detalle_dia(comisaria_sel, fecha_sel)
    if not detalle:
        st.info("No hay delitos asignados en este día.")
    else:
        for idx, (delito, info) in enumerate(sorted(detalle.items(), key=lambda par: par[0].casefold())):
            planificados = info.get("plan", 0)
            restantes = max(planificados - info.get("cargados", 0), 0)
            preventivos_actuales: List[Optional[str]] = info.get("preventivos") or []
            instancias = planificados if planificados > 0 else len(preventivos_actuales)
            instancias = max(instancias, 1)
            cols = st.columns([3, 2.2, 3.1, 0.8])
            cols[0].markdown(f"**{delito.strip()}**")
            preventivo_lines = []
            for idx_prev in range(instancias):
                valor = preventivos_actuales[idx_prev] if idx_prev < len(preventivos_actuales) else None
                preventivo_lines.append(f"Preventivo #{idx_prev + 1}: {valor or '—'}")
            preventivo_txt = "  \\n".join(preventivo_lines)
            cols[1].markdown(
                f"Planificados: {planificados}  \\n"
                f"Cargados: {info.get('cargados', 0)}  \\n"
                f"Restantes: {restantes}  \\n"
                f"{preventivo_txt}"
            )
            with cols[2]:
                nueva_cantidad = st.number_input(
                    "Cantidad",
                    min_value=max(info.get("cargados", 0), 0),
                    value=planificados,
                    step=1,
                    key=f"agenda_admin_plan_{idx}"
                )
                total_inputs = max(int(nueva_cantidad), 1)
                preventivo_inputs: List[str] = []
                for idx_prev in range(total_inputs):
                    valor = preventivos_actuales[idx_prev] if idx_prev < len(preventivos_actuales) else ""
                    preventivo_inputs.append(
                        st.text_input(
                            f"Preventivo #{idx_prev + 1}",
                            value=valor,
                            max_chars=20,
                            key=f"agenda_admin_prev_{idx}_{idx_prev}"
                        )
                    )
                st.caption(
                    "Complete un número de preventivo por cada hecho asignado. "
                    "Deje el campo vacío si la comisaría debe cargarlo."
                )
                if st.button("Guardar cambios", key=f"agenda_admin_update_{idx}"):
                    ok, msg = asignar_delito(
                        comisaria_sel,
                        fecha_sel,
                        delito,
                        int(nueva_cantidad),
                        preventivos=preventivo_inputs,
                    )
                    if ok:
                        st.success(f"Se actualizó {delito.strip()}.")
                        st.rerun()
                    else:
                        st.error(msg or "No se pudo actualizar la asignación.")
            if cols[3].button("Quitar", key=f"agenda_admin_remove_{idx}"):
                ok, msg = quitar_delito(comisaria_sel, fecha_sel, delito)
                if ok:
                    st.warning(f"Se quitó {delito.strip()} del día seleccionado.")
                    st.rerun()
                else:
                    st.error(msg or "No se pudo quitar el delito.")

    st.markdown("#### Agregar o actualizar delito")

    if st.session_state.pop("agenda_admin_preventivo_reset", False):
        st.session_state["agenda_admin_preventivo_add"] = ""

    with st.form(key="agenda_admin_add_form"):
        delito_nuevo = st.selectbox(
            "Delito",
            options=DELITOS_DISPONIBLES,
            key="agenda_admin_delito_add",
        )
        cantidad = st.number_input(
            "Cantidad a cargar",
            min_value=1,
            step=1,
            value=1,
            key="agenda_admin_cantidad_add",
        )
        preventivo_form = st.text_area(
            "N° de preventivos (opcional)",
            key="agenda_admin_preventivo_add",
            height=90,
            help="Ingrese un número por línea para separar cada hecho planificado.",
        )
        submitted = st.form_submit_button("Guardar asignación")
        if submitted:
            preventivos_nuevos = [line.strip() for line in preventivo_form.splitlines()]
            ok, msg = asignar_delito(
                comisaria_sel,
                fecha_sel,
                delito_nuevo,
                int(cantidad),
                preventivos=preventivos_nuevos if any(preventivos_nuevos) else None,
            )
            if ok:
                # Limpiar el campo en la próxima ejecución para evitar
                # reutilizar accidentalmente el último número de preventivo ingresado.
                st.session_state["agenda_admin_preventivo_reset"] = True
                st.success("Asignación guardada correctamente.")
                st.rerun()
            else:
                st.error(msg or "No se pudo guardar la asignación.")


def render_selector_comisaria(comisaria: str) -> Tuple[Optional[datetime.date], Dict[str, Dict[str, Any]], Optional[str]]:
    dias = obtener_dias_planificados(comisaria)
    if not dias:
        return None, {}, "No hay delitos asignados por el administrador para esta comisaría."

    resumen = _resumen_estados_dias(comisaria)

    preferido = st.session_state.get("agenda_fecha")
    if preferido not in dias:
        preferido = obtener_primer_dia_pendiente(comisaria) or dias[0]

    fecha_sel = st.date_input(
        "Seleccione el día asignado",
        value=preferido,
        key="agenda_fecha_comisaria",
    )

    if not isinstance(fecha_sel, datetime.date):
        return None, {}, "Seleccione una fecha válida."

    st.session_state.agenda_fecha = fecha_sel

    _render_almanaque(dias, resumen, fecha_sel)

    if fecha_sel not in dias:
        return None, {}, "No hay delitos asignados para la fecha elegida."

    primer_pendiente = obtener_primer_dia_pendiente(comisaria)
    if primer_pendiente and fecha_sel > primer_pendiente:
        msg = primer_pendiente.strftime("%d/%m/%Y")
        return None, {}, f"Debe completar primero el día {msg} antes de avanzar."

    resumen_dia_dataframe(comisaria, fecha_sel)
    pendientes = obtener_delitos_pendientes(comisaria, fecha_sel)
    return fecha_sel, pendientes, None
