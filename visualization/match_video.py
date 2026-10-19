"""EFOS — Vídeo del partido sincronizado con los eventos (clips estilo Wyscout + animación 2D).

Sincronización
  * Los eventos StatsBomb llevan `timestamp` = reloj DENTRO de cada parte (se reinicia en 00:00 al empezar la 2.ª).
  * El vídeo tiene su propio reloj (previa, descanso…). Basta con indicar, una vez por partido, en qué segundo del
    vídeo empieza cada parte:  tiempo_vídeo = inicio_parte[periodo] + timestamp_del_evento.
  * Precisión esperable ±1 s (la del marcado manual del saque inicial).

Fuentes de vídeo
  * Archivo local (mp4, mov, mkv, m4v, webm, avi) en `data/video/` o una ruta absoluta.
  * Enlace DIRECTO a un archivo de vídeo (https://…/partido.mp4). YouTube/Wyscout/Hudl no dan un archivo directo:
    hay que descargar el vídeo (con permiso de quien tiene los derechos) y dejarlo en `data/video/`.

Salidas
  * Clip MP4 del momento (H.264, 720p) recortado con ffmpeg (del sistema o de `imageio-ffmpeg`).
  * Reproductor HTML para el portal: clip real → animación 2D del mismo tramo, en secuencia y sin cortes.
  * MP4 único «clip + animación» para presentaciones.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "data" / "video"
CONFIG = VIDEO_DIR / "videos.json"
CLIPS = VIDEO_DIR / "clips"
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".avi"}
PRE_ROLL = 3.0          # s de vídeo antes de la recuperación / pérdida
POST_ROLL = 2.0         # s después del último evento de la secuencia
PERIOD_START_MIN = {1: 0, 2: 45, 3: 90, 4: 105, 5: 120}


# ============================================================== ffmpeg
def ffmpeg_exe() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _run(args: list[str], timeout: int = 300) -> None:
    exe = ffmpeg_exe()
    if exe is None:
        raise RuntimeError("No se encontró ffmpeg. Instálalo con:  pip install imageio-ffmpeg")
    p = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg falló: {p.stderr.strip()[-400:]}")


def has_audio(src: str) -> bool:
    exe = ffmpeg_exe()
    if exe is None:
        return False
    p = subprocess.run([exe, "-hide_banner", "-i", str(src)], capture_output=True, text=True, timeout=60)
    return "Audio:" in p.stderr


def duration(src: str) -> float | None:
    exe = ffmpeg_exe()
    if exe is None:
        return None
    p = subprocess.run([exe, "-hide_banner", "-i", str(src)], capture_output=True, text=True, timeout=60)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


# ============================================================== configuración por partido
def list_videos(folder: Path = VIDEO_DIR) -> list[str]:
    if not folder.exists():
        return []
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.suffix.lower() in VIDEO_EXT and CLIPS not in p.parents)


def load_config(path: Path = CONFIG) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_match(match_id, source: str, start_1: float, start_2: float, path: Path = CONFIG) -> dict:
    cfg = load_config(path)
    cfg[str(match_id)] = {"fuente": source, "inicio_1": float(start_1), "inicio_2": float(start_2)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def resolve_source(source: str, folder: Path = VIDEO_DIR) -> str:
    """Ruta absoluta del vídeo (relativa a data/video/) o el enlace directo tal cual."""
    if re.match(r"^https?://", source or ""):
        return source
    p = Path(source).expanduser()
    return str(p if p.is_absolute() else folder / p)


def parse_clock(text: str) -> float | None:
    """'mm:ss', 'hh:mm:ss' o segundos → segundos."""
    t = str(text or "").strip().replace(",", ".")
    if not t:
        return None
    try:
        parts = [float(x) for x in t.split(":")]
    except ValueError:
        return None
    s = 0.0
    for x in parts:
        s = s * 60 + x
    return s


def fmt_clock(sec: float | None) -> str:
    if sec is None or pd.isna(sec):
        return ""
    sec = max(0.0, float(sec)); h, r = divmod(int(sec), 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ============================================================== sincronización
def period_seconds(ev_row) -> float:
    """Segundos desde el inicio de la parte (usa `timestamp` con milisegundos; si falta, minuto y segundo)."""
    ts = ev_row.get("timestamp") if hasattr(ev_row, "get") else None
    if isinstance(ts, str) and ":" in ts:
        v = parse_clock(ts)
        if v is not None:
            return v
    per = int(ev_row.get("period", 1))
    return float(ev_row["minute"]) * 60 + float(ev_row["second"]) - PERIOD_START_MIN.get(per, 0) * 60


def video_time(ev_row, match_cfg: dict) -> float | None:
    per = int(ev_row.get("period", 1))
    start = match_cfg.get(f"inicio_{per}")
    if start is None:
        return None
    return float(start) + period_seconds(ev_row)


def clip_window(ev_row, match_cfg: dict, seq_seconds: float) -> tuple[float, float] | None:
    t = video_time(ev_row, match_cfg)
    if t is None:
        return None
    return max(0.0, t - PRE_ROLL), max(0.0, t - PRE_ROLL) + PRE_ROLL + max(seq_seconds, 4.0) + POST_ROLL


# ============================================================== clips
def cut_clip(source: str, start: float, length: float, out: Path | None = None, height: int = 720) -> bytes:
    """Recorta [start, start+length] a MP4 H.264 (fotograma exacto, apto para navegador)."""
    out = Path(out) if out else Path(tempfile.mkstemp(suffix=".mp4")[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["-ss", f"{start:.2f}", "-i", str(source), "-t", f"{length:.2f}", "-vf", f"scale=-2:'min({height},ih)'",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
          "-movflags", "+faststart", str(out)])
    return out.read_bytes()


def frame_at(source: str, t: float, height: int = 360) -> bytes:
    """Fotograma JPG en el segundo t (para comprobar el saque inicial)."""
    with tempfile.TemporaryDirectory() as d:
        o = Path(d) / "f.jpg"
        _run(["-ss", f"{max(t, 0):.2f}", "-i", str(source), "-frames:v", "1", "-vf", f"scale=-2:{height}", str(o)], timeout=60)
        return o.read_bytes()


def moment_clip(source: str, match_id, event_id: str, window: tuple[float, float], cache: Path = CLIPS) -> bytes:
    a, b = window
    out = cache / f"{match_id}_{str(event_id)[:12]}_{int(a * 10)}_{int(b * 10)}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out.read_bytes()
    return cut_clip(source, a, b - a, out)


def sequence_mp4(clip: bytes, anim: bytes, size: tuple[int, int] = (1280, 720)) -> bytes:
    """Un único MP4: clip real seguido de la animación 2D (misma resolución, audio del clip y silencio después)."""
    w, h = size
    with tempfile.TemporaryDirectory() as d:
        c, a, o = Path(d) / "c.mp4", Path(d) / "a.mp4", Path(d) / "o.mp4"
        c.write_bytes(clip); a.write_bytes(anim)
        fit = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,fps=25,format=yuv420p"
        if has_audio(str(c)):
            fc = (f"[0:v]{fit}[v0];[1:v]{fit}[v1];[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
                  f"[2:a]aformat=channel_layouts=stereo[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")
            anim_len = duration(str(a)) or 10
            _run(["-i", str(c), "-i", str(a), "-f", "lavfi", "-t", f"{anim_len:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
                  "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
                  "-c:a", "aac", "-movflags", "+faststart", str(o)])
        else:
            fc = f"[0:v]{fit}[v0];[1:v]{fit}[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
            _run(["-i", str(c), "-i", str(a), "-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast",
                  "-crf", "24", "-movflags", "+faststart", str(o)])
        return o.read_bytes()


# ============================================================== reproductor del portal
def player_html(clip: bytes, fig, caption: str = "") -> str:
    """Clip real → animación 2D en secuencia. Botones para ver cada parte por separado o repetir la secuencia."""
    import plotly.io as pio
    meta = (fig.layout.meta or {}) if hasattr(fig.layout, "meta") else {}
    frame_ms = float(meta.get("frame_ms", 100)) if isinstance(meta, dict) else 100.0
    plot = pio.to_html(fig, full_html=False, include_plotlyjs=True, div_id="efos_anim", auto_play=False,
                       config={"displayModeBar": False, "responsive": True})
    b64 = base64.b64encode(clip).decode()
    cap = (caption or "").replace("<", "&lt;")
    return f"""
