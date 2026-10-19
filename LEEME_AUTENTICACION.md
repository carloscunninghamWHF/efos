# EFOS v0.4.31 — Corrección definitiva de Supabase Auth

## Por qué fallaba
El dashboard permitía iniciar sesión usando `auth/users.txt` cuando `SB.config()`
no encontraba la configuración, aunque EFOS ya utiliza Supabase Auth.
El archivo local de usuarios no existe en la distribución de código para GitHub.

## Qué hace este parche
- **Elimina la alternativa de autenticación local** en la pantalla de acceso.
- Busca `.streamlit/secrets.toml` dentro de la carpeta real `efos`, aunque VS Code
  o Streamlit se hayan iniciado desde otro directorio.
- Mantiene compatibilidad con Streamlit Cloud: si no hay archivo local, utiliza
  `st.secrets` / variables de entorno.
- Si la configuración falta, informa el problema en pantalla. No solicita ni
  utiliza `auth/users.txt`.
- Parte de la versión que **ya incorpora** las correcciones anteriores de gráficas,
  posesiones y Balón parado, sin modificar las fórmulas del motor.
- No agrega secretos ni requiere procesar de nuevo Guadalajara.

## Instalar desde VS Code en Mac

1. Detén Streamlit usando `Ctrl+C`.
2. Coloca `EFOS_v0_4_31_FIX_LOGIN_SUPABASE.zip` en la carpeta **Descargas**.
3. Abre Terminal en el directorio `efos`, donde existe `visualization/efos_dashboard.py`.
4. Ejecuta:
   ```bash
   unzip -o "$HOME/Downloads/EFOS_v0_4_31_FIX_LOGIN_SUPABASE.zip" -d .
   ```
5. Comprueba (sin mostrar ni revelar secretos):
   ```bash
   python3 - <<'PY'
   from pathlib import Path
   import tomllib
   p=Path('.streamlit/secrets.toml')
   print('secrets.toml:', 'PRESENTE' if p.is_file() else 'NO ENCONTRADO')
   if p.is_file():
       c=tomllib.loads(p.read_text())
       print('URL:', 'OK' if c.get('EFOS_SUPABASE_URL') else 'FALTA')
       print('Clave pública:', 'OK' if str(c.get('EFOS_SUPABASE_ANON_KEY','')).startswith('sb_publishable_') else 'REVISAR')
   PY
   ```
6. Ejecuta:
   ```bash
   python3 -m streamlit run visualization/efos_dashboard.py
   ```
7. Inicia sesión con Supabase Auth y selecciona el análisis guardado de Guadalajara.

**Seguridad:** NO compartas `secrets.toml`, contraseñas o claves `sb_secret_`.
El ZIP no incluye `secrets.toml` ni cambia datos de Supabase.
