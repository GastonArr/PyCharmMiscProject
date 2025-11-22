import io
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ANEXO_1 import mostrar_anexo1
from ANEXO_2 import mostrar_anexo_2
from gcs_utils import download_blob_bytes, upload_blob_bytes

APP_TITLE = "Operativos Verano"

# Este parámetro ya no se usa para elegir archivo (eso se hace por unidad),
# pero se mantiene por compatibilidad con las funciones de los anexos.
ANEXO1_PATH = "operativos-verano/anexo1/anexo1.xlsx"
ANEXO2_PATH = "operativos-verano/anexo2/anexo2.xlsx"

ESTADO_BLOB = "operativos-verano/estado_carga_operativos.csv"
DIA_INICIO = 19   # solo para fecha_default de formularios

# La planilla empieza a usarse a partir de esta fecha
START_DATE = date(2025, 11, 19)

UNIDADES = ["comisaria 9", "comisaria 42", "DTCCO-PH"]


# -------------------------------------------------------------------
# FUNCIONES ESTADO DIARIO (POR UNIDAD)
# -------------------------------------------------------------------
def cargar_estado():
    """
    Carga el CSV de estado.
    Estructura esperada: fecha, unidad, anexo1_completo, anexo2_completo
    """
    data = download_blob_bytes(ESTADO_BLOB)
    if data:
        df = pd.read_csv(io.BytesIO(data))
        if "fecha" not in df.columns or "unidad" not in df.columns:
            df = pd.DataFrame(columns=["fecha", "unidad", "anexo1_completo", "anexo2_completo"])
    else:
        df = pd.DataFrame(columns=["fecha", "unidad", "anexo1_completo", "anexo2_completo"])

    # Convertimos fecha a datetime
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    return df


def guardar_estado(df_estado):
    buffer = io.StringIO()
    df_estado.to_csv(buffer, index=False)
    upload_blob_bytes(ESTADO_BLOB, buffer.getvalue().encode("utf-8"), content_type="text/csv")


def asegurar_fila_estado(df_estado, fecha_objetivo: date, unidad: str):
    """
    Se asegura de que exista una fila para (fecha_objetivo, unidad)
    en df_estado y devuelve (df_estado_actualizado, idx_fila).
    """
    if df_estado.empty:
        df_estado = pd.DataFrame(
            {
                "fecha": [pd.to_datetime(fecha_objetivo)],
                "unidad": [unidad],
                "anexo1_completo": [False],
                "anexo2_completo": [False],
            }
        )
    else:
        df_estado["fecha"] = pd.to_datetime(df_estado["fecha"], errors="coerce")
        mask = (df_estado["fecha"].dt.date == fecha_objetivo) & (df_estado["unidad"] == unidad)
        if not mask.any():
            nueva = pd.DataFrame(
                {
                    "fecha": [pd.to_datetime(fecha_objetivo)],
                    "unidad": [unidad],
                    "anexo1_completo": [False],
                    "anexo2_completo": [False],
                }
            )
            df_estado = pd.concat([df_estado, nueva], ignore_index=True)

    idx = df_estado[
        (df_estado["fecha"].dt.date == fecha_objetivo) & (df_estado["unidad"] == unidad)
    ].index[0]
    return df_estado, idx


def fecha_inicio_por_defecto(hoy: date) -> date:
    """Fecha inicial por defecto para algunos formularios (día 19 del mes actual)."""
    return date(hoy.year, hoy.month, DIA_INICIO)


def _unidades_habilitadas(allowed_units: list[str] | None) -> list[str]:
    if not allowed_units:
        return UNIDADES
    unidades_validas: list[str] = []
    for unidad in allowed_units:
        if unidad in UNIDADES and unidad not in unidades_validas:
            unidades_validas.append(unidad)
    return unidades_validas or UNIDADES


def _seleccionar_unidad(unidades_disponibles: list[str]) -> str:
    st.sidebar.title("Configuración de unidad")
    if len(unidades_disponibles) == 1:
        unidad = unidades_disponibles[0]
        st.sidebar.info(f"Unidad asignada: **{unidad}**")
        return unidad
    return st.sidebar.selectbox(
        "Seleccione la unidad con la que quiere trabajar:",
        unidades_disponibles,
    )


def _cerrar_sesion() -> None:
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()


