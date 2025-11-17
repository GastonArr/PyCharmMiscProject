# Cómo habilitar la API de Google Cloud Storage desde la consola web

Sigue estos pasos partiendo del panel de bienvenida de Google Cloud (como en la captura que compartiste):

1. En la barra superior, abre el menú **Navegador de APIs y servicios**:
   - Haz clic en el ícono de **menú lateral (≡)** ubicado en la esquina superior izquierda.
   - En el menú que se despliega, selecciona **APIs y servicios** y luego **Biblioteca**.

2. Dentro de la **Biblioteca de APIs**:
   - En la barra de búsqueda superior escribe **"Cloud Storage"**.
   - Verás varias coincidencias. Para un bucket estándar de GCS, elige:
     - **Cloud Storage** (Google Enterprise API). Es la API general de GCS y la que necesitas para subir/descargar objetos.
     - **Cloud Storage JSON API** también funciona, pero la opción recomendada en la consola es la ficha **Cloud Storage**. 
     - No selecciones **Cloud Storage for Firebase API** a menos que estés trabajando con Firebase Storage.

3. Habilita la API:
   - En la página de la API, pulsa el botón **"Habilitar"**.
   - La consola te llevará a la pantalla de configuración; espera a que termine el proceso.

4. Verifica que quedó activa:
   - En **APIs y servicios → Panel**, deberías ver **Cloud Storage API** en la lista de APIs habilitadas.

5. Próximos pasos recomendados para tu app (lo que necesitas hacer ahora):
   1) **Cuenta de servicio** (se ve en tu captura debajo de “Cuentas de servicio”):
      - Si ya tienes una, valídala; si no, crea una desde **IAM y administración → Cuentas de servicio** con el rol mínimo necesario (por ejemplo, `Storage Object Admin` o `Storage Object User` + `Storage Object Creator`).
   2) **Descargar la clave JSON** de esa cuenta de servicio:
      - En la fila de la cuenta de servicio, abre el menú de tres puntos **⋮** → **Administrar claves** → **Agregar clave** → **Crear nueva clave** → elige **JSON** → **Crear**. Se descargará un archivo `.json`.
      - Guarda ese JSON como secreto/variable en tu entorno de despliegue (Docker secret, variable de entorno, etc.); nunca lo subas al repositorio.
   3) **Configurar la app para usar la clave** (según dónde la corras):
      - **Local**: guarda el `.json` fuera del repositorio y exporta `GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/clave.json` antes de lanzar `streamlit run app.py` (o el comando que uses).
      - **Docker**: monta el archivo como *secret* o volumen y pasa la ruta en `GOOGLE_APPLICATION_CREDENTIALS`. Ejemplo: `docker run -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcs.json --secret gcs.json imagen`.
      - **Streamlit Cloud** (streamlit.io): sube el contenido del JSON a **Secrets** (`Settings → Secrets`) con una clave como `gcs_service_account="{...json...}"`. Luego en tu código: 
        ```python
        import json, streamlit as st
        from google.cloud import storage

        creds_info = json.loads(st.secrets["gcs_service_account"])
        client = storage.Client.from_service_account_info(creds_info)
        ```
        Así evitas subir el archivo al repositorio. Si prefieres usar `GOOGLE_APPLICATION_CREDENTIALS`, puedes escribir el secreto a un archivo temporal y apuntar la variable a esa ruta.
   4) **Prueba de acceso**:
      - Con la variable o el secreto configurado, ejecuta un comando simple (por ejemplo `gsutil ls gs://tu-bucket`) o un script corto con el SDK para confirmar que puedes listar/leer/escribir en el bucket.

Con esto la API de Google Cloud Storage quedará habilitada y lista para integrarla en tu aplicación.
