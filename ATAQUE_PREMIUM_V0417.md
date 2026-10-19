# EFOS v0.4.17 — Ataque organizado con evidencia

## Ejecutar
Desde la carpeta `efos`, ejecutar:

```bash
python -m pip install -r requirements.txt
python -m streamlit run visualization/efos_dashboard.py
```

Abrir el módulo Ataque Organizado después de seleccionar el equipo. La carga CSV personalizada también incluye el módulo de ataque. No se requieren nuevas dependencias respecto a v0.4.16.

## Cambios
- Ocho visualizaciones del paquete aportado por el usuario, adaptadas a datos reales.
- Cinco vistas: Identidad, Salida y conexiones, Progresión, Llegada y finalización, Prioridades y evidencia.
- Filtros de partido, tipo de posesión, jugador y minuto de inicio; marcador cuando existe score_state. No se reconstruye un marcador ausente.
- Red dirigida y atlas de seis familias; selección de conexión y de secuencia.
- Hallazgos descriptivos con denominadores, propuestas para revisión y eventos fuente.
- CSV de secuencias y cobertura de campos; datos ausentes permanecen ausentes.
- Se amplía el mapeo CSV con receptor, presión, OBV, cambio de orientación y etiquetas de posesión.

## Trazabilidad conceptual
| Componente EFOS | Aplicación implementada | Límite |
|---|---|---|
| CTS | Perfil descriptivo de conexiones, rutas y mecanismos | No se sustituye ni recalibra la fórmula CTS existente |
| PCI/HPS | Comparación de pases con/sin presión marcada y continuación del receptor | No recalcula HPS; comparación sin ajuste causal |
| OC | Red relacional observable complementaria | No modifica OC ni equivale a cohesión social o posición simultánea |
| Tactical Framework | Reglas espaciales y cadenas de pases | Hipótesis operativas, pendientes de validación experta |
| RPS/DS/DER/ESI | Se conservan los cálculos anteriores | No se crea un ESI ofensivo ni se afirma calidad decisional |
| OBV / xG | Valor disponible del proveedor | No son modelos originales de EFOS; se muestra cobertura |
| Coach Story | Narrativa ligada a secuencias y eventos | Propuestas de revisión, no predicciones ni prescripciones |

IIS, COI, CVS, ECS y APE no se incorporan en este sprint. No se afirma validación científica de los índices. La red relacional es un complemento y no una nueva fórmula calibrada.

## Definiciones operativas
Coordenadas normalizadas StatsBomb 120×80, ataque hacia +X. Las distancias X no son metros.

- Se excluyen completas las posesiones con reanudaciones etiquetadas, incluidos saques de puerta y laterales. Por tanto, la salida desde saque de puerta queda fuera del alcance de este módulo.
- Se divide la evidencia ante intervenciones rivales con balón e interrupciones explícitas; el identificador interno es partido, periodo, posesión y segmento. No se mezclan partidos ni periodos.
- Transición: cualquier etiqueta is_transition verdadera o From Counter. Posesión controlada: is_controlled_possession verdadera sin transición. El resto se llama juego abierto sin clasificación. Son reglas de agregación de EFOS sobre etiquetas del proveedor, no clasificación universal de ataque organizado.
- A→B→C: pases completos consecutivos entre acciones relevantes, destinatario B como siguiente pasador, tres jugadores distintos, ≤4 segundos, avance total ≥15 X y segundo pase ≥8 X. No prueba tercer hombre ni apoyo de primera.
- Continuación: siguiente acción relevante del receptor, en ≤8 segundos y ≤6 posiciones del índice. No se salta a una acción futura tras una intervención de otro jugador.
- Medios espacios: destino x=70–95, y=18–30 o 50–62. No prueba recepción entre líneas. La presión coloreada pertenece al pase.
- Cambio de orientación: pass_switch y desplazamiento lateral absoluto ≥20. Sin etiqueta no se infiere a partir de longitud.
- Entrada al área: destino x≥102 e y=18–62, con origen fuera; pase completo o conducción. La figura de rutas distingue pases al área; la tabla de secuencias incorpora ambos.
- Las redes usan medianas de ubicaciones de pase/recepción; las seis familias se solapan. No son seis categorías MECE ni seis formaciones. Volumen y valor son dimensiones diferentes.
- Directicidad: mediana de valores disponibles dentro de la secuencia y media entre secuencias. Se informa variación interna. Su interpretación depende del contrato del campo exportado.
- La pizarra divide acciones en tres grupos cronológicos; no detecta fases tácticas ni interpola movimientos.
- Las tasas se calculan sobre toda la selección; mapas limitan trayectorias y enlaces por legibilidad. La red de temporada puede reunir jugadores que no coincidieron: usar filtros de partido/tramo.
- El OBV de enlaces puede incluir cobertura parcial; ver cobertura y eventos fuente. No se rellena valor ausente con cero.
- Convención de resultado vacío=completado solo para exports StatsBomb o CSV cuyos significados se hayan confirmado en el importador. Sin columna de resultado no se computan completados.

## Sustento y validación pendiente
La literatura fundamenta el enfoque relacional y contextual, no los pesos ni los umbrales propios de EFOS:

1. *Defining a historic football team: Using Network Science to analyze Guardiola’s F.C. Barcelona* (2019). Scientific Reports. https://doi.org/10.1038/s41598-019-49969-2 — redes de pase temporales frente a promedios globales.
2. *Consistency and identifiability of football teams: a network science perspective* (2020). Scientific Reports. https://doi.org/10.1038/s41598-020-76835-3 — redes espaciales y consistencia de comportamientos.
3. *Interpersonal Dynamics in 2-vs-1 Contexts of Football: The Effects of Field Location and Player Roles* (2019). https://doi.org/10.3389/fpsyg.2019.01407 — restricciones espaciales y coordinación. No valida inferencias de posiciones a partir de eventos.
4. StatsBomb, *Introducing On-Ball Value*. https://blogarchive.statsbomb.com/news/introducing-on-ball-value-obv/ — alcance del modelo de valor del proveedor.

Antes de afirmar validez táctica: etiquetado independiente de secuencias por analistas, revisión de falsos positivos/negativos, sensibilidad de ventanas y zonas, comparación por rival/marcador y evaluación fuera de la muestra. Antes de afirmar valor predictivo: definición de objetivo, separación temporal de entrenamiento/evaluación y comparación con baselines. Este sprint es descriptivo.

## Archivos
- intelligence/organized_attack.py: secuencias, filtros, conexiones y hallazgos.
- visualization/efos_smart_attack_graphs.py: las ocho figuras adaptadas.
- visualization/organized_attack_app.py: interfaz y evidencia.
- tests/test_organized_attack.py: continuidad, ausencias, filtros, reanudaciones y figuras.
- docs/ataque_atlas_real.html: vista autónoma del atlas, calculada con los datos incluidos, no sintética.
