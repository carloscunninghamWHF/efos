# EFOS v0.4.21 — Executive Intelligence

## Qué aporta (comparación con v0.4.10 y v0.4.20)

**v0.4.10** tenía una lectura de 30 segundos y tres observaciones útiles, pero el bloque «cómo jugarle» convertía proxies y comparaciones en decisiones tácticas demasiado concluyentes. **v0.4.20** mejoró el control de evidencia, aunque desplazó la visualización hacia abajo y presentó tres fichas metodológicas largas.

La **v0.4.21** conserva v0.4.20 y establece este orden en el Informe Ejecutivo:

1. **La lectura del equipo:** un relato corto generado de la muestra seleccionada; separa eventos reales de hipótesis.
2. **Tres señales para el cuerpo técnico:** origen del ataque, posesiones rivales clasificadas con remate y acción tras pérdida en los siguientes 5 segundos. Las tres muestras **no** se suman como si fueran particiones.
3. **Gráfico principal de campo:** distribución exacta de corredores de inicio de secuencias válidas. No dibuja trayectorias ficticias ni posicionamientos simultáneos.
4. **Siguiente pregunta y comprobación:** examen de las secuencias en su módulo.
5. **Exploración opcional:** límites de inferencia y muestra, red de pases compacta en orientación horizontal, comparaciones históricas con advertencia.
6. **Exportación:** PDF ejecutivo de una página con el mismo generador narrativo; el PDF completo permanece explícitamente etiquetado como legado.

El módulo **Modelo de Juego y DT** utiliza la misma lectura breve, sin repetir tres fichas y sin modificar su CTS, radar o análisis por marcador.

## Código modificado / añadido

- `coach_story/executive_brief.py` — capa narrativa dinámica que reutiliza las salidas canónicas, independiente de los módulos y sus fórmulas.
- `coach_story/executive_pdf.py` — reemplaza únicamente el diseño de exportación ejecutiva de una página para concordar con la nueva portada.
- `visualization/efos_dashboard.py` — nueva página ejecutiva, estilos CSS editoriales, accesos por módulo y resumen de Modelo de Juego.
- `visualization/efos_smart_attack_graphs.py` — nuevo gráfico de bandas por corredor real; red horizontal opcional, sin cambiar la interfaz por defecto del módulo Ataque.
- `tests/test_executive_brief_v0421.py` — tests de cobertura, porcentajes, causalidad, figura y PDF.

## Integridad de datos

- No se altera el pipeline de carga/limpieza ni fórmulas ESI, CTS, HPS, RPS, DER, DS, OC o OBV.
- El corredor se calcula sobre el **primer evento con coordenadas** en la tabla canónica de ataque organizado, no sobre posiciones de jugadores en un instante.
- La frecuencia de remate defensivo utiliza solo las posesiones etiquetadas dentro de `STATES` de juego abierto; no representa todas las posesiones del adversario.
- Respuesta tras pérdida significa acción etiquetada como presión, recuperación o intercepción dentro de cinco segundos, **no** recuperación exitosa.
- Cada tarjeta muestra el tamaño de su denominador y declara cuando la muestra es limitada.
- Los filtros del Informe Ejecutivo corresponden a la muestra ya procesada por el motor; no se promete recalcular todo el análisis al cambiar un filtro dentro de otro módulo.

## Validación realizada

- **152 tests OK** ejecutados con `python3 -m pytest -q --ignore=tests/test_defense_story_csv.py --ignore=tests/test_defensive_connected_story.py`.
- Dos tests que requieren importar `streamlit` no se ejecutaron en el entorno de validación, que no cuenta con Streamlit. **No se realizó validación visual en navegador.**
- Prueba de integración con **un partido real** de StatsBomb del conjunto incluido: carga, análisis de América, tres señales, gráfico de orígenes y PDF ejecutivo de una página completados. El conjunto completo de 38 partidos no se volvió a ejecutar durante esta revisión.
- PDF ejecutivo de muestra renderizado e inspeccionado (A4, una página).

## Cómo arrancar en macOS

En VS Code / terminal dentro de la carpeta `efos`:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run visualization/efos_dashboard.py
```

Seleccionar el equipo desde **Selección de Equipo** y abrir **★ Informe Ejecutivo**.

## Pendientes honestos

- PDF completo de cuerpo técnico: aún corresponde al informe anterior; sustituirlo requiere rediseñar `coach_story/football_pdf.py` y sus modelos para una narrativa coherente.
- La importación genérica desde el workbench sigue con cobertura distinta al pipeline ejecutivo del repositorio.
- Filtros universales de partido/rival/estado sincronizados entre todos los módulos: pendiente.
- Validación visual de Streamlit en macOS: pendiente; se probó sintaxis, motor, gráficos y PDF, no la interfaz corriendo en navegador.
- Antes de publicar en GitHub: revisar licencias y confidencialidad de los CSV de `data/raw`, así como los hashes de usuarios presentes en `auth/users.txt`.
