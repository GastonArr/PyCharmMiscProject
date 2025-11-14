import datetime
import html
import json
from typing import Dict, List, Optional, Tuple

import streamlit as st

from drive_storage import DriveStorage, get_storage, guess_mime_type
from login import COMISARIA_OPTIONS

# ===========================
# Configuración básica
# ===========================

AGENDA_REMOTE_FILENAME = "agenda_delitos.json"
AGENDA_MIME = guess_mime_type(AGENDA_REMOTE_FILENAME)


def _storage() -> Optional[DriveStorage]:
    try:
        return get_storage()
    except RuntimeError as exc:
        st.error(f"⚠️ {exc}")
        return None


def _agenda_local_path(force_download: bool = False) -> Optional[str]:
    storage = _storage()
    if storage is None:
        return None
    return storage.ensure_local_file(
        AGENDA_REMOTE_FILENAME,
        default=lambda: b"{}",
        mime_type=AGENDA_MIME,
        force_download=force_download,
    )

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

AgendaData = Dict[str, Dict[str, Dict[str, Dict[str, int]]]]


def es_admin(username: Optional[str], allowed_comisarias: Optional[List[str]]) -> bool:
    if not username:
        return False
    if username in ADMIN_USERS:
        return True
    allowed = allowed_comisarias or []
    return set(allowed) == set(COMISARIA_OPTIONS)


def _leer_agenda() -> AgendaData:
    path = _agenda_local_path(force_download=True)
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data  # type: ignore[return-value]
    except json.JSONDecodeError:
        st.error("El archivo de agenda está dañado. Se comenzará con una agenda vacía.")
    return {}


def _guardar_agenda(data: AgendaData) -> None:
    path = _agenda_local_path(force_download=False)
    if not path:
        st.error("⚠️ No se pudo acceder al almacenamiento de agenda en Google Drive.")
        return
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    storage = _storage()
    if storage is None:
        return
    try:
        storage.upload_local_path(path)
    except RuntimeError as exc:
        st.error(f"⚠️ No se pudo sincronizar la agenda con Google Drive: {exc}")


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


def obtener_detalle_dia(comisaria: str, fecha: datetime.date) -> Dict[str, Dict[str, int]]:
    data = _leer_agenda()
    entry = data.get(comisaria, {}).get(_key_fecha(fecha), {})
    delitos = entry.get("delitos", {})
    resultado: Dict[str, Dict[str, int]] = {}
    for delito, valores in delitos.items():
        plan = int(valores.get("plan", 0))
        cargados = int(valores.get("cargados", 0))
        resultado[delito] = {
            "plan": max(plan, 0),
            "cargados": max(min(cargados, plan if plan > 0 else cargados), 0),
        }
    return resultado


def obtener_delitos_pendientes(comisaria: str, fecha: datetime.date) -> Dict[str, Dict[str, int]]:
    detalle = obtener_detalle_dia(comisaria, fecha)
    pendientes: Dict[str, Dict[str, int]] = {}
    for delito, valores in detalle.items():
        plan = valores.get("plan", 0)
        cargados = valores.get("cargados", 0)
        restantes = max(plan - cargados, 0)
        pendientes[delito] = {
            "plan": plan,
            "cargados": cargados,
            "restantes": restantes,
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


def asignar_delito(comisaria: str, fecha: datetime.date, delito: str, cantidad: int) -> Tuple[bool, Optional[str]]:
    if cantidad <= 0:
        return False, "La cantidad debe ser mayor a cero."
    data = _leer_agenda()
    entry = _ensure_entry(data, comisaria, fecha)
    delitos = entry["delitos"]
    registro = delitos.get(delito)
    if registro and registro.get("cargados", 0) > cantidad:
        return False, "No se puede reducir la cantidad por debajo de lo ya cargado."
    delitos[delito] = {
        "plan": int(cantidad),
        "cargados": int(registro.get("cargados", 0)) if registro else 0,
    }
    _guardar_agenda(data)
    return True, None


def quitar_delito(comisaria: str, fecha: datetime.date, delito: str) -> Tuple[bool, Optional[str]]:
    data = _leer_agenda()
    com_data = data.get(comisaria)
    if not com_data:
        return False, "No se encontraron asignaciones para la comisaría.", None
    key = _key_fecha(fecha)
    dia_info = com_data.get(key)
    if not dia_info:
        return False, "El día seleccionado no tiene delitos asignados.", None
    delitos = dia_info.get("delitos", {})
    registro = delitos.get(delito)
    if not registro:
        return False, "El delito no está asignado en este día.", None
    if int(registro.get("cargados", 0)) > 0:
        return False, "No se puede quitar un delito que ya tiene cargas registradas.", None
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
        filas.append({
            "Delito": delito.strip(),
            "Planificados": info.get("plan", 0),
            "Cargados": info.get("cargados", 0),
            "Restantes": info.get("restantes", 0),
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
    hoy = datetime.date.today()
    umbral_ocultamiento = datetime.timedelta(days=10)
    for fecha in dias:
        info = resumen.get(fecha, {})
        plan = int(info.get("plan", 0) or 0)
        cargados = int(info.get("cargados", 0) or 0)
        restantes = int(info.get("restantes", max(plan - cargados, 0)) or 0)
        estado = info.get("estado")
        if not estado:
            estado = "completo" if plan > 0 and restantes <= 0 else "pendiente"

        if estado == "completo" and (hoy - fecha) >= umbral_ocultamiento:
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
            restantes = max(info.get("plan", 0) - info.get("cargados", 0), 0)
            cols = st.columns([3, 1, 1, 1])
            cols[0].markdown(f"**{delito.strip()}**")
            cols[1].markdown(
                f"Planificados: {info.get('plan', 0)}  \\n"
                f"Cargados: {info.get('cargados', 0)}  \\n"
                f"Restantes: {restantes}"
            )
            nueva_cantidad = cols[2].number_input(
                "Cantidad",
                min_value=max(info.get("cargados", 0), 0),
                value=info.get("plan", 0),
                step=1,
                key=f"agenda_admin_plan_{idx}"
            )
            if cols[2].button("Actualizar", key=f"agenda_admin_update_{idx}"):
                ok, msg = asignar_delito(comisaria_sel, fecha_sel, delito, int(nueva_cantidad))
                if ok:
                    st.success(f"Se actualizó la cantidad para {delito.strip()}.")
                    st.rerun()
                else:
                    st.error(msg or "No se pudo actualizar la cantidad.")
            if cols[3].button("Quitar", key=f"agenda_admin_remove_{idx}"):
                ok, msg = quitar_delito(comisaria_sel, fecha_sel, delito)
                if ok:
                    st.warning(f"Se quitó {delito.strip()} del día seleccionado.")
                    st.rerun()
                else:
                    st.error(msg or "No se pudo quitar el delito.")

    st.markdown("#### Agregar o actualizar delito")
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
        submitted = st.form_submit_button("Guardar asignación")
        if submitted:
            ok, msg = asignar_delito(comisaria_sel, fecha_sel, delito_nuevo, int(cantidad))
            if ok:
                st.success("Asignación guardada correctamente.")
                st.rerun()
            else:
                st.error(msg or "No se pudo guardar la asignación.")


def render_selector_comisaria(comisaria: str) -> Tuple[Optional[datetime.date], Dict[str, Dict[str, int]], Optional[str]]:
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
