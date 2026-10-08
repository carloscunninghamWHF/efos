# EFOS v0.4.4 — Tactical Framework for Coach Story

Esta capa incorpora al Coach Story los conceptos tácticos aportados en la síntesis de videos, pero distingue entre **observación directa** y **proxy táctico**.

## Regla metodológica

`Evento -> Regla -> Evidencia -> Proxy/Observación -> Narrativa`

EFOS nunca convierte automáticamente un proxy en intención del entrenador.

## Limpieza

Antes del cálculo, la capa vuelve a garantizar una fila por evento:

1. `event_id` si existe.
2. `id` si existe.
3. `match_id + index` como fallback.
4. fila completa como último fallback.

El loader `statsbomb_wide_csv.py` ya elimina duplicaciones del export ancho antes de entrar al motor, por lo que esta segunda desduplicación funciona como guardrail.

## I. Perfil defensivo

### Altura de intervención defensiva
Promedio X de `Pressure`, `Ball Recovery`, `Interception`, `Clearance` y `Foul Committed`.

**Importante:** no se llama "altura de la línea defensiva" porque event data no contiene la posición continua de la línea. Es una señal de dónde ocurren las intervenciones.

### Counterpress
Cuenta acciones con `counterpress == True` y las normaliza por partido y por acciones defensivas elegibles.

### Offside rival
Cuenta `Pass Offside` del rival. Se reporta como **proxy compatible con coordinación de profundidad**, no como prueba de una trampa deliberada.

### Presión al pasador
Share de pases rivales con `under_pressure == True`.

### Presión alta
Share de `Pressure` events del equipo con `location_x >= 80`.

## II. Construcción y progresión

### Fishing / atracción de presión
Pase completado bajo presión antes de `x=80`.

La métrica complementaria `pressure_release_success` evalúa si, dentro de los siguientes eventos de la misma posesión, el equipo consigue progresar territorialmente. Esto reduce el riesgo de llamar "fishing" a un pase bajo presión que no libera al equipo.

### Half-spaces
Pases completados a dos zonas configurables:

- X entre 70 y 95.
- Y entre 18–30 o 50–62.

### Tercer hombre — proxy A→B→C
Se exige:

- dos pases completados consecutivos dentro de la misma posesión;
- tres jugadores distintos;
- el receptor del primer pase es el pasador del segundo;
- secuencia rápida (`<= 4s`);
- progresión total >= 15 unidades X;
- segundo pase con ganancia >= 8 unidades X;
- presión involucrada en al menos uno de los dos pases.

No observa movimientos sin balón, por lo que sigue etiquetado `SEQUENCE_PROXY`.

## III. Microconceptos ofensivos

### Aliup — proxy geométrico
Identifica centros cuyo destino entra en la zona configurada de peligro. EFOS **no** afirma que exista rosca, pierna cambiada, segundo palo real o un receptor específico, porque event data no contiene toda esa información.

### Intervalo central-lateral
Pases completados desde `x>=60` hacia `x>=88` terminando en las zonas de half-space configuradas.

## IV. Propósito y valor

- xG total, por partido y por tiro.
- OBV neto total, por partido y por 100 eventos del equipo.

Estas variables explican valor esperado; no prueban el mecanismo táctico que produjo la acción.

## V. Hipótesis de foco semanal

EFOS genera un puente entre hallazgos y temas de discusión del staff:

- Lunes: corrección/consolidación de salida bajo presión.
- Martes: principios defensivos y reorganización.
- Miércoles: plan de presión contra el próximo rival (**requiere scouting rival**).
- Jueves: plan ofensivo contra el próximo rival (**requiere scouting rival**).
- Viernes: balón parado y escenarios con xG/OBV como evidencia.

No es una prescripción de carga física ni reemplaza la planificación del cuerpo técnico.

## Outputs nuevos

`run_sprint4.py` genera adicionalmente:

- `tactical_framework.json`
- nueva sección en `coach_story.json`
- nueva sección completa en `coach_story.md`
- claims tácticos dentro de `evidence.json`

## UI

- **Resumen:** muestra el marco táctico detectado en lenguaje de entrenador.
- **Con balón:** Fishing, liberación, half-spaces, tercer hombre, intervalos y centros a zona peligrosa.
- **Sin balón:** altura de intervención, counterpress, presión al pasador y offside rival.
- **Evidencia:** cada claim táctico conserva fuente, N, confianza y limitación.
