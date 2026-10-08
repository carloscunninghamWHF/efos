# EFOS Coach Story — América

> **Método:** Data -> Metrics -> Interpretation -> Evidence -> Coach Story

> **Equipo focal:** América · **Partidos:** 38 · **Eventos del equipo:** 68382 · **Formato:** EFOS_NORMALIZED
> **Archivos:** 1 · **Selección:** auto_full_coverage · **Perfil:** `EFOS_v0.4.5_PDF_CoachStory`

## Coach Story — en 30 segundos

En la muestra analizada, América se define principalmente por respuesta ante riesgo (94.5/100), mientras organización colectiva (56.5/100) es la dimensión relativamente más variable del perfil. Sin balón registra 42.2 acciones de counterpress por partido y 27.1% de sus Pressure events aparecen en x≥80. Con balón, 45.4% de las secuencias que cumplen el proxy de atracción de presión encuentran una liberación progresiva posterior. Los patrones candidatos con mayor evidencia incluyen Conservación bajo alta restricción, Respuesta inmediata tras pérdida, Uso de banda como restricción. EFOS describe regularidades observadas; no afirma por sí solo que sean instrucciones deliberadas del entrenador.

> **La pregunta clave:** ¿Qué provoca los momentos en que organización colectiva se separa del comportamiento habitual y cómo cambia la respuesta del equipo después?

### Lo que EFOS encontró
**01.** La altura media de las acciones defensivas es x=55.6/120 (Intervención defensiva media-alta). EFOS la interpreta como altura de intervención, no como posición exacta de la línea defensiva.
**02.** Sin balón, el equipo registra 42.2 acciones de counterpress por partido; 27.1% de sus Pressure events aparecen en x≥80 y 18.0% de los pases rivales están etiquetados bajo presión.
**03.** EFOS detecta 1692 pases completados bajo presión antes de x=80 como proxy de atracción ('fishing'). En 45.4% de esos casos la posesión encuentra una liberación progresiva dentro de la ventana secuencial configurada.
**04.** En progresión se observan 37.0 entradas a half-space por partido y 9.3 cadenas A→B→C progresivas por partido como proxy de tercer hombre.
**05.** En último tercio aparecen 20.4 pases por partido hacia el intervalo central-lateral y 16.9 centros por partido que cumplen la geometría del proxy 'Aliup'.

## 1. Identidad general del sistema

El ESI global es 72.01. La dimensión relativamente más alta dentro del perfil es Respuesta ante riesgo (RPS) (94.53) y la relativamente más baja es Organización colectiva (OC) (56.53). Esto describe la forma interna del perfil, no una clasificación absoluta.

**Confianza:** MEDIUM

### Dimensiones ESI

| Dimensión | Valor | Lectura |
|---|---:|---|
| OC | 56.53 | Organización colectiva (OC) = 56.53. Dentro de las cinco dimensiones del propio modelo, se sitúa por debajo de la mediana interna (70.04); representa la cohesión organizacional estimada del sistema a partir de su compactación espacial y señales de control disponibles. |
| HPS | 70.04 | Estabilidad bajo presión (HPS) = 70.04. Dentro de las cinco dimensiones del propio modelo, se sitúa cerca de la mediana interna (70.04); representa cuánto de la funcionalidad del equipo se conserva cuando aumenta la restricción contextual rival. |
| RPS | 94.53 | Respuesta ante riesgo (RPS) = 94.53. Dentro de las cinco dimensiones del propio modelo, se sitúa por encima de la mediana interna (70.04); representa la estabilidad con la que el sistema procesa acciones de riesgo en zonas vulnerables dentro de la definición actual. |
| DS | 83.96 | Estabilidad de decisión (DS) = 83.96. Dentro de las cinco dimensiones del propio modelo, se sitúa por encima de la mediana interna (70.04); representa la estabilidad de ejecución/decisión observada frente a las probabilidades de pase disponibles. |
| DER | 61.87 | Respuesta tras pérdida (DER) = 61.87. Dentro de las cinco dimensiones del propio modelo, se sitúa por debajo de la mediana interna (70.04); representa la rapidez con la que el sistema recupera equilibrio después de pérdidas y cambios de estado. |

> Las comparaciones son relativas dentro del modelo/muestra; no son benchmarks absolutos de liga.

## 2. Identidad según el marcador

| Estado | ESI | OC | HPS | RPS | DS | DER | Eventos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ganando | 71.63 | 55.75 | 69.94 | 94.12 | 82.92 | 62.20 | 16683 |
| Empatando | 72.12 | 56.85 | 69.98 | 94.45 | 84.05 | 62.05 | 36767 |
| Perdiendo | 72.29 | 56.87 | 70.29 | 95.45 | 84.84 | 60.98 | 14932 |

