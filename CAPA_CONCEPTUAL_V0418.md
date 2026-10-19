# EFOS v0.4.18 — Interpretación conceptual para probar

## Qué cambia
- Se añade una biblioteca de cinco conceptos: conexiones, respuesta ante presión, recepciones interiores, llegada y defensa.
- Ataque muestra un desplegable contextual en cada una de sus cinco vistas.
- Defensa incorpora una lectura conceptual después de seleccionar la muestra.
- Coach Story incorpora contexto conceptual separado en sus claims y lo exporta a Markdown.
- El resumen ejecutivo distingue puntuación relativa de variabilidad temporal.
- Se revisan etiquetas visibles: pases completos bajo presión, combinaciones A→B→C y zonas interiores. Los identificadores de métricas se conservan.

## Contrato
Esta capa consume resultados existentes y añade texto separado. No ingiere ni modifica eventos, no recalcula índices, no altera denominadores, filtros, coordenadas o valores StatsBomb. No añade LLM, llamadas de API ni modelos predictivos.

Cada concepto incluye lectura posible, explicación alternativa, pregunta para el entrenador, límite observacional y referencias con su estado real. Las fuentes localizadas no se presentan como transcripciones verificadas. AL9 conserva estado pendiente de enlace. No se han incorporado las citas textuales ni los umbrales sugeridos por NotebookLM como reglas validadas.

La documentación aportada también menciona Zeira FC y el PDF de métricas: permanecen pendientes de identificación/lectura y no se usan para atribuir conclusiones en esta versión.

## Dónde probar
Desde efos:

```bash
python3 -m streamlit run visualization/efos_dashboard.py
```

Abrir Ataque Organizado y desplegar “Lectura táctica”. Cambiar entre Identidad, Salida y conexiones, Progresión, Llegada y finalización y Prioridades y evidencia. En Defensa, desplegar la lectura conceptual de las intervenciones. El Coach Story generado incluye el nuevo contexto; los resultados antiguos almacenados requieren volver a ejecutar el análisis para regenerar sus textos.

Los nuevos párrafos completos se exportan a Coach Story Markdown/JSON. El PDF existente recibe cambios puntuales de etiquetas; no incorpora todavía el apéndice conceptual completo. Los reportes históricos ya generados no se reescriben automáticamente.

## Validación
Ver VALIDACION_CONCEPTUAL_V0418.txt. Se compara la integridad de los archivos de datos y cálculo con v0.4.17. Las pruebas demuestran independencia de las estructuras de entrada y conservación de valores e identificadores al enriquecer claims. No equivalen a validación científica de reglas o índices.
