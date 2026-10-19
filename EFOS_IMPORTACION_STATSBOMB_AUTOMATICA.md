# EFOS v0.4.22 · Parche de importación automática de StatsBomb

Este parche **conserva la base v0.4.22 (Storytelling Táctico Conectado)** y corrige la selección de ruta que obligaba a relacionar manualmente las columnas de los CSV nativos.

## Flujo

1. Inicia sesión en el dashboard e ingresa en **Selección de Equipo → Cargar CSV de cualquier equipo**.
2. Selecciona uno o varios CSV de StatsBomb con la estructura nativa de `event_type_name`, `team_name`, `id`, `match_id` y `period`, o CSV EFOS normalizados.
3. EFOS reconoce el esquema, presenta archivos/partidos/eventos únicos y muestra la selección del equipo y de los partidos reales (con los rivales derivados de los eventos).
4. Haz clic en **Analizar en EFOS**. La selección se envía al **mismo pipeline completo** usado para los CSV almacenados en el repositorio: Informe Ejecutivo, Modelo de Juego, Ataque, Defensa, Transiciones, Balón Parado y Momentos del Partido. El encabezado cambia a la muestra importada.
5. La relación manual de columnas permanece exclusivamente como alternativa para archivos de otros proveedores o formatos no reconocidos.

Los archivos cargados se preservan sin modificación en `.runtime/uploads/<usuario>/` con hash de contenido; `.runtime` no se incorpora al ZIP ni debe subirse a GitHub. No se modificó la lógica de los motores tácticos ni la narrativa de v0.4.22.

## Qué se conserva y qué no se infiere

- La tabla de eventos se consolida por el identificador original del evento, para que un remate repetido en varias filas cuente **una sola vez**.
- `ingestion/statsbomb_auxiliary.py` conserva en dos tablas auxiliares las posiciones observadas en los **freeze frames de tiros** y las filas de participantes en formación/lineup, vinculadas a `match_id` y `event_id`. En el resultado del pipeline se encuentran en `shot_freeze_frames` y `formation_lineups`. Se limitan a los partidos realmente seleccionados.
- Son **datos auxiliares vinculados**, no métricas nuevas: los motores de métricas y los gráficos no fueron reescritos para consumir las tablas auxiliares.
- **Los freeze frames de tiros NO son StatsBomb 360**, ni autorizan a mostrar una posición simultánea en cualquier momento del partido, seguimiento de jugadores ni animación 360. La función de animación del módulo Transiciones sigue requiriendo JSON StatsBomb 360 real.
- Los eventos sin el mismo nombre que los eventos tradicionales, por ejemplo `Offensive Duel`, `Defensive Duel` y `Loose Ball Duel`, permanecen diferenciados; **no** se traducen a `Duel` sin evidencia ni se cuentan como repeticiones de los eventos ordinarios.
- Las coordenadas del export nativo se mantienen en su escala StatsBomb 120 × 80. No se reescalan ni se invierten por defecto.
- La selección de partidos ocurre antes del cálculo. Así los resultados, denominadores y narrativas se derivan de la misma muestra, no de una selección visual posterior.

## Verificaciones

- Se procesó el archivo de Guadalajara 2026–2027 entregado: 41,274 filas originales → 36,523 eventos únicos → 10 partidos; 4,146 posiciones relacionadas con 271 remates, 605 filas de participantes/formación.
- Pipeline completo para 10 partidos: ESI, Coach Story, 645 posesiones de ataque organizado, 589 posesiones del motor defensivo de juego abierto.
- Pipeline para un único partido seleccionado y exportaciones PDF disponibles.
- 162 pruebas automáticas existentes y nuevas pasadas en el entorno de evaluación; módulos que importan Streamlit se excluyeron por falta de Streamlit en ese entorno.
- **Pendiente en equipo del usuario:** validación visual en navegador con Streamlit instalado; aquí no se garantizan los elementos de interfaz mediante ejecución interactiva.

## Ejecutar (desde `efos/`)

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run visualization/efos_dashboard.py
```
