Railway deployment guide — Backend (FastAPI) and Frontend (Flet)

Resumen

Este documento explica cómo desplegar el backend (`Gestor-De-Laboratorios`) y el frontend (`gestor-frontend`) en Railway (u otro PaaS). Incluye las variables de entorno necesarias, pasos para configurar Google OAuth en Google Cloud Console, y comprobaciones post-deploy.

Requisitos

- Cuenta en Railway (o Heroku, Render, Vercel). 
- Código en un repo público o privado conectado a Railway.
- Google Cloud Console: Client ID y Client Secret creados (OAuth consent screen configurado).

Archivos importantes en el repo

- `Gestor-De-Laboratorios/Procfile` — arranca el backend con uvicorn:
  web: uvicorn main:app --host=0.0.0.0 --port=$PORT

- `gestor-frontend/Procfile` — arranca el frontend con `python main.py` (para Flet desktop/web).

- `.env` (local) — contiene: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `DATABASE_URL`, `SESSION_SECRET_KEY`, etc. NO subir este archivo al repo ni a Railway.

Paso 0 — Seguridad (IMPORTANT)

Si ya tienes un `.env` versionado (committed) en el repo, debes eliminarlo del historial y borrar el archivo en el repo. Railway no usa `.env` en el repo; debes configurar variables en el panel de Railway.

Para quitar el archivo del historial (ejemplo):

1. Eliminar del control de versiones y commitear:

   git rm --cached .env
   git commit -m "remove .env from repo"

2. Opcional: Reescribir historial para eliminar secretos (hazlo con cuidado):
   - Usar BFG o `git filter-branch`.

Paso 1 — Variables de entorno necesarias (Backend)

En Railway, en el proyecto Backend -> Settings -> Variables, añade las siguientes variables:

- GOOGLE_CLIENT_ID (ej: 322045933748-...apps.googleusercontent.com)
- GOOGLE_CLIENT_SECRET
- DATABASE_URL (tu cadena Postgres)
- SESSION_SECRET_KEY (random secret for sessions)
- GOOGLE_SERVICE_ACCOUNT_FILE (si usas service account para calendar; en producción se recomienda usar secretos gestionados o variables con contenido JSON)
- GOOGLE_CALENDAR_ID (si aplica)
- LOCAL_TIMEZONE (ej: America/Mexico_City)

Notas:
- No pongas el archivo JSON del service account en una variable si puedes evitarlo: Railway supports uploading secrets/files via project settings or puedes utilizar un storage seguro.
- `main.py` ahora incluye un `load_dotenv()` opcional para facilitar pruebas locales; en Railway no es necesario.

Paso 2 — Configurar OAuth en Google Cloud Console

1. En Google Cloud Console -> APIs & Services -> OAuth consent screen: configura tu aplicación (tipo Internal/External según corresponda).
2. Crear credenciales -> OAuth 2.0 Client IDs -> Tipo: Web application
   - Name: Gestor-De-Laboratorios
   - Authorized JavaScript origins: añade la URL pública de Railway (ej: https://tu-backend.up.railway.app)
   - Authorized redirect URIs: si usas redirect flow (no copy/paste), añade la URL de callback (ej: https://tu-backend.up.railway.app/auth/google/callback). Para el flujo copy/paste no es estrictamente necesario, pero si quieres el redirect automatico añade esta.
3. Copia `Client ID` y `Client Secret` y pégalos en Railway como variables.

Paso 3 — Despliegue en Railway

Opción A: Backend y Frontend como servicios separados (recomendado)

- Crea dos proyectos en Railway o un monorepo con dos deployments (cada servicio con su carpeta raíz):
  - Servicio Backend: path `Gestor-De-Laboratorios`
  - Servicio Frontend: path `gestor-frontend` (si piensas desplegar la UI web)

- Conecta el repo a Railway, crea un servicio, selecciona la carpeta correcta para cada servicio.
- Añade las variables de entorno del Paso 1 al proyecto Backend.
- Deploy.

Opción B: Monolito (único servicio)

- Si deseas desplegar sólo el backend y ejecutar el frontend como aplicación de escritorio local, sube sólo `Gestor-De-Laboratorios`.

Paso 4 — Verificaciones post-deploy

1. Abrir `https://<tu-backend>.up.railway.app/auth/google` en el navegador — deberías ver la página que genera un ID token tras autenticar con Google (esto es la página helper que añadimos).
2. En la app Flet (o frontend desplegado), al hacer click en "Iniciar con Google" deberías poder abrir el `auth/google` o copiar el id_token y pegarlo en el diálogo — el backend verificará y devolverá un JWT.
3. Revisa logs en Railway para ver errores de verificación si hay problemas con `GOOGLE_CLIENT_ID`.

Problemas comunes y soluciones

- 404 en `/auth/google`: posiblemente el código no fue desplegado o tu servicio no apunta a la carpeta correcta. Asegúrate de que Railway ejecuta `uvicorn main:app` en la carpeta `Gestor-De-Laboratorios`.
- `invalid_client` en Google: revisa que `GOOGLE_CLIENT_ID` coincide con el ID en Google Cloud Console y que el origen/redirect URI está registrado.
- Secrets en repo: borra y reescribe historial si fue comprometido.

Comprobaciones rápidas desde tu máquina

```powershell
# desde la carpeta Gestor-De-Laboratorios
python -m uvicorn main:app --reload --port 8000
# en otro shell
curl http://127.0.0.1:8000/auth/google -i
```

Si quieres, puedo:

- Generar un archivo `railway_deploy.md` con pasos CLI (railway up) y un ejemplo de cómo mapear carpetas en el dashboard.
- Preparar un pequeño script para validar que `GOOGLE_CLIENT_ID` está cargado en tiempo de arranque y así evitar errores silenciosos.

---

Cambios mínimos realizados en el repo para compatibilidad: `main.py` ahora intenta `load_dotenv()` durante import para que las variables locales funcionen durante pruebas.

Si quieres que añada el `README_DEPLOY_RAILWAY.md` también al frontend o que cree un `railway_deploy.md` con comandos exactos, dime y lo añado.
