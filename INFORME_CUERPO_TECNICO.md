# EFOS v0.4.6 — Informe para cuerpo técnico

Objetivo: que una persona que sabe de fútbol, pero no de datos, entienda EFOS sin aprender sus siglas.

## Qué se añadió

1. **Informe organizado por momentos del juego** (`coach_story/football_report.py`): Ficha · El entrenador ·
   Ataque organizado · Transición defensiva · Defensa organizada · Transición ofensiva · Balón parado ·
   Cómo reacciona · Jugadores · Conclusiones (fortalezas, debilidades, cómo jugarle, perfil que lo continuaría) · Vídeo.
2. **Lenguaje de vestuario**: glosario único (`GLOSSARY`) que traduce ESI, OC, HPS, RPS, DS, DER, DTC, PCI, LAP, CTS,
   PPDA y xG. Se usa en el informe, el PDF y el portal; las siglas solo aparecen en el glosario y en «Método».
3. **Unidades de fútbol y comparación con rivales**: metros, por partido, % y goles esperados; cada dato va
   acompañado de lo que hicieron sus rivales en esos mismos partidos.
4. **Vídeo**: `clips_sugeridos.csv` con las jugadas que mejor ilustran cada rasgo (rival, parte, minuto,
   protagonista y qué observar), a favor y en contra.
5. **Visuales de campo**: once medio (posición media con balón de los 11 más utilizados), dibujos, reacción
   al marcador y minutos de los cambios.
6. **Afirmaciones matizadas**: el ESI por marcador ya no habla de «sensibilidad» cuando la diferencia es < 2
   puntos; los índices compuestos (ESI y dimensiones) tienen confianza máxima MEDIUM porque sus pesos no están
   calibrados; las trampas de presión no aparecen en las conclusiones (siguen como experimentales).
7. **Contexto**: balance G-E-P, puntos por partido, goles y goles esperados. Local/visitante y torneo
   (Apertura, Clausura, Liguilla) no vienen en los datos y se declaran como pendientes.
8. **Cierre accionable**: fortalezas, debilidades (o «lo menos destacado» si no hay debilidades reales),
   cómo jugarle y qué perfil de entrenador lo continuaría.

Incluye el **perfil del entrenador** (`coach_story/coach_profile.py`) y el **encaje con perfiles de entrenador**
(`coach_story/coach_fit.py`, `config/coach_archetypes.yaml`) de la v0.4.3.

## Salidas nuevas de `run_sprint4.py`

`informe_cuerpo_tecnico.pdf` (entregable principal) · `informe_cuerpo_tecnico.md` · `perfil_entrenador.md` ·
`coach_profile.json` · `partidos.csv` · `clips_sugeridos.csv` · `posiciones_medias.csv` · `style_profile.csv` ·
`coach_fit.csv`. El `coach_story.pdf` técnico se conserva como anexo.

## Portal

Navegación: Informe · El entrenador · Con balón · Sin balón · Transiciones · Balón parado · Jugadores · Vídeo ·
Momentos del partido · Análisis técnico (Coach Story EFOS, Regularidad del juego, Presión) · Evidencia · Método.
