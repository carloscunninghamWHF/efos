# Vídeo del partido · clip + animación 2D (v0.4.17)

En Transiciones → «Jugada a jugada» → pestaña **Clip + animación 2D**. Funciona como una lista de clips: eliges un
momento (o avanzas con ◀ Anterior / Siguiente ▶) y se reproduce el clip real; al terminar arranca sola la animación 2D
del mismo tramo con su Voronoi. Botones para ver solo el clip o solo la animación.

## Vincular el vídeo de un partido (una vez)
1. Copia el vídeo en `data/video/` (mp4, mov, mkv, m4v, webm o avi). También vale una ruta absoluta o un enlace
   DIRECTO a un archivo .mp4. YouTube, Wyscout o Hudl no dan archivo directo: hay que descargar el vídeo (con permiso).
2. En el desplegable «Vídeo del partido» elige el archivo e indica en qué minuto del vídeo arranca cada parte
   (pitido del saque inicial), como mm:ss o h:mm:ss. «Comprobar saques» muestra ese fotograma para verificarlo.
3. «Guardar». La configuración queda en `data/video/videos.json`; todos los momentos del partido quedan sincronizados.

## Cómo se sincroniza
- StatsBomb reinicia el `timestamp` en 00:00 al empezar cada parte: tiempo en el vídeo = inicio de la parte + timestamp.
- Clip: 3 s antes de la recuperación/pérdida hasta 2 s después del último evento de la secuencia. Precisión ≈ 1 s.
- Los clips recortados se guardan en `data/video/clips/` para no recortarlos dos veces.

## Descargas
- **Clip** del momento (MP4 H.264, 720p).
- **MP4 clip + animación**: un único vídeo con el clip y, a continuación, la animación 2D (≈ 30–40 s en prepararse).

## Requisitos y límites
- ffmpeg: del sistema o `pip install imageio-ffmpeg` (incluido en requirements.txt).
- El vídeo de televisión tiene repeticiones y planos cortos: a veces el clip no enseña toda la jugada; la animación sí.
  Con vídeo táctico (plano abierto) el resultado es mejor.
- `data/video/` está en .gitignore: los vídeos pesan varios GB y tienen derechos; no se suben al repositorio.
