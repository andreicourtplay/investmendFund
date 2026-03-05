# Funds Weekly Dashboard

Dashboard en Streamlit para cargar Excel/CSV de fondos, publicar un dataset y compartir una vista en modo lectura.

## Requisitos

- Python 3.9+

## Ejecutar local

```bash
./run_dashboard.sh
```

## Seguridad (admin para publicar)

La app lee la password de admin desde:

1. `st.secrets["ADMIN_PASSWORD"]` (recomendado en Streamlit Cloud)
2. variable de entorno `FUNDS_ADMIN_PASSWORD`

Ejemplo local (no se versiona):

```toml
# .streamlit/secrets.toml
ADMIN_PASSWORD = "tu-password-segura"
```

El archivo real `.streamlit/secrets.toml` está ignorado en git.

## Deploy en Streamlit Community Cloud

1. Sube este repo a GitHub.
2. Entra a https://share.streamlit.io
3. New app:
   - Repository: `andreicourtplay/investmendFund`
   - Branch: `main`
   - Main file path: `app.py`
4. En `Advanced settings -> Secrets` agrega:

```toml
ADMIN_PASSWORD = "tu-password-segura"
```

5. Deploy y comparte el link público de Streamlit.

## Flujo de uso

1. Entras como admin con password.
2. Subes tus archivos y pulsas `Publicar dataset`.
3. Compartes el link: otros usuarios solo ven el dashboard publicado.

## Nota de persistencia

En Streamlit Community Cloud, el filesystem local puede resetearse al reiniciar la app. Si necesitas persistencia fuerte del dataset publicado, conviene guardar en una base de datos o storage externo (S3, Supabase, etc.).
