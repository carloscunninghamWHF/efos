# EFOS v0.4.31 — Parche de gráficos y Balón parado

## Qué corrige
- Recuperación de claves de posesión compuestas al abrir un análisis persistente de Supabase.
- Mapa «Una secuencia, una historia» con la clave real, no su representación textual.
- Conservación de atributos de evidencia del análisis al serializar DataFrames.
- Compatibilidad con los análisis ya guardados en la versión inicial v0.4.31.
- Diagnóstico por tipo y perspectiva en Balón parado; selección inicial de una categoría con eventos.
- Indicador «Muestra del archivo» en lugar de afirmar una temporada completa para selecciones parciales.

Este parche no toca los cálculos del motor de análisis, la base de datos, las credenciales ni los archivos de StatsBomb.
El análisis guardado de Guadalajara no requiere volver a procesarse.

## Instalación en Mac / VS Code
1. Detén Streamlit desde la terminal con Ctrl+C.
2. Abre en VS Code la carpeta efos que ya tienes configurada con .streamlit/secrets.toml.
3. Abre una terminal de VS Code ubicada en la raíz efos (deben existir las carpetas ui y visualization).
4. Si el ZIP se encuentra en Descargas, ejecuta exactamente:

   unzip -o "$HOME/Downloads/EFOS_v0_4_31_PARCHE_GRAFICAS_BALON_PARADO.zip" -d .

5. Reinicia Streamlit:

   python3 -m streamlit run visualization/efos_dashboard.py

6. En EFOS, pulsa Salir, inicia sesión nuevamente, elige
   Liga MX -> 2024-2025 -> Guadalajara -> p1 -> los tres partidos.
   Pulsa Abrir análisis guardado y comprueba Informe Ejecutivo y Balón parado.

## Qué comprobar
- En Informe Ejecutivo, el mapa «Una secuencia, una historia» debe mostrar acciones numeradas
  cuando la secuencia tenga coordenadas registradas.
- En Balón parado verás un resumen por córners/tiros libres/saques y perspectiva.
  Si una combinación no tiene eventos, EFOS lo indicará en lugar de fabricar jugadas.
- Si el gráfico está vacío porque faltan coordenadas, la interfaz lo informa expresamente.

## Validación
25 pruebas dirigidas superadas (persistencia, gráficos, balón parado, Supabase y ataque).
La suite íntegra no pudo ejecutarse en el entorno de pruebas porque allí falta la dependencia Streamlit.
La validación final del dashboard se realiza en tu Mac.

## Seguridad
No modifiques o compartas .streamlit/secrets.toml. El parche no incluye secretos.