def run_operativos_verano_app(
    allowed_units: list[str] | None = None,
    configure_page: bool = True,
) -> None:
    if configure_page:
        st.set_page_config(page_title=APP_TITLE, layout="wide")

    unidades_disponibles = _unidades_habilitadas(allowed_units)

    _cerrar_sesion()

    # -------------------------------------------------------------------
    # SESSION STATE
    # -------------------------------------------------------------------
    if "pantalla" not in st.session_state:
        st.session_state["pantalla"] = "bienvenida"

    if "unidad_actual" not in st.session_state:
        st.session_state["unidad_actual"] = None

    unidad_seleccionada = _seleccionar_unidad(unidades_disponibles)
    st.session_state["unidad_actual"] = unidad_seleccionada
    unidad_actual = unidad_seleccionada

    # -------------------------------------------------------------------
    # LÓGICA PRINCIPAL
    # -------------------------------------------------------------------
    hoy = date.today()

    # Si todavía no llegamos a la fecha de inicio, no se habilita la carga
    if hoy < START_DATE:
        st.title("BIENVENIDO AL SISTEMA DE CARGA OPERATIVOS VERANO")
        st.subheader(f"Unidad: {unidad_actual}")
        st.info(
            "La planilla de carga de OPERATIVOS VERANO comenzará a utilizarse "
            f"a partir del día {START_DATE.strftime('%d/%m/%Y')} ."
        )
        st.stop()

    df_estado = cargar_estado()

    # Buscar la primera fecha entre START_DATE y hoy cuya carga NO esté completa
    # para la unidad_actual
    fecha_objetivo = None
    idx_estado = None

    dia = START_DATE
    while dia <= hoy:
        df_estado, idx = asegurar_fila_estado(df_estado, dia, unidad_actual)
        anexo1_completo = bool(df_estado.loc[idx, "anexo1_completo"])
        anexo2_completo = bool(df_estado.loc[idx, "anexo2_completo"])

        if not (anexo1_completo and anexo2_completo):
            fecha_objetivo = dia
            idx_estado = idx
            break

        dia += timedelta(days=1)

    # Si fecha_objetivo sigue en None → esta unidad está al día hasta hoy
    if fecha_objetivo is None:
        st.title("BIENVENIDO AL SISTEMA DE CARGA OPERATIVOS VERANO")
        st.subheader(f"Unidad: {unidad_actual}")
        st.subheader("Estado de la carga")

        ultima_fecha_operativos = hoy - timedelta(days=1)
        st.success(
            f"La unidad **{unidad_actual}** está al día con la carga de OPERATIVOS VERANO.\n\n"
            f"La última fecha de operativos cargados es: "
            f"{ultima_fecha_operativos.strftime('%d/%m/%Y')}.\n\n"
            "ESPERE AL DÍA SIGUIENTE PARA CONTINUAR."
        )
        st.stop()

    # A partir de acá trabajamos sobre la fecha_objetivo encontrada
    fecha_default = fecha_inicio_por_defecto(hoy)
    anexo1_completo = bool(df_estado.loc[idx_estado, "anexo1_completo"])
    anexo2_completo = bool(df_estado.loc[idx_estado, "anexo2_completo"])

    # Mensaje de cambio de día (si viene de la ejecución anterior)
    mensaje_cambio = st.session_state.pop("mensaje_cambio_dia", None)
    if mensaje_cambio:
        st.success(mensaje_cambio)

    # Pantalla inicial según estado para esa fecha_objetivo
    if st.session_state["pantalla"] == "bienvenida":
        if not anexo1_completo:
            st.session_state["pantalla"] = "anexo1"
        elif anexo1_completo and not anexo2_completo:
            st.session_state["pantalla"] = "anexo2"

    # -------------------------------------------------------------------
    # PANTALLA ANEXO I
    # -------------------------------------------------------------------
    if st.session_state["pantalla"] == "anexo1":
        # ruta_excel se ignora dentro de mostrar_anexo1 (usa archivos por unidad),
        # pero se mantiene el parámetro para compatibilidad
        finalizado_anexo1 = mostrar_anexo1(
            ruta_excel=ANEXO1_PATH,
            fecha_objetivo=fecha_objetivo,
            fecha_default=fecha_default,
        )

        if finalizado_anexo1:
            df_estado.loc[idx_estado, "anexo1_completo"] = True
            guardar_estado(df_estado)
            st.success("ANEXO I COMPLETO")
            st.session_state["pantalla"] = "anexo2"
            st.rerun()

        st.stop()

    # -------------------------------------------------------------------
    # PANTALLA ANEXO II
    # -------------------------------------------------------------------
    if st.session_state["pantalla"] == "anexo2":
        finalizado_anexo2 = mostrar_anexo_2(
            ruta_excel=ANEXO2_PATH,
            fecha_objetivo=fecha_objetivo,
            fecha_default=fecha_default,
        )

        if finalizado_anexo2:
            df_estado.loc[idx_estado, "anexo2_completo"] = True
            guardar_estado(df_estado)
            st.success("ANEXO II COMPLETO")

            # Buscar siguiente día con carga pendiente (si hay)
            dia = fecha_objetivo + timedelta(days=1)
            prox_fecha = None
            while dia <= hoy:
                df_estado, idx = asegurar_fila_estado(df_estado, dia, unidad_actual)
                anexo1_completo = bool(df_estado.loc[idx, "anexo1_completo"])
                anexo2_completo = bool(df_estado.loc[idx, "anexo2_completo"])
                if not (anexo1_completo and anexo2_completo):
                    prox_fecha = dia
                    break
                dia += timedelta(days=1)

            if prox_fecha:
                st.session_state["mensaje_cambio_dia"] = (
                    f"Se completó la carga del día {fecha_objetivo.strftime('%d/%m/%Y')} "
                    f"para la unidad {unidad_actual}. Ahora puede continuar con el día "
                    f"{prox_fecha.strftime('%d/%m/%Y')}"
                )
            else:
                st.session_state["mensaje_cambio_dia"] = (
                    f"La unidad {unidad_actual} está al día hasta el {fecha_objetivo.strftime('%d/%m/%Y')}. "
                    "ESPERE AL DÍA SIGUIENTE PARA CONTINUAR."
                )

            st.session_state["pantalla"] = "bienvenida"
            st.rerun()

        st.stop()


if __name__ == "__main__":
    run_operativos_verano_app(configure_page=True)