El ESI contextual se mantiene prácticamente igual según el marcador: entre 71.6 (winning) y 72.3 (losing), una diferencia de 0.7 puntos demasiado pequeña para interpretarla.

**Confianza:** MEDIUM

## 3. Comportamiento bajo presión

HPS v2 = 70.04 con un PCI medio de 0.350 sobre las acciones elegibles de HPS. EFOS separa el estímulo (presión/restricción rival) de la respuesta del sistema. Retención=92.2, progresión=54.3, preservación de valor=50.2 y estabilidad de decisión=61.4 en escala 0–100.

El PCI medio sobre todas las acciones contextuales del equipo es 0.326; el 16.4% supera el umbral operativo de presión alta (PCI≥0.60). La cobertura de Lane Closure es 0.0%; con 0% el motor trabaja como EVENT_PROXY y no como tracking/360 completo.

**Confianza:** MEDIUM

| Componente HPS | Valor (0–100) |
|---|---:|
| Retención | 92.15 |
| Progresión | 54.34 |
| Preservación de valor | 50.22 |
| Estabilidad de decisión | 61.35 |

### Presión impuesta al rival

Sobre acciones del rival, el contexto defensivo asociado al equipo registra PCI medio=0.336 y 18.1% de acciones en PCI≥0.60. Los componentes medios son presión directa=0.213, presión cercana=0.354, restricción de banda=0.485 y DefR=0.506. DefR se interpreta como proxy de responsabilidad defensiva, no como intensidad física.

| Componente PCI | Media | Cobertura |
|---|---:|---:|
| Presión directa | 0.213 | 100.0% |
| Presión cercana | 0.354 | 100.0% |
| Confinamiento por banda | 0.485 | 98.9% |
| DefR | 0.506 | 100.0% |
| Restricción de control | 0.270 | 81.8% |
| Cierre de líneas | N/A | 0.0% |

## 4. Estructura y respuesta defensiva

DS = 83.96 y DER = 61.87. EFOS trata organización/decisión y recuperación tras pérdida como dimensiones diferentes. Su distancia describe una asimetría del perfil, no una falla automática.

## 5. Momentos del partido

DTC clasifica 271 ventanas. El estado más frecuente es adaptation (52.8% de las ventanas). La transición condicional más frecuente observada es stability → adaptation (54.5%).

**Confianza:** MEDIUM

| Estado interno | Ventanas | Share |
|---|---:|---:|
| Recuperación / adaptación | 143 | 52.8% |
| Control | 125 | 46.1% |
| Presión creciente | 3 | 1.1% |

## 6. Principios de juego candidatos

| Patrón candidato | Incidencia | Confidence score | Evidencia | Fuente |
|---|---:|---:|---:|---|
| Conservación bajo alta restricción | 95.4% | 97.7/100 | 11217 | EVENT_PROXY |
| Ejecución de traps defensivos | 91.2% | 94.8/100 | 1518 | TRAP_ENGINE |
| Respuesta inmediata tras pérdida | 45.5% | 75.2/100 | 2912 | TRANSITION_ENGINE |
| Uso de banda como restricción | 30.5% | 69.8/100 | 10123 | EVENT_PROXY |
| Presión en bloque alto | 27.0% | 68.1/100 | 5609 | EVENT |
| Presión directa sobre acciones rivales | 21.3% | 67.2/100 | 55971 | EVENT_PROXY |
| Progresión directa desde inicio a último tercio | 4.0% | 60.6/100 | 5126 | EVENT |

> Un patrón candidato describe regularidad observada; no demuestra por sí mismo una instrucción deliberada del entrenador.

## 7. Marco teórico-táctico derivado de video

Esta capa traduce conceptos del marco táctico a reglas auditables sobre eventos StatsBomb. Cuando el dato no observa directamente el concepto, EFOS lo marca como **proxy**.

### 7.1 Perfil defensivo

| Señal | Resultado | Confianza | Fuente |
|---|---|---|---|
| Altura de intervención defensiva | 55.59 | HIGH | EVENT |
| Counterpress | n=1603 · 42.18/partido · 19.8% | HIGH | EVENT |
| Offsides del rival (proxy) | n=40 · 1.05/partido · 0.3% | MEDIUM | EVENT_PROXY |
| Pases rivales bajo presión | n=2798 · 73.63/partido · 18.0% | HIGH | EVENT |
| Pressure events altos (x≥80) | n=1521 · 40.03/partido · 27.1% | HIGH | EVENT |