<style>
 body{{margin:0;font-family:Inter,'Segoe UI',sans-serif;color:#0F172A}}
 .bar{{display:flex;gap:8px;align-items:center;margin:4px 0 8px}}
 .bar button{{border:1px solid #CBD5E1;background:#fff;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:13px}}
 .bar button.on{{background:#0F172A;color:#fff;border-color:#0F172A}}
 .st{{font-size:12px;color:#64748B;margin-left:auto}}
 #vbox video{{width:100%;max-height:600px;background:#000;border-radius:10px}}
 #abox{{display:none}}
</style>
<div class="bar">
  <button id="bseq" class="on">▶ Secuencia: clip + animación</button>
  <button id="bclip">Solo clip</button>
  <button id="banim">Solo animación 2D</button>
  <span class="st" id="st">{cap}</span>
</div>
<div id="vbox"><video id="vid" controls playsinline preload="auto" src="data:video/mp4;base64,{b64}"></video></div>
<div id="abox">{plot}</div>
<script>
(function(){{
  const vid=document.getElementById('vid'), vbox=document.getElementById('vbox'), abox=document.getElementById('abox');
  const st=document.getElementById('st'); let seq=true;
  const btn={{seq:document.getElementById('bseq'),clip:document.getElementById('bclip'),anim:document.getElementById('banim')}};
  function mark(k){{for(const b in btn) btn[b].classList.toggle('on',b===k);}}
  function gd(){{return document.getElementById('efos_anim');}}
  function showClip(){{abox.style.display='none'; vbox.style.display='block';}}
  function playAnim(){{
    vbox.style.display='none'; abox.style.display='block'; vid.pause();
    const g=gd(); if(!g||!window.Plotly) return;
    Plotly.Plots.resize(g);
    st.textContent='Animación 2D del mismo tramo';
    Plotly.animate(g,['0'],{{mode:'immediate',frame:{{duration:0,redraw:true}},transition:{{duration:0}}}}).then(()=>
      Plotly.animate(g,null,{{frame:{{duration:{frame_ms:.1f},redraw:true}},transition:{{duration:0}},fromcurrent:true,mode:'immediate'}}));
  }}
  vid.addEventListener('ended',()=>{{ if(seq) playAnim(); }});
  btn.seq.onclick=()=>{{seq=true;mark('seq');showClip();st.textContent='Clip real del partido';vid.currentTime=0;vid.play();}};
  btn.clip.onclick=()=>{{seq=false;mark('clip');showClip();st.textContent='Clip real del partido';vid.currentTime=0;vid.play();}};
  btn.anim.onclick=()=>{{seq=false;mark('anim');playAnim();}};
}})();
</script>"""
