# EFOS v0.4.5 - Visual Coach Story PDF

Cada corrida de `run_sprint4.py` con `--out` genera automáticamente `coach_story.pdf`.

El PDF está diseñado como entregable ejecutivo y contiene:

1. Portada + lectura de 30 segundos.
2. Identidad del sistema y cinco dimensiones EFOS.
3. Perfil sin balón: altura de intervención, counterpress, presión alta, presión sobre pases rivales y offside proxy.
4. Perfil con balón: atracción de presión, liberación, half-spaces, tercer hombre, intervalos y centros a zona peligrosa.
5. Momentos del partido y evolución de la muestra.
6. Coach Tactical Signature y principios candidatos.
7. Evidencia, confianza, conclusión y límites metodológicos.

En Streamlit, la pestaña **Coach Story** muestra una vista previa del PDF y un botón de descarga. El archivo `.md` se conserva como anexo de auditoría.

Dependencia adicional: `reportlab>=4.0`.
