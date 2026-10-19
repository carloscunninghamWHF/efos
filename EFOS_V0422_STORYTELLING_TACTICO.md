# EFOS v0.4.22 · Narrativa táctica conectada

Base: **v0.4.21 Executive Intelligence**. Los motores (normalización StatsBomb, ESI, CTS, OBV, presión, transiciones, deduplicación y posesiones) no se modificaron.

## 1. Informe Ejecutivo

- Sustituye el gráfico aislado de porcentajes por una **secuencia observada sobre el campo** que permite seguir acciones reales, entradas al área y remates (si existen). Se puede elegir otra secuencia relevante y ver la cronología de eventos.
- La secuencia elegida **no es un patrón promedio ni una ruta habitual demostrada**; los agregados y sus denominadores están en un desplegable distinto.
- La lectura inicial conserva tres señales sustentadas en datos; la distribución del corredor de inicio ya **no es el gráfico protagonista**.

## 2. Ataque Organizado

- Inicio: distingue explícitamente **origen registrado** de transición ofensiva y muestra la distribución de etiquetas de posesión sin inventar categorías.
- Armado táctico: explica las **principales conexiones** y muestra cinco pares de pases completos con el mismo filtro que la red.
- Progresión: escena observada con recorrido de pelota y eventos; no reconstruye carreras sin balón.
- Finalización: remates / entradas al área con descripción de lo que representan los puntos y de la cobertura xG.
- Botón de acceso desde «¿Qué sucede después de recuperar?» a Transiciones, donde se estudia el cambio de posesión.

## 3. Defensa Organizada

- Portada: **«¿Cómo defiende el equipo?»**. Selección independiente de **equipo base** si los datos contienen múltiples equipos, más filtros de **rival** y **partido específico**; aclara que cambiar el equipo base en Defensa no cambia la portada ejecutiva global.
- Los filtros reducen las **posesiones y eventos originales** y esa misma selección se entrega a mapas, porcentajes, redes, informes y jugadas.
- Tres situaciones de juego abierto: reacción tras pérdida, defensa ante contraataque y defensa ante ataque posicional. Cada una presenta el **relato específico generado de su muestra**, actividad defensiva más registrada, número de remates y **cancha amplia propia** con instrucciones de lectura; no se muestran tres diagramas pequeños ni texto genérico.
- La clasificación utiliza el mismo motor v0.4.13 (contraataque etiquetado → reacción tras pérdida operacional → ataque posicional operacional → otro). Reanudaciones a balón parado se analizan en su módulo específico.
- La mayoría de las conexiones por co-intervenciones no demuestran coordinación, estructura fija ni marcaje.

## 4. Transiciones / parche aportado

Del ZIP `efos_v0_4_16_parche_animacion_continua.zip` se recuperó `transition_animation.py` y se integró **sin sobrescribir el dashboard v0.4.21**.

- Bloque opcional «Animación 2D con StatsBomb 360» en Transiciones. Permite subir archivos JSON nativos 360 por partido y elegir evento observado de recuperación o pérdida, además de partido.
- Utiliza eventos originales (máximo 15 s) y fotografías realmente disponibles. Se exige un mínimo de dos fotografías por secuencia; **no se sintetizan datos 360 ausentes**.
- Se añadió un motor sencillo de polígonos Voronoi acotados al campo, exclusivamente para la representación gráfica de la animación.
- Los desplazamientos entre fotografías y los Voronoi interpolados **son aproximaciones visuales, no tracking continuo ni control espacial medido**. No debe interpretarse como trayectoria real del futbolista.
- Animación Plotly interactiva, controles de reproducción y GIF opcional probados con eventos/fotografías sintéticos de validación.

**No se incluyen** los diez indicadores Voronoi O1–O5 y D1–D5 del documento del parche, porque faltan los archivos `intelligence/transition_voronoi_360.py` y `visualization/transition_voronoi_360_maps.py` que implementan sus medidas. Tampoco debe usarse el `efos_dashboard.py` antiguo del parche, pues sobrescribiría los cambios recientes.

## Validación y limitaciones

- `python -m compileall` completado.
- `158` pruebas automatizadas completadas; se excluyeron dos módulos de tests que requieren Streamlit, no instalado en este entorno.
- Pipeline probado contra un CSV de **un partido real**: 3460 eventos procesados, 47 secuencias ofensivas y 48 posesiones rivales incluidas en el motor abierto de defensa; gráficos de ataque y defensa renderizados en Plotly.
- Animación Plotly (14 frames en la prueba controlada) y GIF real generado con Pillow.
- **Sin validación visual interactiva del portal Streamlit** en navegador y sin volver a procesar exhaustivamente los 38 partidos; revisar en macOS antes de presentar a un club.
- Las visualizaciones de Defensa por escenario y las animaciones no cambian los datos del motor; no se infieren alineaciones ni movimientos simultáneos con eventos.
- El PDF ejecutivo mantiene su plantilla narrativa v0.4.21; los gráficos detallados del portal no se exportan automáticamente en ese PDF.

## Ejecución

Desde la carpeta `efos`:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run visualization/efos_dashboard.py
```

**Prueba manual recomendada:** elegir base América, luego Defensa → Rival → Partido; comprobar si cada cancha cambia junto con los denominadores. En Transiciones, cargar un JSON 360 correspondiente a ese partido (si se dispone de licencia y permiso de uso).
