"""Almanaque de asignación para Planillas Ley 2785.

Inspirado en el módulo ``agenda_delitos`` de SNIC-SAT pero adaptado
para trabajar con la columna "Información específica (AI)" como
referencia obligatoria de cada hecho planificado.
"""
from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from gcs_utils import blob_exists, load_json_from_gcs, save_json_to_gcs

AGENDA_PATH = "agenda_planillas_ley_2785.json"
ADMIN_USERS = {"Gaston"}

# ===========================
# Utilidades internas
# ===========================

AgendaData = Dict[str, Dict[str, Dict[str, Dict[str, Any]]]]


def _normalize_referencia(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    return value or None


def es_admin(username: Optional[str], allowed_unidades: Optional[List[str]]) -> bool:
    if not username:
        return False
    if username in ADMIN_USERS:
        return True
    allowed = allowed_unidades or []
    return bool(allowed)


def _leer_agenda() -> AgendaData:
    data = load_json_from_gcs(AGENDA_PATH)
    if isinstance(data, dict) and data:
        if _migrar_formato_antiguo(data):
            _guardar_agenda(data)
        return data  # type: ignore[return-value]

    agenda_vacia: AgendaData = {}
    if not blob_exists(AGENDA_PATH):
        st.caption("No se encontró el almanaque en la nube. Se creará uno nuevo.")
        _guardar_agenda(agenda_vacia)
        return agenda_vacia

    if isinstance(data, dict):
        return agenda_vacia

    st.error("El archivo de almanaque está dañado. Se comenzó con uno vacío.")
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


def _generate_slot_id() -> str:
    return uuid.uuid4().hex


def _migrar_formato_antiguo(data: AgendaData) -> bool:
    modificado = False
    for unidad_data in data.values():
        for entry in unidad_data.values():
            hechos = entry.get("hechos")
            if not isinstance(hechos, dict):
                continue
            if all(isinstance(info, dict) and info.get("id") for info in hechos.values()):
                continue
            nuevos: Dict[str, Dict[str, Any]] = {}
            for nombre_clave, info in hechos.items():
                if not isinstance(info, dict):
                    continue
                referencia = _normalize_referencia(info.get("referencia"))
                plan = max(int(info.get("plan", 0) or 0), 0)
                cargados = max(int(info.get("cargados", 0) or 0), 0)
                if plan <= 0:
                    plan = max(1, cargados)
                for idx in range(plan):
                    slot_id = _generate_slot_id()
                    nuevos[slot_id] = {
                        "id": slot_id,
                        "plan": 1,
                        "cargados": 1 if idx < cargados else 0,
                        "referencia": referencia if idx == 0 else None,
                        "etiqueta": nombre_clave or f"Hecho {idx + 1}",
                    }
            entry["hechos"] = nuevos
            modificado = True
    return modificado


def _ensure_entry(data: AgendaData, unidad: str, fecha: datetime.date) -> Dict[str, Dict[str, Any]]:
    unidad_data = data.setdefault(unidad, {})
    key = _key_fecha(fecha)
    entry = unidad_data.setdefault(key, {"hechos": {}})
    if "hechos" not in entry:
        entry["hechos"] = {}
    hechos = entry["hechos"]
    if not isinstance(hechos, dict):
        entry["hechos"] = {}
    else:
        cambios = False
        nuevos: Dict[str, Dict[str, Any]] = {}
        for clave, info in hechos.items():
            if not isinstance(info, dict):
                continue
            registro = dict(info)
            if not registro.get("id"):
                registro["id"] = _generate_slot_id()
                cambios = True
            if "plan" not in registro:
                registro["plan"] = 1
                cambios = True
            if "cargados" not in registro:
                registro["cargados"] = 0
                cambios = True
            registro.setdefault("etiqueta", clave)
            nuevos[registro["id"]] = registro
        if cambios:
            entry["hechos"] = nuevos
    return entry


# ===========================
# API pública de datos
# ===========================


def obtener_dias_planificados(unidad: str) -> List[datetime.date]:
    data = _leer_agenda()
    dias = data.get(unidad, {})
    ordenados = _ordenar_dias(list(dias.keys()))
    resultado = []
    for key in ordenados:
        fecha = _parse_fecha(key)
        if fecha is not None:
            resultado.append(fecha)
    return resultado


def obtener_hechos_pendientes(
    unidad: str, fecha: datetime.date, incluir_completados: bool = False
) -> Dict[str, Dict[str, Any]]:
    data = _leer_agenda()
    entry = data.get(unidad, {}).get(_key_fecha(fecha), {})
    hechos = entry.get("hechos", {})
    resultado: Dict[str, Dict[str, Any]] = {}
    for hecho_id, valores in hechos.items():
        plan = int(valores.get("plan", 0))
        cargados = int(valores.get("cargados", 0))
        referencia = _normalize_referencia(valores.get("referencia"))
        etiqueta = valores.get("etiqueta") or hecho_id
        if plan <= 0:
            plan = 1
        cargados = 1 if cargados > 0 else 0
        if plan <= cargados and not incluir_completados:
            continue
        resultado[hecho_id] = {
            "plan": 1,
            "cargados": cargados,
            "referencia": referencia,
            "etiqueta": etiqueta,
        }
    return resultado


def obtener_primer_dia_pendiente(unidad: str) -> Optional[datetime.date]:
    for fecha in obtener_dias_planificados(unidad):
        detalle = obtener_hechos_pendientes(unidad, fecha)
        if any(info.get("cargados", 0) < info.get("plan", 1) for info in detalle.values()):
            return fecha
    return None


def registrar_carga_hecho(unidad: str, fecha: datetime.date, hecho_id: str) -> Tuple[bool, Optional[str], Optional[int]]:
    data = _leer_agenda()
    unidad_data = data.get(unidad)
    if not unidad_data:
        return False, "No hay un almanaque cargado para esta unidad.", None
    key = _key_fecha(fecha)
    dia_info = unidad_data.get(key)
    if not dia_info:
        return False, "El día seleccionado no tiene hechos asignados.", None
    hechos = dia_info.get("hechos", {})
    if hecho_id not in hechos:
        return False, "El hecho no pertenece al día seleccionado.", None
    registro = hechos[hecho_id]
    cargados = int(registro.get("cargados", 0))
    if cargados >= 1:
        return False, "Se alcanzó el total planificado para este hecho.", None
    registro["cargados"] = 1
    _guardar_agenda(data)
    restantes = sum(
        max(int(info.get("plan", 1)) - int(info.get("cargados", 0)), 0)
        for info in hechos.values()
        if isinstance(info, dict)
    )
    return True, None, restantes


def asignar_hecho(
    unidad: str,
    fecha: datetime.date,
    cantidad: int,
    referencia: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    if cantidad <= 0:
        return False, "La cantidad debe ser mayor a cero."
    data = _leer_agenda()
    entry = _ensure_entry(data, unidad, fecha)
    hechos = entry["hechos"]
    referencia_normalizada = _normalize_referencia(referencia)
    for idx in range(cantidad):
        slot_id = _generate_slot_id()
        nuevo_registro = {
            "id": slot_id,
            "plan": 1,
            "cargados": 0,
            "etiqueta": f"Hecho {len(hechos) + idx + 1}",
        }
        if referencia_normalizada and idx == 0:
            nuevo_registro["referencia"] = referencia_normalizada
        hechos[slot_id] = nuevo_registro
    _guardar_agenda(data)
    return True, None


def actualizar_referencia_hecho(
    unidad: str,
    fecha: datetime.date,
    hecho_id: str,
    referencia: Optional[str],
) -> Tuple[bool, Optional[str]]:
    data = _leer_agenda()
    unidad_data = data.get(unidad)
    if not unidad_data:
        return False, "No se encontraron asignaciones para la unidad."
    key = _key_fecha(fecha)
    dia_info = unidad_data.get(key)
    if not dia_info:
        return False, "El día seleccionado no tiene hechos asignados."
    hechos = dia_info.get("hechos", {})
    registro = hechos.get(hecho_id)
    if not registro:
        return False, "El hecho no está asignado en este día."
    referencia_normalizada = _normalize_referencia(referencia)
    if referencia_normalizada:
        registro["referencia"] = referencia_normalizada
    else:
        registro.pop("referencia", None)
    _guardar_agenda(data)
    return True, None


def quitar_hecho(unidad: str, fecha: datetime.date, hecho_id: str) -> Tuple[bool, Optional[str]]:
    data = _leer_agenda()
    unidad_data = data.get(unidad)
    if not unidad_data:
        return False, "No se encontraron asignaciones para la unidad."
    key = _key_fecha(fecha)
    dia_info = unidad_data.get(key)
    if not dia_info:
        return False, "El día seleccionado no tiene hechos asignados."
    hechos = dia_info.get("hechos", {})
    registro = hechos.get(hecho_id)
    if not registro:
        return False, "El hecho no está asignado en este día."
    if int(registro.get("cargados", 0)) > 0:
        return False, "No se puede quitar un hecho que ya tiene cargas registradas."
    hechos.pop(hecho_id, None)
    if not hechos:
        unidad_data.pop(key, None)
    _guardar_agenda(data)
    return True, None


def resumen_dia_dataframe(unidad: str, fecha: datetime.date) -> None:
    detalle = obtener_hechos_pendientes(unidad, fecha, incluir_completados=True)
    if not detalle:
        st.info("No hay hechos pendientes para el día seleccionado.")
        return
    filas = []
    for idx, (hecho_id, info) in enumerate(sorted(detalle.items(), key=lambda par: par[1].get("etiqueta", par[0]).casefold()), start=1):
        filas.append({
            "Hecho": info.get("etiqueta") or f"Hecho {idx}",
            "Planificados": info.get("plan", 0),
            "Cargados": info.get("cargados", 0),
            "Restantes": max(info.get("plan", 0) - info.get("cargados", 0), 0),
            "Información específica (AI)": info.get("referencia") or "—",
        })
    st.dataframe(filas, use_container_width=True)


# ===========================
# Componentes visuales
# ===========================


def _resumen_estados_dias(unidad: str) -> Dict[datetime.date, Dict[str, int]]:
    data = _leer_agenda()
    unidad_data = data.get(unidad, {})
    resumen: Dict[datetime.date, Dict[str, int]] = {}
    for key in _ordenar_dias(list(unidad_data.keys())):
        fecha = _parse_fecha(key)
        if fecha is None:
            continue
        entry = unidad_data.get(key, {})
        hechos = entry.get("hechos", {})
        if not isinstance(hechos, dict) or not hechos:
            continue
        total_plan = 0
        total_cargados = 0
        pendientes = False
        for valores in hechos.values():
            if not isinstance(valores, dict):
                continue
            plan = max(int(valores.get("plan", 1)), 1)
            cargados = 1 if int(valores.get("cargados", 0)) > 0 else 0
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
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 0.5rem;
        }
        .agenda-card {
            padding: 0.75rem;
            border-radius: 0.6rem;
            border: 1px solid rgba(49, 51, 63, 0.2);
        }
        .agenda-card.pendiente {
            background-color: rgba(255, 152, 0, 0.1);
        }
        .agenda-card.completo {
            background-color: rgba(76, 175, 80, 0.12);
        }
        .agenda-card .meta { font-size: 0.9rem; color: #555; }
        .agenda-legend { margin-top: 0.5rem; font-size: 0.9rem; }
        .agenda-legend-item { margin-right: 1rem; }
        .agenda-legend-dot { display: inline-block; width: 0.8rem; height: 0.8rem; border-radius: 50%; margin-right: 0.35rem; }
        .agenda-legend-dot.pendiente { background-color: #ff9800; }
        .agenda-legend-dot.completo { background-color: #4caf50; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    tarjetas = []
    for fecha in dias:
        resumen_dia = resumen.get(fecha, {})
        estado = resumen_dia.get("estado", "pendiente")
        meta = f"Planificados: {resumen_dia.get('plan', 0)} | Restantes: {resumen_dia.get('restantes', 0)}"
        fecha_txt = fecha.strftime("%d/%m/%Y")
        card_class = "agenda-card " + estado
        tarjetas.append(
            f"<div class='{card_class}'><div><strong>{fecha_txt}</strong></div><div class='meta'>{meta}</div></div>"
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


def render_admin_agenda(username: Optional[str], allowed_unidades: Optional[List[str]]) -> None:
    if not es_admin(username, allowed_unidades):
        return
    st.markdown("---")
    st.markdown("### 🗓️ Almanaque de hechos (Administración)")
    st.caption(
        "Asigne hechos a cargar por cada unidad en días específicos. "
        "La referencia será la columna 'Información específica (AI)'."
    )
    st.markdown("#### Respaldo del almanaque")
    col_backup_download, col_backup_upload = st.columns(2)
    with col_backup_download:
        st.markdown("**Guardar almanaque actual**")
        agenda_actual = _leer_agenda()
        backup_bytes = json.dumps(agenda_actual, ensure_ascii=False, indent=2).encode("utf-8")
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        st.download_button(
            label="📁 Descargar respaldo",
            data=backup_bytes,
            file_name=f"agenda_planillas_2785_{timestamp}.json",
            mime="application/json",
            use_container_width=True,
        )
        st.caption("Guarde una copia local del almanaque actual para conservar un respaldo.")
    with col_backup_upload:
        st.markdown("**Cargar almanaque desde archivo**")
        uploaded_backup = st.file_uploader(
            "Seleccione un archivo .json previamente guardado",
            type=["json"],
            key="agenda_planillas_admin_backup",
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
                    st.error("El respaldo debe contener un objeto JSON con el almanaque completo.")
                else:
                    _guardar_agenda(data)
                    st.success("Se restauró el almanaque desde el archivo subido.")
                    st.rerun()

    unidades = allowed_unidades or []
    if not unidades:
        st.info("El usuario no tiene unidades cargadas para administrar el almanaque.")
        return
    unidad_sel = st.selectbox(
        "Seleccione la unidad a planificar",
        options=unidades,
        key="agenda_planillas_admin_unidad",
    )
    fecha_sel = st.date_input(
        "Día a planificar",
        value=st.session_state.get("agenda_planillas_admin_fecha") or datetime.date.today(),
        key="agenda_planillas_admin_fecha",
    )
    if not isinstance(fecha_sel, datetime.date):
        st.error("Seleccione un día válido.")
        return
    st.markdown(
        f"#### Hechos planificados para {fecha_sel.strftime('%d/%m/%Y')} — {unidad_sel}"
    )
    detalle = obtener_hechos_pendientes(unidad_sel, fecha_sel, incluir_completados=True)
    if not detalle:
        st.info("No hay hechos pendientes en este día.")
    else:
        orden = sorted(detalle.items(), key=lambda par: par[1].get("etiqueta", par[0]).casefold())
        for hecho_id, info in orden:
            restantes = max(info.get("plan", 0) - info.get("cargados", 0), 0)
            referencia_actual = info.get("referencia") or ""
            etiqueta = info.get("etiqueta") or hecho_id
            cols = st.columns([3, 2, 1])
            cols[0].markdown(f"**{etiqueta}**")
            cols[1].markdown(
                f"Estado: {'Pendiente' if restantes > 0 else 'Completado'}  \\\n"
                f"Cargados: {info.get('cargados', 0)} / {info.get('plan', 0)}  \\\n"
                f"Referencia AI: {referencia_actual or '—'}"
            )
            with cols[2]:
                referencia_input = st.text_input(
                    "Información específica (AI)",
                    value=referencia_actual,
                    key=f"agenda_planillas_ref_{hecho_id}",
                )
                st.caption("Se muestra al usuario como referencia.")
                if st.button("Guardar", key=f"agenda_planillas_update_{hecho_id}"):
                    ok, msg = actualizar_referencia_hecho(
                        unidad_sel,
                        fecha_sel,
                        hecho_id,
                        referencia_input,
                    )
                    if ok:
                        st.success(f"Se actualizó {etiqueta}.")
                        st.rerun()
                    else:
                        st.error(msg or "No se pudo actualizar la asignación.")
            if st.button("Quitar", key=f"agenda_planillas_remove_{hecho_id}"):
                ok, msg = quitar_hecho(unidad_sel, fecha_sel, hecho_id)
                if ok:
                    st.warning(f"Se quitó {etiqueta} del día seleccionado.")
                    st.rerun()
                else:
                    st.error(msg or "No se pudo quitar el hecho.")
    st.markdown("---")
    with st.form("agenda_planillas_form"):
        st.markdown("#### Agregar hechos al día seleccionado")
        referencia_form = st.text_input(
            "Información específica (AI) de referencia (opcional)",
            key="agenda_planillas_ref_form",
        )
        cantidad = st.number_input(
            "Cantidad de hechos a asignar",
            min_value=1,
            step=1,
            value=1,
            key="agenda_planillas_cantidad",
        )
        submitted = st.form_submit_button("Agregar al día")
        if submitted:
            ok, msg = asignar_hecho(
                unidad_sel,
                fecha_sel,
                int(cantidad),
                referencia_form,
            )
            if ok:
                st.success("Asignación guardada correctamente.")
                st.rerun()
            else:
                st.error(msg or "No se pudo guardar la asignación.")


def render_selector_unidad(unidades: List[str]) -> str:
    if not unidades:
        st.error("No hay unidades disponibles para el almanaque.")
        st.stop()
    current = st.session_state.get("agenda_planillas_unidad") or unidades[0]
    if current not in unidades:
        current = unidades[0]
    unidad_sel = st.selectbox(
        "Seleccione la unidad asignada",
        options=unidades,
        index=unidades.index(current),
        key="agenda_planillas_unidad",
    )
    st.session_state.institucion = unidad_sel
    return unidad_sel


def render_selector_agenda(unidad: str) -> Tuple[Optional[datetime.date], Dict[str, Dict[str, Any]], Optional[str]]:
    dias = obtener_dias_planificados(unidad)
    if not dias:
        return None, {}, "No hay hechos asignados por el administrador para esta unidad."
    resumen = _resumen_estados_dias(unidad)
    preferido = st.session_state.get("agenda_planillas_fecha")
    if preferido not in dias:
        preferido = obtener_primer_dia_pendiente(unidad) or dias[0]
    fecha_sel = st.date_input(
        "Seleccione el día asignado",
        value=preferido,
        key="agenda_planillas_fecha_input",
    )
    if not isinstance(fecha_sel, datetime.date):
        return None, {}, "Seleccione una fecha válida."
    st.session_state.agenda_planillas_fecha = fecha_sel
    _render_almanaque(dias, resumen, fecha_sel)
    if fecha_sel not in dias:
        return None, {}, "No hay hechos asignados para la fecha elegida."
    primer_pendiente = obtener_primer_dia_pendiente(unidad)
    if primer_pendiente and fecha_sel > primer_pendiente:
        msg = primer_pendiente.strftime("%d/%m/%Y")
        return None, {}, f"Debe completar primero el día {msg} antes de avanzar."
    estado_dia = resumen.get(fecha_sel)
    if estado_dia and estado_dia.get("restantes", 0) <= 0:
        return fecha_sel, {}, "¡Felicitaciones! Completaste todos los hechos planificados para la fecha seleccionada."
    resumen_dia_dataframe(unidad, fecha_sel)
    pendientes = obtener_hechos_pendientes(unidad, fecha_sel)
    ordenados = sorted(
        pendientes.items(),
        key=lambda par: par[1].get("etiqueta", par[0]).casefold(),
    )
    for idx, (hecho_id, info) in enumerate(ordenados, start=1):
        etiqueta = info.get("etiqueta") or f"Hecho {idx}"
        pendientes[hecho_id]["display"] = f"{etiqueta} — Ref: {info.get('referencia') or 'sin dato'}"
    return fecha_sel, pendientes, None
