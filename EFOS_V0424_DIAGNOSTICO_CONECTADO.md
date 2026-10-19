# EFOS v0.4.24 — Diagnóstico táctico conectado

## Qué incluye

La lógica nueva se encuentra en `interpretation/tactical_reasoning.py`. Recibe **las salidas ya calculadas** por ataque organizado, defensa organizada y transiciones verificadas. **No recalcula ni modifica** ESI, CTS, eventos, posesiones, coordenadas ni xG del proveedor.

Por cada hallazgo genera: pregunta futbolística, observación, contexto de la muestra, interpretación condicionada, explicación alternativa, decisión de revisión, limitación, numerador, denominador y partidos analizados. No inventa datos de tracking, carreras sin balón, patrones de entrenamiento ni intenciones del DT.

### Producto y navegación

- **Informe Ejecutivo:** lectura conjunta de fases, hallazgos contextualizados, comparación gráfica de corredores y escenarios, pregunta táctica, muestra y PDF actualizado. Las tres tarjetas numéricas antiguas permanecen en un desplegable para reducir redundancias.
- **Modelo de Juego y DT:** permite desplegar la lectura común sin alterar el CTS.
- **Cómo ataca:** origen de posesiones, entradas al área, conexiones registradas y decisiones de revisión. La interpretación conectada utiliza el universo seleccionado en la muestra principal; los filtros propios del explorador ofensivo siguen siendo locales y se identifican como tales.
- **Cómo defiende:** escenarios con remates rivales, presión y recuperaciones tras pérdida verificada. Si se cambia el equipo base solo en el módulo defensivo, la lectura principal sigue indicando a qué equipo corresponde.
- **PDF ejecutivo:** incorpora interpretación y prioridades de observación, y mantiene las definiciones auditables.

### Consistencia temporal

Las transiciones del diagnóstico comparten motor con los capítulos de ataque y defensa (`intelligence.transition_story.analyze_transitions`). A partir de v0.4.24, la tarjeta del ejecutivo y el diagnóstico **no mezclan** los cambios de posesión amplios del motor histórico con pérdidas candidatas seguidas de **posesión rival confirmada**. Se distinguen: (a) presión etiquetada en 5 s; (b) recuperación confirmada en 5 s; (c) remate rival en 15 s. Son métricas distintas.

### Evidencia / limitaciones

- Las proporciones ofensivas de corredor representan **la primera acción con coordenadas de la posesión**, no el carril usado para entrar al último tercio ni un dibujo colectivo.
- Las tasas de remate por corredor corresponden a la misma posesión y **no** atribuyen causalidad al corredor.
- Un pase completado entre dos jugadores es evidencia de conexión, **no** de la eficiencia total de los intentos: algunos pases fallidos carecen de destinatario.
- La defensa usa solo posesiones rivales de juego abierto **clasificadas**. Escenarios no clasificables quedan fuera de los denominadores.
- El volumen de presión no es efectividad de la presión ni tracking.
- El marco conceptual organiza preguntas e interpretaciones, nunca sustituye evidencia cuantificada.

### Exportaciones opcionales (cuando `outdir` está configurado)

`diagnostico_conectado.json`, `diagnostico_carriles.csv`, `diagnostico_escenarios_rivales.csv`. No contienen bibliografía conceptual: registran el cálculo y su cobertura como parte de la evidencia del equipo.

### Ejecución local

```bash
cd efos
python3 -m streamlit run visualization/efos_dashboard.py
```

En la pantalla **Selección de Equipo** usa el importador automático para CSV StatsBomb nativos. Selecciona equipo y partidos y abre **Informe Ejecutivo**. Las lecturas solo aparecen cuando hay muestras evaluables. Sin Streamlit instalado en el entorno de pruebas, la ejecución visual debe verificarse localmente.

### Pruebas

`PYTHONPATH=. pytest -q tests/test_tactical_reasoning_v0424.py tests/test_executive_brief_v0421.py tests/test_conceptual_context.py`

Se verificó además la ejecución con los 10 partidos disponibles de Guadalajara del archivo CSV proporcionado. Los resultados pertenecen **solo a esa muestra** y no representan un benchmark de Liga MX.