### 7.2 Construcción y progresión

| Señal | Resultado | Confianza | Fuente |
|---|---|---|---|
| Directicidad media | 0.51 | HIGH | EVENT |
| Atracción de presión / Fishing | n=1692 · 44.53/partido · 13.4% | MEDIUM | EVENT_PROXY |
| Liberación tras atraer presión | n=769 · 20.24/partido · 45.4% | MEDIUM | SEQUENCE_PROXY |
| Entradas a half-space | n=1406 · 37.00/partido · 8.3% | MEDIUM | EVENT_PROXY |
| Tercer hombre (proxy A→B→C) | n=354 · 9.32/partido · 2.1% | MEDIUM | SEQUENCE_PROXY |

### 7.3 Microconceptos ofensivos

| Señal | Resultado | Confianza | Fuente |
|---|---|---|---|
| Centro a zona peligrosa / Aliup proxy | n=641 · 16.87/partido · 31.7% | LOW | EVENT_PROXY |
| Ataque intervalo central-lateral | n=776 · 20.42/partido · 4.6% | MEDIUM | EVENT_PROXY |

### 7.4 Propósito y valor (PMDS / xG / OBV)

| Variable | Total | Por partido | Lectura |
|---|---:|---:|---|
| xG | 52.68 | 1.386 | Calidad esperada de los remates |
| OBV neto | 57.487 | 1.513 | Cambio de valor esperado asociado a acciones elegibles |

### 7.5 Hipótesis de foco semanal (estructura de microciclo del marco aportado)

> No es una prescripción de carga ni un plan físico. Es un puente entre hallazgos de EFOS y temas técnico-tácticos a discutir con el staff.

| Día | Tema | Foco sugerido por la evidencia | Requiere scouting rival |
|---|---|---|---|
| Lunes | Corrección / salida bajo presión | Revisar secuencias de atracción de presión y salida posterior; priorizar apoyos y tercer hombre. | No |
| Martes | Principios defensivos | Coordinar distancias de presión, cobertura y reorganización del bloque tras pérdida. | No |
| Miércoles | Plan contra rival | Definir altura y gatillos de presión frente a la salida específica del próximo rival. | Sí |
| Jueves | Plan ofensivo contra rival | Consolidar ataques de intervalo y variantes de centro a zona peligrosa; ajustar al comportamiento defensivo del rival. | Sí |
| Viernes | Balón parado y escenarios | Revisar balón parado y escenarios de partido usando xG/OBV como evidencia de valor, sin prescribir carga física desde EFOS. | No |

> **Guardrail:** Cada concepto se reporta como observación o proxy según la información realmente disponible. Un proxy no prueba por sí solo intención del entrenador. 

## 8. Defensive Traps

El Trap Engine detecta 1518 secuencias candidatas y clasifica 1384 como exitosas con la definición operativa actual, produciendo DTE=91.17% y Trap Rate=21.61 por cada 100 posesiones rivales observadas. Estos valores describen la salida del detector, no un benchmark validado de eficiencia defensiva.

**Confianza:** EXPERIMENTAL

**Outcomes más frecuentes en traps clasificados como exitosos:**

- Negative OBV: 534
- Backward pass: 375
- Incomplete: 268
- Forced long pass: 92
- Dispossessed: 54
- Out: 31
- Miscontrol: 19
- Unknown: 6

## 9. Coach Tactical Signature

CTS es un **vector descriptivo**, no una calificación global del entrenador.

| Componente CTS | Valor | Qué representa |
|---|---:|---|
| construction | 25.06 | densidad heurística de pases de construcción respecto al volumen total de eventos |
| progression | 7.42 | densidad heurística de progresiones profundas desde zona inicial hacia X>80 |
| attack | 94.63 | densidad heurística de eventos del equipo en último tercio |
| defense | 68.35 | densidad heurística de eventos Pressure ejecutados por el equipo |
| transition | 45.54 | proporción de pérdidas con respuesta registrada dentro de 5 segundos |
| adaptation | N/A | componente reservado para adaptación; en Sprint 4 no está estimado como dimensión independiente |
| trap_efficiency | 91.17 | DTE del Trap Engine; experimental hasta calibración |
| pressure_resistance | 70.04 | HPS v2 utilizado como componente de resistencia contextual |
| mean_pressure_context | 32.56 | PCI medio reescalado a 0–100 |
| confidence | 100.00 | cobertura muestral interna del CTS, no certeza causal del análisis |

**Confianza:** MEDIUM

## 10. Participación individual en último tercio (LAP)

