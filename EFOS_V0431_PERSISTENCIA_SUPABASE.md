# EFOS v0.4.31 — Integración persistente segura

## Qué se cambió (sin alterar las fórmulas tácticas)

- `ui/supabase_bridge.py`: valida certificados HTTPS (`certifi`), pagina catálogos, rechaza claves de administrador en la UI y recupera artefactos privados validando SHA-256.
- `ui/analysis_archive.py`: guarda y restaura el dict completo de `run_sprint4`, incluso DataFrames, tuplas y narrativas, como JSON comprimido **sin pickle** ni ejecución de código al abrirlo.
- `ui/analysis_identity.py`: una selección de partidos, equipo, dataset, versión y hash del código/configuración identifica inequívocamente el resultado. Cambiar el motor invalida automáticamente snapshots antiguos.
- `tools/precompute_supabase.py`: realiza los cálculos fuera de Streamlit, publica artefactos privados y cambia el estado a `ready` **solo después** de guardar el resultado.
- `visualization/efos_dashboard.py`: muestra **Abrir análisis guardado** cuando existe snapshot compatible; un análisis nuevo queda como alternativa manual bajo un desplegable.
- `.gitignore`: previene publicar secretos, CSV históricos, archivos de procesamiento y usuarios locales al subir los nuevos archivos.

**No** se han cambiado las fórmulas de ESI/CTS ni las funciones de los módulos tácticos, y no se han importado nuevos datos a `efos_events`.

## Supabase actual

- URL pública de proyecto: `https://uvcqmxjjajgensjdidso.supabase.co`.
- Bucket privado `efos-private`: 4 fuentes originales CSV.GZ ya catalogadas.
- PostgreSQL: `efos_datasets`, `efos_matches`, `efos_source_files`, `efos_match_teams`, `efos_organization_members`, `efos_analysis_runs`, `efos_analysis_artifacts`, vista `efos_catalog_match_teams`.
- Políticas de Storage `efos_private_member_cataloged_read` y `efos_private_member_ready_analysis` ya aplicadas: restringen SELECT a miembros autenticados, no permiten escritura ni acceso público.
- **Falta** crear cuentas en Supabase Auth y asignarlas a WHF; el login local no es equivalente al login de Supabase.
- **Falta** ejecutar el worker con una clave nueva de backend local; hasta entonces `efos_analysis_runs` estará vacío y Streamlit no mostrará snapshots listos.

## 1. Primer usuario autorizado

