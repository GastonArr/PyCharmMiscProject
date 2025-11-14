# PyCharm Misc Project

## Configurar sincronización con Google Drive

La aplicación puede descargar y subir automáticamente los Excel y la agenda a
una carpeta compartida de Google Drive. Para habilitar esta integración se
necesita un **Service Account** con acceso a la carpeta compartida.

### 1. Credenciales del Service Account

1. Crear (o reutilizar) un Service Account desde Google Cloud Console y
   descargar el archivo JSON de credenciales.
2. Compartir la carpeta de Drive donde se alojarán los archivos con el correo
   del Service Account (aparece como `xxxx@xxxx.iam.gserviceaccount.com`).
3. Cargar las credenciales en el despliegue de Streamlit Cloud o en el entorno
   local mediante **una** de las siguientes opciones:

   - `/.streamlit/secrets.toml`

     ```toml
     [gdrive]
     folder_id = "<ID_DE_LA_CARPETA_COMPARTIDA>"

     [gdrive.service_account]
     type = "service_account"
     project_id = "..."
     private_key_id = "..."
     private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
     client_email = "..."
     token_uri = "https://oauth2.googleapis.com/token"
     # ... resto de campos del JSON original
     ```

   - Variables de entorno:

     ```bash
     export GDRIVE_FOLDER_ID="<ID_DE_LA_CARPETA_COMPARTIDA>"
     export GDRIVE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ... }'
     ```

### 2. Asociar cada archivo al recurso remoto

Para evitar ambigüedades cuando hay archivos con el mismo nombre se puede
configurar la tabla `COMISARIA_REMOTE_FILES` en `cloud_storage.py`. Cada clave
es la ruta **relativa** al proyecto (por ejemplo `excel/comisaria 14.xlsm`) y
se asocia al `file_id` exacto del archivo en la carpeta compartida.

```python
COMISARIA_REMOTE_FILES = {
    "excel/comisaria 14.xlsm": {
        "file_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
        # "remote_name": "Comisaria 14.xlsm",  # opcional
    },
    "datos/agenda_delitos.json": {
        "file_id": "1ZyXwVuTsRqPoNmLkJiHgFeDcBa",
    },
}
```

- El `file_id` se obtiene desde la URL de Google Drive (`.../d/<ID>/view`).
- `remote_name` es opcional; por defecto se usa el nombre del archivo local.
- La tabla puede dejarse vacía. La aplicación seguirá funcionando usando solo
  el nombre del archivo, pero es recomendable completar los IDs para garantizar
  que se sincroniza el recurso correcto.

Una vez configurada esta tabla, la aplicación ya se encarga de pasar el nombre
remoto y el `file_id` correcto cuando sincroniza cada archivo.

### 3. Actualizar los IDs

Cuando se agregue un nuevo Excel o se reemplace un archivo en la carpeta
compartida:

1. Crear el archivo local en la carpeta `excel/` o `datos/` según corresponda.
2. Subir o ubicar el archivo definitivo en la carpeta compartida y copiar su
   `file_id`.
3. Editar `COMISARIA_REMOTE_FILES` en `cloud_storage.py` para agregar o
   actualizar la entrada con el nuevo `file_id`.
4. (Opcional) Reiniciar la aplicación para que tome los cambios si el entorno
   no los recarga automáticamente.

Con estas configuraciones el Service Account descargará los Excel existentes al
iniciar la aplicación y subirá los cambios cada vez que se guarden registros.