LAP describe qué proporción de las acciones de cada jugador en último tercio pertenece a tipos definidos como críticos. En la tabla descriptiva, Igor Lichnovsky Osorio registra 76.2% (32/42) dentro de esta definición.

**Confianza:** MEDIUM

| Jugador | LAP | Acciones críticas | Acciones último tercio | xG | xA |
|---|---:|---:|---:|---:|---:|
| Igor Lichnovsky Osorio | 76.2% | 32 | 42 | 0.746 | 0.000 |
| Ralph Orquin | 67.5% | 54 | 80 | 0.031 | 0.000 |
| Raphael Cavalcante Veiga | 67.0% | 383 | 572 | 1.905 | 0.000 |
| Cristian Alexis Borja González | 66.5% | 808 | 1216 | 0.499 | 0.000 |
| Miguel Ángel Vázquez García | 65.6% | 128 | 195 | 0.936 | 0.000 |
| Alexis Hazael Gutiérrez Torres | 65.6% | 454 | 692 | 1.107 | 0.000 |
| Aaron Mejía Montoya | 65.3% | 113 | 173 | 0.000 | 0.000 |
| Vinícius Moreira de Lima | 64.1% | 134 | 209 | 0.757 | 0.000 |

> LAP no es un ranking de calidad; mide participación proporcional dentro de la definición de acciones críticas.

## 11. Evolución dentro de la muestra

La muestra se divide en tres bloques usando **orden de aparición del dataset**.

| Fase | Partidos | ESI | OC | HPS | RPS | DS | DER |
|---|---:|---:|---:|---:|---:|---:|---:|
| early | 13 | 71.33 | 55.46 | 69.43 | 94.67 | 81.08 | 62.42 |
| middle | 13 | 72.01 | 56.88 | 69.70 | 94.00 | 83.21 | 62.85 |
| late | 12 | 71.56 | 59.05 | 69.89 | 92.38 | 82.27 | 60.00 |

Al dividir la muestra en tres bloques por orden de aparición en el dataset, el mayor cambio entre el primer y último bloque aparece en OC: 55.46 → 59.05 (Δ=+3.59); por tanto aumenta dentro de esta partición descriptiva.

**Confianza:** MEDIUM

## 12. Resumen estadístico de soporte

| Variable | Valor |
|---|---:|
| Eventos del equipo | 68382 |
| Pases de construcción | 4284 |
| Progresiones profundas | 203 |
| Eventos en último tercio | 19412 |
| Pressures | 5609 |
| X media de Pressure | 58.9158 |
| Tiros | 563 |
| Goles | 59 |
| Under-pressure rate | 0.1880 |
| Respuesta ≤5s tras pérdida | 45.54% |

## 13. ¿Qué sistema parece estar construyendo?

En la muestra analizada, América se define principalmente por respuesta ante riesgo (94.5/100), mientras organización colectiva (56.5/100) es la dimensión relativamente más variable del perfil. Sin balón registra 42.2 acciones de counterpress por partido y 27.1% de sus Pressure events aparecen en x≥80. Con balón, 45.4% de las secuencias que cumplen el proxy de atracción de presión encuentran una liberación progresiva posterior. Los patrones candidatos con mayor evidencia incluyen Conservación bajo alta restricción, Respuesta inmediata tras pérdida, Uso de banda como restricción. EFOS describe regularidades observadas; no afirma por sí solo que sean instrucciones deliberadas del entrenador.

## 14. Límites metodológicos

- ESI y sus dimensiones aún no están calibrados como benchmark universal de liga.
- PCI basado sólo en eventos es un proxy: no equivale a tracking continuo ni a Time-to-Intercept real.
- Trap Engine y DTE permanecen experimentales hasta calibrar umbrales/outcomes contra video o etiquetado humano.
- DTC depende de umbrales configurables y debe validarse antes de tratar sus estados como categorías universales.
- LAP mide participación en acciones críticas definidas por el modelo, no calidad global del jugador.
- Los patrones observados no demuestran por sí solos intención o instrucción del entrenador.
- Fishing, tercer hombre, Aliup, intervalos y trampa de fuera de juego se reportan como proxies cuando el event data no observa directamente el movimiento/estructura requerido.
- La planificación semanal generada es una hipótesis de foco técnico-táctico; EFOS no prescribe carga física ni sustituye el scouting específico del próximo rival.
- Cuando no hay fecha de partido, la evolución usa orden de aparición del dataset, no cronología calendario.

## 15. Registro de evidencia

Este reporte contiene **29 claims auditables** en `evidence.json`. Cada claim incluye evidencia, fuente, tamaño de muestra, confianza y limitación.
