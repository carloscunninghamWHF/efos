# EFOS v0.4.10 — Premium Set Piece Story & Spatial Illustration

## Objetivo
Mantener EFOS v0.4.9 y su evidencia P0 → P1 → P2, simplificando la pestaña **Balón Parado**: una lectura narrativa en primer lugar, destinos por banda en un mapa 2D, comparación entre repetición y peligro, secuencias recurrentes auditables, vista 3D **opcional** y evidencia jugada por jugada plegable.

## Qué cambió

- `intelligence/set_piece_patterns.py`
  - `premium_story_profile()` produce el título, la explicación, distribución por banda, patrón frecuente, patrón con mayor xG cubierto y una secuencia de jugadores **realmente repetida** (sin mezclar las modas de cada columna).
  - Se conserva `pass_height_name` cuando esté presente en el dataset, sin inventar etiquetas faltantes.
- `visualization/efos_dashboard.py`
  - Jerarquía de lectura: hero narrativo → 2 hallazgos secundarios como máximo → dos mapas 2D por banda → comparación frecuencia/peligro → secuencia cuando hay evidencia → 3D desplegable → evidencia.
  - Misma identidad Editorial Glass UX y colores EFOS; no se añade una nueva pestaña principal.
- `visualization/set_piece_story_3d.py`
  - Plano de cancha interactivo Plotly; muestra como máximo 3, 5 u 8 envíos reales.
  - Selección de patrón más repetido, con mayor xG o por banda; excluye eventos sin coordenadas.
  - Relieve gráfico meramente simbólico. La información de altura de StatsBomb es **categórica**, no ofrece altura real, recorrido ni tiempo de vuelo. Sin etiqueta, el arco es un dibujo genérico explícito.
  - Se activa solo si el entrenador lo solicita; se habilita para córners y tiros libres, no para saques laterales.
- `tests/test_set_piece_premium.py`: 5 pruebas adicionales de narrativas auditables, cobertura, muestra, filtros y 3D.

## Reglas para no romper el storytelling

1. **Historia antes que métricas**: el mensaje inicial responde cuál es el patrón más repetido en la selección, siempre con número de partidos y ejecuciones.
2. **Mapa 2D prioritario**: dos bandas, idéntica metodología, fuente StatsBomb.
3. **No confundir frecuencia y productividad**: comparar xG por ejecución solo con cobertura suficiente, sin convertirlo en probabilidad de marcar.
4. **Secuencia P1 honesta**: es primer evento registrado, no contacto real. La cadena de nombres solo se muestra si todos los pasos coinciden en ejecuciones observadas repetidas.
5. **3D sin falsas mediciones**: en ningún momento se habla de trayectoria física medida ni altura real del balón.
6. **Auditoría accesible**: los CSV y la tabla de evidencia siguen disponibles y el pipeline analítico anterior no ha sido sustituido.

## Ejecutar en Mac / Visual Studio Code

Abre la carpeta `efos/`:

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q tests
python3 -m streamlit run visualization/efos_dashboard.py
```

En la plataforma, entra a **Balón Parado**. Elige tipo de jugada, perspectiva y partido(s); observa primero el análisis 2D. Para activar la visualización ilustrativa, despliega **Explorar patrón en 3D** y marca **Mostrar vista espacial 3D**. Los datos son los mismos que el análisis, no una simulación independiente.

## Validación

- **95/95 pruebas automatizadas aprobadas**, incluyendo las cinco de este sprint.
- El motor de Set Piece Story procesó `data/processed/sprint3_real/events_normalized.csv`: **124,353 eventos**, **38 partidos**, **1,038 ejecuciones** en los seis cruces de tipo/perspectiva.
- Se generaron mapas 2D y la escena Plotly 3D sobre córners reales del dataset.
- Una nueva ejecución integral de `run_sprint4.py` excedió el límite de tiempo en este entorno y **no se acredita como validación completa v0.4.10**.
- Streamlit no estaba instalado en este entorno de pruebas: falta abrir visualmente la interfaz en navegador local y comprobar login, filtros y navegación.

## Alcance científico

Los cortes de zona son parámetros exploratorios. StatsBomb Event no permite inferir movimientos sin balón, marcaje, orientación física, primer contacto, altura real ni curvas de vuelo. La atribución de resultados utiliza la ventana temporal y posesión declarada en el motor vigente de EFOS. La vista 3D solamente espacializa P0, sin agregar evidencia nueva.
