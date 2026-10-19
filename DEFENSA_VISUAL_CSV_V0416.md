# EFOS 0.4.16 · Defensa con contexto y CSV flexible

## Abrir la plataforma
Desde la carpeta efos, con las dependencias de requirements.txt instaladas:

```bash
python -m streamlit run visualization/efos_dashboard.py
```

## Defensa organizada
- Vulnerabilidad: volumen de entradas por carril, proporción con remate y distribución por partido. Las tablas quedan como respaldo desplegable.
- Selector de carril y desenlace conectado con una posesión real: inicio, intervenciones, desenlace, cancha y cronología verificable.
- Patrones: rutas repetidas por carril de entrada y zona del primer remate posterior (o sin remate). Selector de todas las rutas con al menos dos casos; número de partidos y señal exploratoria visibles.
- Contrapresión: canchas separadas de primera acción etiquetada y primer control confirmado; ejemplo de posesión vinculado con el evento posterior de control.
- Análisis integral: confirmación del control, señal zonal prioritaria y pregunta concreta para contrastar en una jugada.
- Todos los segmentos representan eventos observados. No se interpolan movimientos, coberturas ni espacios libres.

## Importar otro equipo
Selección de Equipo → Cargar CSV de cualquier equipo.
1. Cargar uno o varios CSV con la misma estructura. Deben incluir ambos equipos.
2. Revisar codificación y separador; relacionar columnas. Traducir los tipos de evento al vocabulario mostrado.
3. Confirmar dimensiones, orientación y significado de resultados. En coordenadas fijas, proporcionar por evento dirección 1 o -1 del equipo actor.
4. Revisar calidad, seleccionar equipo y partidos. El análisis defensivo aparece dentro del mismo flujo de carga.

El importador alimenta el atlas defensivo y su análisis integral. Los informes de los otros módulos conservan su flujo de repositorio; no se regeneran desde esta nueva pantalla. Se pueden exportar eventos normalizados e informe de calidad.

Campos para el atlas: match_id, period, index, possession, team, possession_team, event_type, minute, second, play_pattern_name; coordenadas de inicio y fin; resultado de pase (outcome_name o pass_outcome). Requiere confirmar semántica StatsBomb: pase con resultado vacío = completado. Los campos vacíos opcionales permanecen ausentes; no se crean posesiones, tiempos, xG ni etiquetas de presión.

Los duplicados exactos del evento mapeado se consolidan y se cuentan (por ejemplo, filas de freeze frame del export ancho). Los tipos de evento desconocidos y órdenes duplicados con contenido distinto bloquean el atlas. Carries se normaliza a Carry. Filas incompletas o relojes inválidos se excluyen con recuento visible; coordenadas fuera de rango se anulan. Los ID ausentes se identifican como csv-row-N, referencias locales, no ID del proveedor. La evidencia conserva los IDs presentes.

CSV agregado: filtrar y ver los registros por equipo, sin reconstruir secuencias ni sumar porcentajes sin denominador. CSV de eventos incompleto: resumen por tipo de evento y explicación de los requisitos faltantes. No todos los CSV contienen información suficiente para todas las vistas.

## Límites de interpretación
- Entrada: primer pase completado o conducción de x<80 a x>=80. La clasificación cuenta una vez cada posesión.
- Sin remate no implica recuperación ni éxito defensivo. El remate posterior puede ocurrir en otro carril.
- Patrón repetido significa ruta de eventos similar, no una intención o formación demostrada.
- Umbral 30 posesiones y 5 partidos: criterio exploratorio heredado, no validación estadística ni causal.
- Contrapresión requiere etiqueta del proveedor. Control posterior no equivale a robo causado por presión.
- Los archivos de datos originales incluidos se mantienen byte por byte.
