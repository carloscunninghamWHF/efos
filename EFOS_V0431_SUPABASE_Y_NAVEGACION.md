# EFOS v0.4.31 — Navegación fija + catálogo privado Supabase

## Cambios de interfaz
- Barra de identidad, menú de seis módulos y filtros globales fijos (`st.container(key="efos_sticky_header")`).
- Submenús de preguntas tácticas en Ataque y Defensa con posición adhesiva respecto al menú principal. En pantallas estrechas, la navegación principal es horizontal y desplazable dentro de su propia barra (no mueve el contenido).
- Separadores suaves entre contexto y módulos; pie de página universal con copyright dinámico.
- Progreso **por etapas reales**, tanto al analizar archivos locales como al descargar desde Supabase. Los porcentajes de la barra representan hitos completados, no tiempo estimado del cálculo; durante el motor se muestra un indicador de trabajo.
- Se preservan las seis secciones y los motores de la v0.4.30. Sin tablas/gráficas añadidas al dashboard.

## Infraestructura verificada
Proyecto Supabase actual: tablas `efos_organizations`, `efos_organization_members`, `efos_datasets`, `efos_matches`, `efos_match_teams`, `efos_source_files`, `efos_analysis_runs` y `efos_analysis_artifacts`. Vista con `security_invoker=true`: `efos_catalog_match_teams`. Bucket **privado** `efos-private`. Las 4 fuentes `.csv.gz` ya se registraron en el proyecto; los análisis precalculados no están disponibles todavía. EFOS los procesa al seleccionarlos.

## Activar el modo nube (sin claves administrativas)
1. En Supabase Auth, crea/invita cuentas mediante correo y contraseña. Comprueba que cada cuenta autorizada está vinculada a una organización en `efos_organization_members`. **No uses los usuarios locales como identidades Supabase.**
2. Desde el SQL Editor revisa y, si procede, aplica `SUPABASE_STORAGE_SELECT_V0431.sql`. Permite descargar únicamente objetos cuyos paths figuren en `efos_source_files`, con estado `cataloged`, para un miembro autenticado. El bucket continúa siendo privado. No otorga lectura anónima ni escritura.
3. Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` en desarrollo, o configura las dos variables equivalentes en Streamlit Community Cloud: `EFOS_SUPABASE_URL` y `EFOS_SUPABASE_ANON_KEY` (clave pública). Nunca `service_role`.
4. Reinicia `streamlit run visualization/efos_dashboard.py`. La aplicación activa **Supabase Auth** cuando ambas variables están presentes; en ausencia de ambas, mantiene el login/local. Una variable incompleta produce error de configuración, sin degradarse al login local.
5. Abre **Equipo y datos → Supabase · catálogo privado → Liga → Temporada → Equipo → Periodo → Partidos**. La aplicación consulta la vista RLS, vuelve a comprobar autorización al pulsar **Descargar muestra privada y analizar**, descarga el `.csv.gz` privado y verifica bytes y SHA256 antes de ejecutar el pipeline.
6. Las fuentes descargadas se guardan temporalmente bajo `.runtime/supabase_cache/<hash_usuario>/<sha256>.csv.gz`, excluidas de Git. Cada análisis conserva identificación de dataset y muestra. Para Cloud deployment, asigna memoria/tiempo suficiente: un CSV wide puede ser grande y los motores no son trabajos asíncronos todavía.

## Contrato de permisos
- `anon_key`: **pública**, permite iniciar sesión por Supabase Auth y consultar PostgREST como usuario autenticado.
- `access_token`: sólo en `st.session_state`, enviado como `Bearer` a PostgREST y Storage. Renovación automática del token de acceso; no se guarda en código ni archivos.
- `service_role`: **no** se utiliza ni se solicita; las escrituras del worker siguen separadas.
- La vista está definida `security_invoker=true`, respetando RLS de las tablas origen. El dashboard no registra archivos ni inserta resultados en `efos_analysis_runs` todavía. Esa segunda integración requerirá worker y decisión explícita de arquitectura.
- Sin membresía RLS o sin política de Storage, la interfaz presenta una explicación de permisos y no intenta obtener datos mediante una clave privilegiada.

## Instalación y validación
```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run visualization/efos_dashboard.py
python3 -m pytest -q tests/test_supabase_bridge_v0431.py
```

## Limitaciones
- No se puede garantizar apariencia sticky en todas las versiones/anchos de Streamlit sin test de navegador. La estructura utiliza `st.container(key=...)` y CSS de fijación, con offsets de escritorio y móvil: probar desplazamiento largo en ambos.
- Los CSV.GZ de Supabase **sí se cargan** con pandas por extensión; los frames de tiros del export ancho se mantienen al tratar `.csv.gz` como `.csv` en la capa auxiliar. StatsBomb 360 real sigue siendo una fuente distinta.
- No existe sincronización bidireccional GitHub/Supabase: el GitHub antiguo no debe sobrescribir esta rama. El `efos.zip` local actualizado es la base del código.
