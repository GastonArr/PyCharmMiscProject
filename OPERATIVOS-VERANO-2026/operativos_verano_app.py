import streamlit as st
import pandas as pd
import os
from datetime import date, timedelta

from ANEXO_1 import mostrar_anexo1
from ANEXO_2 import mostrar_anexo_2

# -------------------------------------------------------------------
# CONFIGURACIÓN BÁSICA
# -------------------------------------------------------------------
st.set_page_config(page_title="Operativos Verano", layout="wide")

EXCEL_DIR = "Excel"

# Este parámetro ya no se usa para elegir archivo (eso se hace por unidad),
# pero lo dejamos por compatibilidad con las funciones de los anexos.
ANEXO1_PATH = os.path.join(EXCEL_DIR, "ANEXO I DIAGRAMAS OP VERANO DSICCO.xlsx")
ANEXO2_PATH = os.path.join(EXCEL_DIR, "ANEXO II RESULTADOS OP VERANO.xlsx")

ESTADO_PATH = "estado_carga_operativos.csv"
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
    if os.path.exists(ESTADO_PATH):
        df = pd.read_csv(ESTADO_PATH)
        # Aseguramos columnas mínimas
        if "fecha" not in df.columns or "unidad" not in df.columns:
            df = pd.DataFrame(columns=["fecha", "unidad", "anexo1_completo", "anexo2_completo"])
    else:
        df = pd.DataFrame(columns=["fecha", "unidad", "anexo1_completo", "anexo2_completo"])

    # Convertimos fecha a datetime
    if not df.empty:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

    return df


def guardar_estado(df_estado):
    df_estado.to_csv(ESTADO_PATH, index=False)


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


# -------------------------------------------------------------------
# SESSION STATE
# -------------------------------------------------------------------
if "pantalla" not in st.session_state:
    st.session_state["pantalla"] = "bienvenida"

if "unidad_actual" not in st.session_state:
    st.session_state["unidad_actual"] = None


# -------------------------------------------------------------------
# SELECCIÓN DE UNIDAD (por ahora manual; luego será login)
# -------------------------------------------------------------------
st.sidebar.title("Configuración de unidad")
unidad_seleccionada = st.sidebar.selectbox(
    "Seleccione la unidad con la que quiere trabajar:",
    ["(Seleccione una unidad)"] + UNIDADES,
)

if unidad_seleccionada == "(Seleccione una unidad)":
    st.title("BIENVENIDO AL SISTEMA DE CARGA OPERATIVOS VERANO")
    st.info("Por favor, seleccione una unidad en el menú lateral para comenzar.")
    st.stop()

# Guardamos la unidad actual en session_state
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
        f"a partir del día {START_DATE.strftime('%d/%m/%Y')}."
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
        st.session_state["pantalla"] = "anexo2"
        st.rerun()


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

        # Día de los operativos que se cargaron en ANEXO 2 (fecha_objetivo - 1)
        fecha_carga = fecha_objetivo - timedelta(days=1)
        # Fecha objetivo siguiente
        fecha_siguiente = fecha_objetivo + timedelta(days=1)

        if fecha_objetivo == hoy:
            # Si la fecha objetivo ya es HOY, mostramos pantalla final
            st.session_state["pantalla"] = "completo"
        else:
            # Si todavía quedan días por cargar, avisamos y pasamos al siguiente día
            st.session_state["mensaje_cambio_dia"] = (
                f"Unidad **{unidad_actual}**:\n\n"
                "Se ha completado la carga de los operativos del día "
                f"{fecha_carga.strftime('%d/%m/%Y')} y se pasará al día siguiente "
                f"({fecha_siguiente.strftime('%d/%m/%Y')})."
            )
            st.session_state["pantalla"] = "bienvenida"

        st.rerun()


# -------------------------------------------------------------------
# PANTALLA FINAL
# -------------------------------------------------------------------
if st.session_state["pantalla"] == "completo":
    # Día de los operativos que se cargaron en ANEXO 2
    fecha_carga = fecha_objetivo - timedelta(days=1)

    st.title("BIENVENIDO AL SISTEMA DE CARGA OPERATIVOS VERANO")
    st.subheader(f"Unidad: {unidad_actual}")
    st.subheader("Carga finalizada")

    st.success(
        f"Ha completado la carga de los operativos de la fecha "
        f"{fecha_carga.strftime('%d/%m/%Y')} para la unidad **{unidad_actual}**."
    )
    st.info(
        "USTED ESTÁ AL DÍA CON LA CARGA PARA ESA FECHA.\n\n"
        "ESPERE AL DÍA SIGUIENTE PARA REALIZAR UNA NUEVA CARGA."
    )