En el [panel Auth](https://supabase.com/dashboard/project/uvcqmxjjajgensjdidso/auth/users) crea/invita una cuenta real.
Una vez confirmado su correo, en SQL Editor asigna membresía. Sustituye `CORREO_AUTORIZADO`:

```sql
insert into public.efos_organization_members (organization_id, user_id, role)
select o.id, u.id, 'owner'
from public.efos_organizations o
join auth.users u on lower(u.email) = lower('CORREO_AUTORIZADO')
where o.slug = 'whf'
on conflict (organization_id, user_id) do nothing;
```

Si el `select` no encuentra la cuenta, no insertará nada; comprueba el correo en Auth. Para otros usuarios asigna `analyst`, `coach` o `viewer` después de definir su acceso. No publiques correos, contraseñas ni hashes en Git.

## 2. Instala y genera el primer snapshot con tu Mac

En VS Code, dentro de la carpeta `efos` **de este paquete**, ejecuta:

```bash
python3 -m pip install -r requirements.txt
python3 tools/precompute_supabase.py --list
```

Pega tu **nueva** `Secret key` (`sb_secret_...`) solo cuando la terminal la solicite; no se verá mientras escribes. No la guardes en el código ni en Streamlit. Anota uno de los UUID que muestra `--list` para elegir el dataset. Elige exactamente un equipo de ese dataset:

```bash
python3 tools/precompute_supabase.py --dataset-id 'UUID_DEL_DATASET' --team 'América'
python3 tools/precompute_supabase.py --dataset-id 'UUID_DEL_DATASET' --team 'América' --apply
```

`--team` tiene que coincidir con un nombre registrado. Si no coincide, el programa listará opciones.
El primer comando es **dry-run**; el segundo descarga el CSV original al caché local, procesa la muestra, la serializa y la sube al bucket privado. No se requiere volver a cargar los originales.

Después de validar **un** equipo, genera el resto de la misma temporada (puede tardar bastante):

```bash
python3 tools/precompute_supabase.py --dataset-id 'UUID_DEL_DATASET' --all-teams --apply
```

Los resultados listos se saltan automáticamente. Repite para los 4 UUID si deseas completar las 3 temporadas (Liga MX femenil permanece separada). El almacenamiento y el tiempo de procesamiento dependen de los tamaños reales y de las cuotas del plan.

**No uses `--apply` en Streamlit Cloud ni almacenes una clave secreta en las variables de Streamlit.** El worker es solo para una máquina de administración segura.

## 3. Probar Streamlit local

Crea `.streamlit/secrets.toml` basándote en `.streamlit/secrets.toml.example`. Usa **solo** la URL de proyecto y una clave pública (`sb_publishable_...` o `anon`), nunca `service_role` ni `sb_secret_`.

```bash
python3 -m streamlit run visualization/efos_dashboard.py
```

Accede con **correo y contraseña de Supabase Auth** (no las contraseñas del antiguo `auth/users.txt`).
En «Equipo y datos» elige Supabase, liga, temporada, equipo y muestra; para las selecciones precalculadas aparecerá **Abrir análisis guardado**, que se abre sin `run_sprint4`. Una combinación nueva de partidos puede requerir el worker y se identifica por otra `scope_key`.

## 4. GitHub: sustituir el código antiguo sin perder el historial

1. Descarga este ZIP y comprueba el nuevo código. Haz copia de seguridad de la carpeta local.
2. En tu clon del repositorio GitHub, crea una rama **antes** de copiar la versión nueva:

```bash
git status
git switch -c feature/efos-v0431-supabase-persistent
```

3. Copia el contenido de `efos/` del ZIP a **la raíz** de ese clon, conservando `.git/` sin modificar.
4. Como el repositorio público anterior ya tenía CSV pesados **rastreables**, comprueba primero:

```bash
git ls-files data/raw/statsbomb data/processed auth/users.txt
```

Si aparecen CSV históricos o `auth/users.txt`, sácalos del seguimiento de Git sin borrar la copia local. La decisión de limpiar el historial previo es una operación aparte:

```bash
git rm -r --cached --ignore-unmatch data/raw/statsbomb data/processed auth/users.txt
```

5. Confirma **antes** de enviar nada:

```bash
git add .
git status --short
git diff --cached --stat
```

**No subas** `.streamlit/secrets.toml`, `.env`, `auth/users.txt`, CSV históricos, ni claves secretas. Después:

```bash
git commit -m "EFOS v0.4.31 persistent Supabase integration"
git push -u origin feature/efos-v0431-supabase-persistent
```

6. En GitHub abre una pull request hacia `main`, revisa los cambios, y actualiza Streamlit Cloud **solo cuando hayas verificado que esta versión funciona**. En Streamlit Cloud configura las mismas dos variables **públicas** en los Secrets de la aplicación. Streamlit Cloud seguirá al branch configurado; no cambia automáticamente a una rama nueva.

## 5. Validación

```bash
python3 -m pytest -q tests/test_analysis_persistence_v0431.py tests/test_supabase_bridge_v0431.py
```

Se probó una muestra real de un partido StatsBomb incluida en el ZIP original del usuario, con el motor v0.4.31. El artefacto resultante se pudo recuperar, incluyendo DataFrames y Coach Story. El paso admin → Storage → Auth → Streamlit aún necesita una prueba de extremo a extremo con una cuenta autorizada y una clave nueva, que no se solicita en el chat.

## Límites conocidos

- El snapshot JSON.GZ tiene un límite prudente de 48 MiB por archivo. En muestras enormes podría requerirse partición en varios artefactos.
- Una selección de partidos distinta genera un resultado distinto: no se reutiliza indebidamente el análisis de otro conjunto.
- Cambios en la implementación/configuración del motor invalidan el resultado anterior. Mantén disponibles versiones previas hasta completar el reprocesamiento.
- La UI no tiene inferencia 360 cuando StatsBomb 360 no está disponible: conserva las limitaciones metodológicas del motor.
- No hay todavía un job scheduler cloud. El worker se ejecuta manualmente en tu Mac; si EFOS crece, muévelo a un servidor aislado con cola de trabajos.
