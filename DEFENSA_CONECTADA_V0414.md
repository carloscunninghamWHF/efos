# EFOS v0.4.14 — Defensa explicada y conectada

## Objetivo
Que un entrenador pueda entender los gráficos sin conocer las métricas ni las reglas del clasificador y pasar de una observación a una pregunta verificable.

## Recorrido en Sin balón
1. **Entender las tres respuestas.** Definición futbolística, pregunta de análisis y criterio de clasificación de reacción tras pérdida, contraataque y ataque posicional. Canchas con escala común y tabla con denominadores, presión y cobertura de xG.
2. **Conectar tiempo, jugadores y jugadas.** Evolución por tramos, selección de tramo y partido, red de participantes de esa muestra y posesión concreta con desenlace, cronología e instantánea 360 si existe.
3. **Análisis integral.** Resume qué ocurrió, cuándo, quién participó, qué contrastar en jugadas, una propuesta de revisión para entrenamiento y las limitaciones de la evidencia.

## Alcance de filtros
- Situación, tramo y marcador de la cabecera gobiernan la síntesis.
- El atlas compara las tres situaciones con el mismo tramo y marcador.
- La línea temporal conserva todos los tramos de la situación y marcador para permitir comparación. Se explica este alcance junto al gráfico.
- Los filtros locales de investigación refinan la red y el selector de posesiones; no alteran la síntesis global. La muestra está rotulada.
- Se muestran todas las posesiones elegibles, sin el límite previo de 150 ni la selección automática de las que tuvieron más remates.

## Explicación visual
- Sombreado: volumen absoluto de intervenciones por zona, misma escala y celdas en las tres canchas.
- Puntos: primera intervención defensiva registrada.
- Flechas: hasta tres rutas de balón agregadas entre zonas; no desplazamientos de defensores.
- Red: hasta siete jugadores por volumen; conexiones en al menos dos posesiones compartidas. No demuestra cobertura ni coordinación.
- Secuencia: pase continuo, conducción punteada, intervención numerada, remate con cruz.
- Línea: tramos de inicio de posesión, no una observación minuto a minuto. Huecos sin datos no se conectan.

## Compatibilidad
No cambia las reglas del motor de clasificación ni los archivos de datos. El módulo anterior se conserva como archivo complementario y no alimenta la nueva síntesis, porque incluye otras categorías y balón parado.

## Ejecución
Desde la carpeta `efos`, con el entorno y dependencias del proyecto activos:

```bash
python -m streamlit run visualization/efos_dashboard.py
```

## Validación
Las 11 pruebas existentes del atlas pasan. Se agregan dos pruebas del flujo conectado: ausencia de una situación no se representa como riesgo cero; navegación Streamlit, selección de tramo/partido/xG y manejo de filtro sin datos. Se comprueba además la generación del atlas con los datos reales incluidos. Estas pruebas no constituyen validación táctica de las hipótesis ni una prueba completa de todos los módulos de EFOS.
