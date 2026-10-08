"""EFOS v0.4.7 — authenticated, repository-first, football-native Streamlit portal.

Run from efos/:
    python -m streamlit run visualization/efos_dashboard.py

Flow:
    Login -> Liga -> Temporada -> Equipo -> Periodo -> EFOS -> Informe Ejecutivo.
"""
from __future__ import annotations

import hashlib
import html
import sys
import base64
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import efos_figures as F  # noqa: E402
import football_maps as M  # noqa: E402
import action_explorer as X  # noqa: E402
from coach_story.coach_profile import _starters, _formation  # noqa: E402
from auth.auth import authenticate  # noqa: E402
from coach_story.report_generator import render_coach_story_md  # noqa: E402
from coach_story.pdf_report import build_coach_story_pdf  # noqa: E402
from coach_story.football_pdf import build_football_pdf, _shirt_name  # noqa: E402
from coach_story.executive_pdf import build_executive_pdf  # noqa: E402
from coach_story.football_report import GLOSSARY, POSITION_ES, DTC_FOOTBALL  # noqa: E402
from ingestion.input_adapter import load_event_csvs  # noqa: E402
from intelligence.team_scope import team_coverage  # noqa: E402
from run_sprint4 import run as run_sprint4  # noqa: E402
from ui.data_catalog import scan_catalog, period_options, paths_for_selection, context_for_selection  # noqa: E402
from intelligence.league_similarity import rank_similarity  # noqa: E402

RUNTIME_DIR = BASE_DIR / ".runtime"
STRETCH = {"use_container_width": True}

st.set_page_config(page_title="EFOS", page_icon="⚽", layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Enterprise visual system
# ---------------------------------------------------------------------------
ENTERPRISE_CSS = """
<style>
:root {
  --efos-bg:#F4F5F7;
  --efos-bg-soft:#FBFBFC;
  --efos-surface:rgba(255,255,255,.78);
  --efos-surface-strong:#FFFFFF;
  --efos-ink:#0B1220;
  --efos-muted:#697586;
  --efos-line:rgba(15,23,42,.08);
  --efos-line-strong:rgba(15,23,42,.13);
  --efos-accent:#C89B3C;
  --efos-accent-soft:rgba(200,155,60,.14);
  --efos-shadow:0 8px 32px rgba(15,23,42,.07);
  --efos-shadow-soft:0 3px 14px rgba(15,23,42,.05);
}
html, body, [class*="css"] {font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}
[data-testid="stSidebar"], header[data-testid="stHeader"], footer {display:none !important;}
.stApp {
  color:var(--efos-ink);
  background:
    radial-gradient(circle at 18% 14%, rgba(255,255,255,.92), rgba(255,255,255,0) 28%),
    radial-gradient(circle at 82% 20%, rgba(200,155,60,.10), rgba(200,155,60,0) 26%),
    radial-gradient(circle at 64% 76%, rgba(15,23,42,.05), rgba(15,23,42,0) 28%),
    linear-gradient(180deg, #F8F8F8 0%, #F2F4F7 100%);
}
.block-container {max-width:1500px; padding-top:1rem; padding-bottom:3rem;}
h1,h2,h3,h4 {color:var(--efos-ink); letter-spacing:-0.03em;}
p, label, .stCaption {color:var(--efos-muted);}
.efos-login-stage {
  min-height:82vh; display:flex; align-items:center; justify-content:center;
}
.efos-shell {
  background:linear-gradient(180deg, rgba(255,255,255,.72), rgba(255,255,255,.56));
  border:1px solid rgba(255,255,255,.65);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-radius:28px;
  box-shadow:0 22px 60px rgba(15,23,42,.10);
}
.efos-panel {
  background:var(--efos-surface); border:1px solid var(--efos-line); border-radius:24px;
  box-shadow:var(--efos-shadow-soft); backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.efos-topbar {
  background:rgba(255,255,255,.78); border:1px solid var(--efos-line); border-radius:18px;
  padding:14px 18px; box-shadow:var(--efos-shadow-soft); backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px); margin-bottom:10px;
}
.efos-logo-wrap {display:flex; align-items:center; gap:14px;}
.efos-logo-stack {position:relative; width:112px; height:34px;}
.efos-logo-stack.compact {width:86px; height:28px;}
.efos-logo-circle {
  position:absolute; top:0; width:34px; height:34px; border-radius:50%;
  background:rgba(11,18,32,.08); border:1px solid rgba(11,18,32,.04);
  filter:blur(.15px);
}
.efos-logo-stack.compact .efos-logo-circle {width:28px;height:28px;}
.efos-logo-circle.c1 {left:0; background:rgba(15,23,42,.06);}
.efos-logo-circle.c2 {left:18px; background:rgba(15,23,42,.10);}
.efos-logo-circle.c3 {left:36px; background:rgba(15,23,42,.18);}
.efos-logo-circle.c4 {left:54px; background:rgba(15,23,42,.32);}
.efos-logo-circle.c5 {left:72px; background:rgba(200,155,60,.92); box-shadow:0 0 36px rgba(200,155,60,.18);}
.efos-logo-stack.compact .efos-logo-circle.c2{left:14px;}
.efos-logo-stack.compact .efos-logo-circle.c3{left:28px;}
.efos-logo-stack.compact .efos-logo-circle.c4{left:42px;}
.efos-logo-stack.compact .efos-logo-circle.c5{left:56px;}
.efos-logo-text {font-size:1.9rem; font-weight:300; letter-spacing:.58rem; color:var(--efos-ink);}
.efos-logo-text.compact {font-size:1.2rem; letter-spacing:.28rem;}
.efos-brand-sub {font-size:.72rem; color:var(--efos-muted); text-transform:uppercase; letter-spacing:.12em;}
.efos-brand-headline {font-size:2.1rem; font-weight:760; letter-spacing:-.05em; color:var(--efos-ink); line-height:1.05;}
.efos-brand-copy {font-size:1rem; line-height:1.72; color:#5B6677; max-width:34rem;}
.efos-kicker {font-size:.74rem; text-transform:uppercase; letter-spacing:.16em; color:#8A6A21; font-weight:800;}
.efos-files {font-size:.84rem; color:var(--efos-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.efos-context-title {font-size:.74rem; color:var(--efos-muted); text-transform:uppercase; letter-spacing:.12em; font-weight:700;}
.efos-user-chip {display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; background:rgba(15,23,42,.04); color:var(--efos-ink); font-weight:700;}
.efos-user-dot {width:8px; height:8px; border-radius:50%; background:var(--efos-accent); box-shadow:0 0 0 4px rgba(200,155,60,.14);}
.efos-card {background:var(--efos-surface-strong); border:1px solid var(--efos-line); border-radius:18px; padding:20px 22px; box-shadow:var(--efos-shadow-soft); height:100%;}
.efos-card-eyebrow {font-size:.72rem; color:var(--efos-muted); text-transform:uppercase; letter-spacing:.08em; font-weight:700;}
.efos-card-value {font-size:1.8rem; line-height:1.15; font-weight:760; color:var(--efos-ink); margin-top:7px;}
.efos-card-note {font-size:.82rem; color:var(--efos-muted); margin-top:6px;}
.efos-story {background:linear-gradient(135deg,#0C1322 0%,#111B30 72%,#4E3B1B 120%); border-radius:22px; padding:26px 28px; color:white; margin:10px 0 20px; box-shadow:0 14px 36px rgba(15,23,42,.14);}
.efos-story h3,.efos-story p {color:white !important;}
.efos-story-kicker {font-size:.72rem; text-transform:uppercase; letter-spacing:.1em; color:#E8C679 !important; font-weight:700;}
.efos-story-copy {font-size:1.12rem; line-height:1.6; margin:.45rem 0 0;}
.efos-section-title {font-size:1.22rem; font-weight:760; color:var(--efos-ink); margin:1rem 0 .3rem;}
.efos-section-sub {font-size:.9rem; color:var(--efos-muted); margin-bottom:1rem;}
.efos-chip {display:inline-block; padding:5px 9px; margin:2px 4px 2px 0; border-radius:999px; background:#F6F7F9; border:1px solid var(--efos-line); color:#475569; font-size:.74rem;}
.efos-confidence {display:inline-block; padding:3px 8px; border-radius:999px; background:var(--efos-accent-soft); color:#8A6A21; font-size:.72rem; font-weight:700;}
.efos-question {background:#FBFCFE; border:1px solid rgba(200,155,60,.35); border-left:4px solid var(--efos-accent); border-radius:16px; padding:16px 18px; margin:8px 0 22px; color:#4F3D16; font-size:1rem; line-height:1.55;}
.efos-question b {color:#4F3D16;}
.efos-insight {background:var(--efos-surface-strong); border:1px solid var(--efos-line); border-radius:18px; padding:18px 20px; min-height:155px; box-shadow:var(--efos-shadow-soft);}
.efos-insight-kicker {font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.09em; color:#8A6A21;}
.efos-insight-title {font-size:1.08rem; font-weight:760; color:var(--efos-ink); margin:.35rem 0 .35rem;}
.efos-insight-copy {font-size:.88rem; line-height:1.5; color:var(--efos-muted);}
.efos-narrative {background:#FFFFFF; border:1px solid var(--efos-line); border-radius:18px; padding:22px 24px; margin:8px 0 18px;}
.efos-narrative h4 {font-size:1rem; margin:0 0 8px; color:var(--efos-ink);} 
.efos-narrative p {font-size:.95rem; line-height:1.65; color:#334155; margin:0;}
.efos-section-band {margin:30px 0 12px; padding-top:8px; border-top:1px solid var(--efos-line);} 
.efos-section-band-title {font-size:1.35rem; font-weight:780; color:var(--efos-ink); letter-spacing:-.025em;}
.efos-section-band-sub {font-size:.9rem; color:var(--efos-muted); margin-top:3px;}
.efos-hero-gold {background:linear-gradient(135deg,#FFF8E7 0%,rgba(255,255,255,.96) 70%); border:1px solid rgba(200,155,60,.48); border-left:5px solid var(--efos-accent); border-radius:18px; padding:22px 24px; margin:10px 0 20px; box-shadow:0 8px 24px rgba(153,112,24,.08);} 
.efos-hero-gold .eyebrow{font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;color:#8A681F;font-weight:800;}
.efos-method-note {font-size:.82rem; line-height:1.5; color:#64748B; background:#FAFBFC; border:1px solid var(--efos-line); border-radius:12px; padding:12px 14px;}
.efos-help-list {margin:0; padding-left:1.1rem; color:#5B6677; line-height:1.8;}
.divider-soft {height:1px; background:linear-gradient(90deg, transparent, rgba(15,23,42,.08), transparent); margin:18px 0;}
[data-testid="stForm"] {
  background:linear-gradient(180deg, rgba(255,255,255,.76), rgba(255,255,255,.62));
  border:1px solid rgba(255,255,255,.72);
  border-radius:24px;
  padding:22px 22px 18px;
  box-shadow:0 18px 44px rgba(15,23,42,.08);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] {margin-top:8px;}
.stTextInput>div>div>input, .stSelectbox>div>div, .stTextArea textarea {
  border-radius:14px !important; border:1px solid var(--efos-line-strong) !important;
  background:rgba(255,255,255,.92) !important;
}
.stButton>button, .stDownloadButton>button, .stFormSubmitButton>button {
  border-radius:14px; border:1px solid rgba(15,23,42,.08); font-weight:650; min-height:42px; box-shadow:none;
  background:rgba(255,255,255,.9); color:var(--efos-ink);
}
 .stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover {border-color:rgba(200,155,60,.5); color:#73581B;}
.stButton>button[kind="primary"], .stFormSubmitButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {
  background:linear-gradient(135deg,#121A2B 0%,#1B2946 68%,#6C5120 120%); color:white; border-color:#121A2B;
}
.stButton>button[kind="secondary"] {background:rgba(255,255,255,.78);}
.stFileUploader {background:white; border-radius:14px;}
[data-testid="stFileUploaderDropzone"] {border:1.5px dashed #94A3B8; background:#FAFCFF; border-radius:14px; padding:18px;}
div[role="radiogroup"] {background:rgba(255,255,255,.82); border:1px solid var(--efos-line); border-radius:14px; padding:5px 8px; box-shadow:var(--efos-shadow-soft); gap:4px;}
div[role="radiogroup"] label {padding:7px 11px; border-radius:10px; margin:0; transition:all .15s ease;}
div[role="radiogroup"] label:has(input:checked) {background:rgba(200,155,60,.14); color:#6C5120;}
[data-testid="stDataFrame"] {border:1px solid var(--efos-line); border-radius:14px; overflow:hidden;}
div[data-testid="stMetric"] {background:rgba(255,255,255,.88); border:1px solid var(--efos-line); border-radius:16px; padding:14px 16px; box-shadow:var(--efos-shadow-soft);} 
div[data-testid="stMetricLabel"] {color:var(--efos-muted);} 
div[data-testid="stMetricValue"] {color:var(--efos-ink); font-weight:760;} 
hr {border-color:var(--efos-line);} 

.efos-page-hero {
  background:linear-gradient(135deg, rgba(255,255,255,.82) 0%, rgba(255,255,255,.62) 52%, rgba(200,155,60,.12) 100%);
  border:1px solid rgba(255,255,255,.74);
  border-radius:26px;
  padding:28px 28px 24px;
  box-shadow:0 20px 54px rgba(15,23,42,.08);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  margin:6px 0 18px;
}
.efos-page-kicker {font-size:.72rem; text-transform:uppercase; letter-spacing:.16em; color:#8A6A21; font-weight:800;}
.efos-page-title {font-size:2rem; line-height:1.02; font-weight:800; color:var(--efos-ink); letter-spacing:-.045em; margin-top:10px;}
.efos-page-copy {font-size:.98rem; color:#5B6677; margin-top:8px; line-height:1.7; max-width:60rem;}
.efos-pill-row {display:flex; gap:10px; flex-wrap:wrap; margin-top:16px;}
.efos-pill {display:inline-flex; align-items:center; gap:8px; padding:9px 12px; border-radius:999px; background:rgba(255,255,255,.76); border:1px solid rgba(15,23,42,.08); color:#334155; font-size:.84rem; box-shadow:var(--efos-shadow-soft);}
.efos-dot {width:8px; height:8px; border-radius:50%; background:var(--efos-accent);}
.efos-subgrid-title {font-size:1.05rem; font-weight:760; color:var(--efos-ink); margin:.3rem 0 .7rem;}

</style>
"""
st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)

NAV_ITEMS = ["Selección de Equipo", "★ Informe Ejecutivo", "Modelo de Juego y DT", "Ataque Organizado",
             "Defensa Organizada", "Transiciones", "Balón Parado", "Momentos del Partido"]
# Mismo glosario que el informe para cuerpo técnico (coach_story/football_report.py)
HUMAN_DIMS = {k: GLOSSARY[k] for k in ("OC", "HPS", "RPS", "DS", "DER")}
DTC_HUMAN = DTC_FOOTBALL


def _efos_logo(compact: bool = False) -> str:
    cls = "compact" if compact else ""
    return f"""
    <div class="efos-logo-wrap">
      <div>
        <div class="efos-logo-stack {cls}">
          <span class="efos-logo-circle c1"></span>
          <span class="efos-logo-circle c2"></span>
          <span class="efos-logo-circle c3"></span>
          <span class="efos-logo-circle c4"></span>
          <span class="efos-logo-circle c5"></span>
        </div>
        <div class="efos-logo-text {cls}">EFOS</div>
      </div>
    </div>
    """


def _page_intro(title: str, subtitle: str, pills: list[str] | None = None, eyebrow: str = "EFOS") -> None:
    pills_html = ""
    if pills:
        pills_html = "<div class='efos-pill-row'>" + "".join(
            f"<span class='efos-pill'><span class='efos-dot'></span>{html.escape(str(p))}</span>" for p in pills if p
        ) + "</div>"
    st.markdown(
        f"<div class='efos-page-hero'><div class='efos-page-kicker'>{html.escape(eyebrow)}</div>"
        f"<div class='efos-page-title'>{html.escape(title)}</div>"
        f"<div class='efos-page-copy'>{html.escape(subtitle)}</div>{pills_html}</div>",
        unsafe_allow_html=True,
    )


def _section_lead(title: str, subtitle: str = "") -> None:
    st.markdown(f"<div class='efos-section-band'><div class='efos-section-band-title'>{html.escape(title)}</div>"
                f"<div class='efos-section-band-sub'>{html.escape(subtitle)}</div></div>", unsafe_allow_html=True)


def _init_state() -> None:
    defaults = {
        "authenticated": False, "username": None, "role": None,
        "analysis": None, "analysis_digest": None,
        "upload_names": [], "upload_paths": [],
        "ambiguous_upload_paths": [], "ambiguous_upload_digest": None,
        "ambiguous_upload_names": [], "ambiguous_teams": [],
        "dataset_context": None,
        "nav": "Selección de Equipo",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_analysis(keep_nav: bool = False) -> None:
    for key, value in {
        "analysis": None, "analysis_digest": None,
        "upload_names": [], "upload_paths": [],
        "ambiguous_upload_paths": [], "ambiguous_upload_digest": None,
        "ambiguous_upload_names": [], "ambiguous_teams": [],
        "dataset_context": None,
    }.items():
        st.session_state[key] = value
    if not keep_nav:
        st.session_state["nav"] = "Selección de Equipo"


def _logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def _login_page() -> None:
    left, right = st.columns([1.1, .9], gap="large")
    with left:
        st.markdown(f"""
        <div class="efos-shell" style="padding:34px 34px 30px; min-height:540px;">
          <div class="efos-kicker">Emerging Football Operating System</div>
          <div style="margin-top:18px;">{_efos_logo()}</div>
          <div style="height:24px"></div>
          <div class="efos-brand-headline">Interfaz táctica, limpia y enfocada en decisiones.</div>
          <div style="height:14px"></div>
          <div class="efos-brand-copy">Accede al entorno EFOS para explorar modelos de juego, momentos del partido y reportes ejecutivos con una experiencia minimalista, más visual y lista para presentar.</div>
          <div class="divider-soft"></div>
          <div class="efos-panel" style="padding:18px 18px 14px;">
            <div class="efos-kicker" style="margin-bottom:10px;">Qué encontrarás</div>
            <ul class="efos-help-list">
              <li>Selección automática de liga, temporada, equipo y periodo.</li>
              <li>Coach Story visual en PDF y resumen táctico listo para cuerpo técnico.</li>
              <li>Mapas, patrones y momentos clave traducidos a lenguaje futbolístico.</li>
            </ul>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with right:
        st.markdown("""
        <div class="efos-shell" style="padding:34px 34px 24px; min-height:540px; display:flex; flex-direction:column; justify-content:center;">
          <div class="efos-kicker">Acceso</div>
          <div style="font-size:2rem;font-weight:760;letter-spacing:-.04em;color:#0B1220;margin-top:8px;">Iniciar sesión</div>
          <div style="font-size:.96rem;color:#697586;margin-top:8px; line-height:1.65;">Ingresa con tus credenciales para continuar al dashboard. El acceso está protegido y cada sesión conserva tu contexto de trabajo.</div>
          <div style="height:20px"></div>
        </div>
        """, unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")
        st.caption("Usuarios configurados en la base local de autenticación. Contacta al administrador si necesitas acceso.")
        if submitted:
            user = authenticate(username, password)
            if user is None:
                st.error("Usuario o contraseña incorrectos.")
                return
            st.session_state["authenticated"] = True
            st.session_state["username"] = user.username
            st.session_state["role"] = user.role
            _clear_analysis()
            st.rerun()

def _safe_output_dir(username: str, digest: str) -> Path:
    token = hashlib.sha256(username.encode("utf-8")).hexdigest()[:10]
    return RUNTIME_DIR / "outputs" / token / digest[:16]


def _digest_many(digests: list[str]) -> str:
    payload = "|".join(sorted(digests)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _analyze_paths(paths: list[Path], digest: str, names: list[str], focal_team: str = "auto") -> None:
    outdir = _safe_output_dir(str(st.session_state["username"]), digest)
    result = run_sprint4(paths, focal_team=focal_team, outdir=outdir)
    st.session_state["analysis"] = result
    st.session_state["analysis_digest"] = digest
    st.session_state["upload_names"] = list(names)
    st.session_state["upload_paths"] = [str(p) for p in paths]
    st.session_state["ambiguous_upload_paths"] = []
    st.session_state["ambiguous_upload_digest"] = None
    st.session_state["ambiguous_upload_names"] = []
    st.session_state["ambiguous_teams"] = []
    st.session_state["nav"] = "★ Informe Ejecutivo"


def _prepare_ambiguous_selection(paths: list[Path], digest: str, names: list[str]) -> None:
    events, _ = load_event_csvs(paths)
    coverage = team_coverage(events)
    st.session_state["ambiguous_upload_paths"] = [str(p) for p in paths]
    st.session_state["ambiguous_upload_digest"] = digest
    st.session_state["ambiguous_upload_names"] = list(names)
    st.session_state["ambiguous_teams"] = coverage["team"].astype(str).tolist()


def _header() -> None:
    ctx = st.session_state.get("dataset_context") or {}
    context_text = " · ".join([str(x) for x in [ctx.get("league"), ctx.get("season"), ctx.get("team"), ctx.get("period")] if x]) or "Sin equipo seleccionado"
    c1, c2, c3, c4 = st.columns([1.7, 4.8, 1.9, .9])
    with c1:
        st.markdown(f"<div class='efos-topbar'>{_efos_logo(compact=True)}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='efos-topbar'><div class='efos-context-title'>Muestra activa</div><div class='efos-files'>{html.escape(context_text)}</div></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div class='efos-topbar'><div class='efos-context-title'>Sesión</div><div class='efos-user-chip'><span class='efos-user-dot'></span>{html.escape(str(st.session_state['username']))}</div></div>", unsafe_allow_html=True)
    with c4:
        if st.button("Salir", use_container_width=True):
            _logout()
    active_options = NAV_ITEMS if st.session_state.get("analysis") is not None else ["Selección de Equipo"]
    if st.session_state.get("nav") not in active_options:
        st.session_state["nav"] = active_options[0]
    st.session_state["nav"] = st.radio("Navegación", active_options, index=active_options.index(st.session_state["nav"]), horizontal=True, label_visibility="collapsed")

def _catalog() -> pd.DataFrame:
    return scan_catalog(BASE_DIR / "data" / "raw" / "statsbomb", BASE_DIR / "config" / "team_metadata.yaml")


def _selection_panel() -> None:
    _page_intro("Selección de Equipo", "Explora la base disponible y abre el análisis sin fricción: liga, temporada, club y periodo.", ["Repositorio conectado", "Sin carga manual", "Datos procesables"], eyebrow="Inicio")
    catalog = _catalog()
    if catalog.empty:
        st.error("No hay datasets en data/raw/statsbomb. Añade archivos al repositorio para habilitar la selección automática.")
        return

    leagues = sorted(catalog["league"].dropna().unique().tolist())
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        league = st.selectbox("Liga", leagues, index=0)
    seasons = sorted(catalog.loc[catalog["league"].eq(league), "season"].dropna().unique().tolist(), reverse=True)
    with c2:
        season = st.selectbox("Temporada", seasons, index=0)
    teams = sorted(catalog.loc[catalog["league"].eq(league) & catalog["season"].eq(season), "team"].dropna().unique().tolist())
    with c3:
        team = st.selectbox("Equipo", teams, index=0)
    periods = period_options(catalog, league, season, team)
    with c4:
        period = st.selectbox("Periodo", periods, index=0)

    paths = paths_for_selection(catalog, league, season, team, period)
    ctx = context_for_selection(catalog, league, season, team, period)
    st.markdown(
        f"<div class='efos-narrative'><h4>Muestra seleccionada</h4><p><b>{html.escape(team)}</b> · {html.escape(season)} · {html.escape(period)} · "
        f"{len(paths)} archivo(s) en repositorio" + (f" · DT: <b>{html.escape(ctx['coach'])}</b>" if ctx.get('coach') else "") + "</p></div>",
        unsafe_allow_html=True,
    )
    if ctx.get("coach") is None:
        st.info("El nombre del DT no está documentado en config/team_metadata.yaml. EFOS no lo inferirá ni lo inventará.")

    if st.button("Analizar selección", type="primary", use_container_width=True, disabled=not bool(paths)):
        digest = _digest_many([hashlib.sha256(str(p).encode()).hexdigest() for p in paths])
        try:
            with st.spinner(f"Analizando {team} · {period}…"):
                _analyze_paths(paths, digest, [p.name for p in paths], focal_team=team)
                st.session_state["dataset_context"] = ctx
                if st.session_state.get("analysis") is not None:
                    st.session_state["analysis"]["dataset_context"] = ctx
                    st.session_state["nav"] = "★ Informe Ejecutivo"
            st.rerun()
        except Exception as exc:
            st.error(f"No fue posible analizar la selección: {exc}")

    if st.session_state.get("analysis") is not None:
        st.divider()
        if st.button("Cambiar equipo / periodo"):
            _clear_analysis(keep_nav=True)
            st.session_state["dataset_context"] = None
            st.session_state["nav"] = "Selección de Equipo"
            st.rerun()

def show(fig) -> None:
    st.plotly_chart(fig, **STRETCH, config={"displaylogo": False, "toImageButtonOptions": {"format": "png", "scale": 3}})


def _pdf_bytes(result: dict) -> bytes:
    path = result.get("coach_story_pdf_path")
    if path and Path(path).exists():
        return Path(path).read_bytes()
    return build_coach_story_pdf(result)


def _coach_story_report(result: dict, team: str, preview: bool = True) -> None:
    # PDF is the formal Coach Story deliverable; markdown remains a secondary audit export.
    pdf = _pdf_bytes(result)
    safe_team = team.replace(" ", "_").replace("/", "-")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.download_button(
            "Descargar Coach Story (PDF)",
            data=pdf,
            file_name=f"EFOS_Coach_Story_{safe_team}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    with c2:
        story_md = render_coach_story_md(result["coach_story"], result["evidence"])
        st.download_button(
            "Descargar anexo metodológico (.md)",
            data=story_md.encode("utf-8"),
            file_name=f"EFOS_Coach_Story_{safe_team}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    if preview:
        with st.expander("Vista previa del reporte PDF", expanded=True):
            encoded = base64.b64encode(pdf).decode("ascii")
            pdf_html = (
                '<div style="border:1px solid #E2E8F0;border-radius:14px;overflow:hidden;background:#fff;">'
                f'<embed src="data:application/pdf;base64,{encoded}#toolbar=1&navpanes=0&scrollbar=1" '
                'type="application/pdf" width="100%" height="900px" />'
                '</div>'
            )
            components.html(pdf_html, height=930, scrolling=True)


def _level_100(v: float) -> str:
    if v >= 85: return "Muy alta"
    if v >= 72: return "Alta"
    if v >= 60: return "Media-alta"
    if v >= 45: return "Media"
    return "Baja"


def _pressure_level(v: float) -> str:
    if v >= .65: return "Muy alta"
    if v >= .48: return "Alta"
    if v >= .32: return "Media-alta"
    if v >= .18: return "Media"
    return "Baja"


def _pct_text(v) -> str:
    return "N/A" if v is None else f"{100*float(v):.1f}%"


def _pm_text(v) -> str:
    return "N/A" if v is None else f"{float(v):.1f}/partido"


def _metric_card(title: str, value: str, note: str) -> None:
    st.markdown(f"<div class='efos-card'><div class='efos-card-eyebrow'>{html.escape(title)}</div><div class='efos-card-value'>{html.escape(value)}</div><div class='efos-card-note'>{html.escape(note)}</div></div>", unsafe_allow_html=True)


def _context(result: dict):
    team = result["focal_team"]
    events = result["events"]
    dims = result["esi_dimensions"]
    esi = float(result["ESI"])
    n_matches = int(events.loc[events["team"].eq(team), "match_id"].nunique())
    n_team_events = int(events["team"].eq(team).sum())
    pci = float(result.get("pressure_summary", {}).get("mean_pci", 0.0))
    return team, events, dims, esi, n_matches, n_team_events, pci


def _claim_by_id(tf: dict, claim_id: str) -> str | None:
    for claim in tf.get("claims", []) if isinstance(tf, dict) else []:
        if claim.get("id") == claim_id:
            return claim.get("claim")
    return None


def _story_section(title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='efos-section-band'><div class='efos-section-band-title'>{html.escape(title)}</div>"
        f"<div class='efos-section-band-sub'>{html.escape(subtitle)}</div></div>",
        unsafe_allow_html=True,
    )


def _insight_card(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f"<div class='efos-insight'><div class='efos-insight-kicker'>{html.escape(kicker)}</div>"
        f"<div class='efos-insight-title'>{html.escape(title)}</div>"
        f"<div class='efos-insight-copy'>{html.escape(copy)}</div></div>",
        unsafe_allow_html=True,
    )


def _coach_story_page(result: dict) -> None:
    team, events, dims, esi, n_matches, n_team_events, pci = _context(result)
    story = result.get("coach_story", {})
    executive = story.get("executive_summary", {})
    system = story.get("system_identity", {})
    tf = story.get("tactical_framework", {})
    dynamic = story.get("dynamic_states", {})
    temporal = story.get("temporal_evolution", {})
    traps = story.get("defensive_traps", {})
    sig = story.get("coach_tactical_signature_interpretation", {})
    principles = story.get("coach_principles", [])

    strong = system.get("strongest_relative", "RPS")
    weak = system.get("weakest_relative", "OC")
    strong_label = HUMAN_DIMS.get(strong, (strong, ""))[0]
    weak_label = HUMAN_DIMS.get(weak, (weak, ""))[0]

    st.markdown(f"# Coach Story — {team}")
    st.caption(
        f"Historia táctica generada automáticamente a partir de {n_matches} partidos · "
        f"{n_team_events:,} acciones del equipo · {len(st.session_state.get('upload_names', []))} archivo(s) consolidados"
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _metric_card("Identidad del sistema", f"{esi:.0f} / 100", "EFOS System Identity Index · ESI")
    with c2:
        _metric_card("Estabilidad bajo presión", _level_100(float(dims.get("HPS", 0))), f"{float(dims.get('HPS',0)):.1f}/100")
    with c3:
        _metric_card("Presión contextual", _pressure_level(pci), f"PCI medio {pci:.3f}")
    with c4:
        _metric_card("Respuesta ante riesgo", _level_100(float(dims.get("RPS", 0))), f"{float(dims.get('RPS',0)):.1f}/100")

    narrative = executive.get("narrative") or story.get("conclusion") or "No hay narrativa disponible para la muestra."
    st.markdown(
        f"<div class='efos-story'><div class='efos-story-kicker'>Coach Story · lectura ejecutiva</div>"
        f"<div class='efos-story-copy'>{html.escape(narrative)}</div></div>",
        unsafe_allow_html=True,
    )
    key_question = executive.get("key_question")
    if key_question:
        st.markdown(
            f"<div class='efos-question'><b>Pregunta que deja la muestra</b><br>{html.escape(key_question)}</div>",
            unsafe_allow_html=True,
        )

    _story_section("La historia en tres ideas", "Qué debería recordar un entrenador antes de entrar al detalle técnico.")
    summary_lines = tf.get("summary", []) if isinstance(tf, dict) else []
    a, b, c = st.columns(3)
    with a:
        _insight_card("Identidad", strong_label, f"{float(dims.get(strong,0)):.1f}/100. Es la dimensión relativamente más alta dentro del perfil EFOS de esta muestra.")
    with b:
        _insight_card("Señal a observar", weak_label, f"{float(dims.get(weak,0)):.1f}/100. Es la dimensión relativamente más variable; no constituye por sí sola un benchmark negativo de liga.")
    with c:
        change_claim = dynamic.get("claims", [{}])[0].get("claim") if dynamic.get("claims") else "EFOS segmenta los partidos en ventanas para detectar control, presión creciente, inestabilidad y recuperación."
        _insight_card("Cómo cambia", "Momentos del partido", change_claim)

    # --- Sin balón ----------------------------------------------------------
    _story_section("Sin balón", "Cómo intenta recuperar, restringir y controlar el espacio el equipo.")
    d = tf.get("defensive_profile", {}) if isinstance(tf, dict) else {}
    h = d.get("defensive_action_height", {})
    cp = d.get("counterpress", {})
    hp = d.get("high_press_share", {})
    opp_pressure = d.get("opponent_passes_under_pressure", {})
    offside = d.get("opponent_offside_outcomes", {})
    cols = st.columns(5)
    with cols[0]: _metric_card("Altura de intervención", f"x={float(h.get('value') or 0):.1f}", str(h.get("band") or "acción defensiva"))
    with cols[1]: _metric_card("Counterpress", _pm_text(cp.get("per_match")), "acciones por partido")
    with cols[2]: _metric_card("Presión alta", _pct_text(hp.get("rate")), "Pressure events en x≥80")
    with cols[3]: _metric_card("Pases rivales presionados", _pct_text(opp_pressure.get("rate")), "pases rivales under_pressure")
    with cols[4]: _metric_card("Offside rival", _pm_text(offside.get("per_match")), "proxy de coordinación de profundidad")
    defensive_claim = _claim_by_id(tf, "tactical_pressing_profile")
    height_claim = _claim_by_id(tf, "tactical_defensive_height")
    if defensive_claim or height_claim:
        st.markdown("<div class='efos-narrative'><h4>Lectura EFOS</h4>", unsafe_allow_html=True)
        if height_claim: st.write(height_claim)
        if defensive_claim: st.write(defensive_claim)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Con balón ----------------------------------------------------------
    _story_section("Con balón", "Cómo progresa, atrae presión y ocupa los espacios de avance.")
    build = tf.get("construction_progression", {}) if isinstance(tf, dict) else {}
    off = tf.get("offensive_microconcepts", {}) if isinstance(tf, dict) else {}
    value = tf.get("value_purpose", {}) if isinstance(tf, dict) else {}
    row1 = st.columns(4)
    with row1[0]: _metric_card("Atracción de presión", _pm_text(build.get("pressure_attraction_passes", {}).get("per_match")), "Fishing · proxy EVENT")
    with row1[1]: _metric_card("Liberación posterior", _pct_text(build.get("pressure_release_success", {}).get("rate")), "progresión tras atraer presión")
    with row1[2]: _metric_card("Half-space", _pm_text(build.get("halfspace_entries", {}).get("per_match")), "entradas completadas por partido")
    with row1[3]: _metric_card("Tercer hombre", _pm_text(build.get("third_man_progression_proxy", {}).get("per_match")), "proxy A→B→C progresivo")
    row2 = st.columns(4)
    with row2[0]: _metric_card("Ataque de intervalo", _pm_text(off.get("interval_entries", {}).get("per_match")), "intervalo central-lateral")
    with row2[1]: _metric_card("Centro a zona peligrosa", _pm_text(off.get("cross_to_danger_zone_proxy", {}).get("per_match")), "proxy Aliup")
    with row2[2]: _metric_card("xG generado", _pm_text(value.get("xg", {}).get("per_match")), "calidad esperada de remate")
    with row2[3]: _metric_card("OBV neto", _pm_text(value.get("obv", {}).get("per_match")), "valor neto de acciones elegibles")
    attack_claim = _claim_by_id(tf, "tactical_pressure_attraction")
    progression_claim = _claim_by_id(tf, "tactical_progression_mechanisms")
    micro_claim = _claim_by_id(tf, "tactical_attacking_microconcepts")
    if attack_claim or progression_claim or micro_claim:
        st.markdown("### Qué encuentra EFOS con balón")
        for claim in [attack_claim, progression_claim, micro_claim]:
            if claim: st.write(claim)
        st.caption("Fishing, tercer hombre y Aliup son proxies cuando el event data no observa directamente la intención o el movimiento sin balón.")

    # --- Cómo cambia --------------------------------------------------------
    _story_section("Cómo cambia el equipo", "El Coach Story no sólo resume promedios: busca cuándo el comportamiento se desvía y cómo responde.")
    windows = result.get("match_windows")
    states = result.get("dtc_states")
    if isinstance(windows, pd.DataFrame) and len(windows):
        show(F.fig_esi_timeline(windows, team))
    if dynamic.get("state_distribution"):
        rows = []
        for key, item in dynamic.get("state_distribution", {}).items():
            rows.append({"Momento": DTC_HUMAN.get(key, key), "Ventanas": item.get("windows", 0), "Share": f"{item.get('share_pct',0):.1f}%"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if temporal.get("phases"):
        st.markdown("### Evolución dentro de la muestra")
        phase_rows = []
        for r in temporal.get("phases", []):
            phase_rows.append({"Fase": r.get("phase"), "Partidos": r.get("matches"), "ESI": round(float(r.get("ESI",0)),1), "Organización": round(float(r.get("OC",0)),1), "Estabilidad presión": round(float(r.get("HPS",0)),1), "Respuesta riesgo": round(float(r.get("RPS",0)),1), "Decisión": round(float(r.get("DS",0)),1), "Tras pérdida": round(float(r.get("DER",0)),1)})
        st.dataframe(pd.DataFrame(phase_rows), hide_index=True, use_container_width=True)
        if temporal.get("claims"):
            st.write(temporal["claims"][0].get("claim", ""))

    # --- Principios y firma -------------------------------------------------
    _story_section("Principios que aparecen de forma recurrente", "Regularidades observadas en la muestra; no se presentan como instrucciones confirmadas del entrenador.")
    if principles:
        p_df = pd.DataFrame([
            {
                "Patrón candidato": p.get("display_name", p.get("principle")),
                "Incidencia": f"{float(p.get('value_pct',0)):.1f}%",
                "Confianza": f"{float(p.get('confidence_score',0)):.1f}/100",
                "Evidencia": int(p.get("evidence_n",0)),
                "Fuente": p.get("source"),
            }
            for p in principles
        ])
        st.dataframe(p_df, hide_index=True, use_container_width=True)
    else:
        st.info("No se detectaron principios candidatos suficientes con los umbrales actuales.")

    if sig.get("components"):
        st.markdown("### Coach Tactical Signature")
        st.caption("Vector descriptivo de la muestra; no es una calificación global del entrenador.")
        sig_rows = []
        for r in sig.get("components", []):
            val = r.get("value")
            sig_rows.append({"Componente": r.get("component"), "Valor": "N/A" if val is None else round(float(val),2), "Qué representa": r.get("meaning")})
        st.dataframe(pd.DataFrame(sig_rows), hide_index=True, use_container_width=True)

    # --- Traps --------------------------------------------------------------
    _story_section("Traps defensivos", "Secuencias de presión → restricción → resultado bajo la definición experimental del Sprint 4.")
    tc1, tc2, tc3, tc4 = st.columns(4)
    with tc1: _metric_card("Intentos", f"{int(traps.get('trap_attempts',0)):,}", "secuencias candidatas")
    with tc2: _metric_card("Exitosos", f"{int(traps.get('successful_traps',0)):,}", "según regla actual")
    with tc3: _metric_card("DTE", f"{100*float(traps.get('DTE',0)):.1f}%", "experimental · no benchmark")
    with tc4: _metric_card("Trap rate", f"{float(traps.get('trap_rate',0)):.2f}", "según denominador operativo")
    if traps.get("claims"):
        st.warning(traps["claims"][0].get("claim", "El motor de traps está en fase experimental."))

    # --- Conclusion ---------------------------------------------------------
    _story_section("¿Qué sistema parece estar construyendo?", "Síntesis de la evidencia disponible en la muestra cargada.")
    conclusion = story.get("conclusion") or narrative
    st.markdown(
        f"<div class='efos-story'><div class='efos-story-kicker'>Síntesis del Coach Story</div>"
        f"<div class='efos-story-copy'>{html.escape(conclusion)}</div></div>",
        unsafe_allow_html=True,
    )

    with st.expander("Ver límites metodológicos y trazabilidad"):
        limitations = story.get("limitations", [])
        for item in limitations:
            st.markdown(f"- {item}")
        claims = result.get("evidence", {}).get("claims", []) if isinstance(result.get("evidence"), dict) else []
        st.markdown(f"**Claims auditables:** {len(claims)}")
        st.caption("Cada claim conserva fuente, tamaño de muestra, confianza, limitación y evidencia para recorrer Coach Story → interpretación → métrica → evento → dato original.")

    with st.expander("Ver reporte técnico completo generado por EFOS"):
        st.markdown(render_coach_story_md(story, result.get("evidence", {})))

    _coach_story_report(result, team, preview=True)

# ---------------------------------------------------------------------------
# Páginas en lenguaje de fútbol (informe para cuerpo técnico)
# ---------------------------------------------------------------------------
def _fr(result: dict) -> dict:
    return result.get("football_report") or {}


def _vs_card(title: str, team_val: str, rival_val: str) -> None:
    _metric_card(title, team_val, f"sus rivales: {rival_val}")


def _pm_means(result: dict):
    pm = _fr(result).get("per_match")
    if not isinstance(pm, pd.DataFrame) or pm.empty:
        return None, None
    return pm[pm["es_focal"]].mean(numeric_only=True), pm[~pm["es_focal"]].mean(numeric_only=True)


def _football_pdf_bytes(result: dict) -> bytes:
    path = result.get("football_pdf_path")
    if path and Path(path).exists():
        return Path(path).read_bytes()
    return build_football_pdf(_fr(result))


# ---------------------------------------------------------------------------
# Explorador de acciones (mplsoccer): filtros colectivo / individual y por partido
# ---------------------------------------------------------------------------
def _xcache(result: dict) -> dict:
    """Datos preparados para el explorador; se calculan una vez por análisis."""
    c = result.get("_explorer")
    if c is None:
        team = result["focal_team"]
        e = X.prepare(result["events"])
        c = {"e": e, "team": team, "labels": dict(X.match_options(e, team)), "players": X.team_players(e, team)}
        c["tf"] = X.transition_frames(e, team)
        result["_explorer"] = c
    return c


def _scope_controls(key: str, c: dict, allow_individual: bool = True, label: str = "Tipo de análisis") -> dict:
    a, b, d = st.columns([1.1, 1.4, 2.5])
    opts = ["Colectivo · equipo", "Individual · jugador"] if allow_individual else ["Colectivo · equipo"]
    with a:
        scope = st.radio(label, opts, key=f"{key}_scope")
    player = None
    with b:
        if scope.startswith("Individual"):
            player = st.selectbox("Jugador", c["players"], key=f"{key}_player")
        else:
            st.selectbox("Jugador", ["Todo el equipo"], key=f"{key}_player_off", disabled=True)
    with d:
        sel = st.multiselect("Partido(s) · vacío = todo el torneo", list(c["labels"].values()), key=f"{key}_matches")
    inv = {v: k for k, v in c["labels"].items()}
    matches = [inv[x] for x in sel] or None
    who = player or c["team"]
    where = ("torneo completo" if not matches else (sel[0] if len(sel) == 1 else f"{len(sel)} partidos"))
    return {"player": player, "matches": matches, "label": f"{who} · {where}", "n_matches": len(matches) if matches else len(c["labels"])}


def _action_explorer(key: str, c: dict, catalog: dict, heat_cmap: str, heat_title: str) -> None:
    f = _scope_controls(key, c)
    names = list(catalog)
    chosen = st.multiselect("Acciones a mostrar (un campo por acción)", names, default=names, key=f"{key}_actions")
    if not chosen:
        st.info("Selecciona al menos una acción."); return
    frames = {n: X.apply_scope(catalog[n][1], f["matches"], f["player"]) for n in chosen}
    rows = []
    for n in chosen:
        d = frames[n]
        okr = X._success(d).mean() if len(d) else float("nan")
        rows.append({"Acción": n, "Total": len(d), "Por partido": round(len(d) / max(f["n_matches"], 1), 1),
                     "Con éxito": "—" if catalog[n][0] in ("lines", "shots") or pd.isna(okr) else f"{100 * okr:.0f} %"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.markdown(f"#### Mapa de calor · {f['label']}")
    allx = pd.concat([frames[n] for n in chosen]) if chosen else pd.DataFrame()
    st.pyplot(X.heatmap(allx, heat_title, ", ".join(chosen) if len(chosen) <= 3 else f"{len(chosen)} tipos de acción", cmap=heat_cmap),
              clear_figure=True, use_container_width=True)
    st.markdown(f"#### Un campo por acción · {f['label']}")
    cols = st.columns(2)
    for i, n in enumerate(chosen):
        with cols[i % 2]:
            st.pyplot(X.action_pitch(frames[n], catalog[n][0], n, f["label"]), clear_figure=True, use_container_width=True)


def _value_explorer(key: str, c: dict, obv_df: pd.DataFrame, xg_df: pd.DataFrame, obv_label: str, xg_label: str,
                    note: str, conceded_df: pd.DataFrame | None = None) -> None:
    """Suma del valor (OBV) y de la probabilidad de gol (xG) de un equipo o jugador en un partido o torneo."""
    f = _scope_controls(key, c, label="Valor de")
    o = X.apply_scope(obv_df, f["matches"], f["player"]); x = X.apply_scope(xg_df, f["matches"], f["player"])
    a, b, cc, d = st.columns(4)
    with a: _metric_card(obv_label, f"{o['obv_total_net'].sum():+.2f}", f"{o['obv_total_net'].sum() / max(f['n_matches'], 1):+.2f} por partido")
    with b: _metric_card(xg_label, f"{x['statsbomb_xg'].sum():.2f}", f"{x['statsbomb_xg'].sum() / max(f['n_matches'], 1):.2f} por partido")
    with cc: _metric_card("Acciones con valor", f"{int(o['obv_total_net'].notna().sum()):,}", "acciones con OBV disponible")
    with d: _metric_card("Remates", f"{len(x):,}", f"{int(x['shot_outcome'].eq('Goal').sum())} goles")
    import plotly.graph_objects as go
    if f["matches"] and len(f["matches"]) == 1:
        v = X.value_by_minute(o, x)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=v["minuto"], y=v["OBV acumulado"], name=obv_label, line=dict(color="#2563EB", width=3, shape="hv")))
        fig.add_trace(go.Scatter(x=v["minuto"], y=v["xG acumulado"], name=xg_label, line=dict(color="#C89B3C", width=3, shape="hv")))
        if conceded_df is not None and not f["player"]:
            cd = X.apply_scope(conceded_df, f["matches"]).sort_values("minuto_juego")
            fig.add_trace(go.Scatter(x=cd["minuto_juego"], y=cd["statsbomb_xg"].fillna(0).cumsum(), name="xG concedido",
                                     line=dict(color="#B91C1C", width=2, dash="dot", shape="hv")))
        fig.update_layout(title=f"Valor acumulado minuto a minuto · {f['label']}", xaxis_title="Minuto", yaxis_title="Acumulado",
                          height=380, paper_bgcolor="white", plot_bgcolor="white", legend=dict(orientation="h", y=-0.25),
                          font=dict(family="Inter, Segoe UI, sans-serif", color="#0F172A"))
        fig.update_xaxes(gridcolor="#E2E8F0", range=[0, max(95, float(v["minuto"].max() or 0) + 2)]); fig.update_yaxes(gridcolor="#E2E8F0")
        show(fig)
    else:
        labels = {m: l for m, l in c["labels"].items() if not f["matches"] or m in f["matches"]}
        v = X.value_by_match(o, x, labels)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=v["partido"], y=v["OBV"], name=obv_label, marker_color="#2563EB"))
        fig.add_trace(go.Bar(x=v["partido"], y=v["xG"], name=xg_label, marker_color="#C89B3C"))
        fig.add_trace(go.Scatter(x=v["partido"], y=v["xG"].cumsum(), name=f"{xg_label} acumulado", yaxis="y2",
                                 line=dict(color="#0F172A", width=2)))
        fig.update_layout(title=f"Valor por partido y acumulado del torneo · {f['label']}", barmode="group", height=420,
                          paper_bgcolor="white", plot_bgcolor="white", legend=dict(orientation="h", y=-0.35),
                          yaxis=dict(title="Por partido", gridcolor="#E2E8F0"), yaxis2=dict(title="Acumulado", overlaying="y", side="right"),
                          font=dict(family="Inter, Segoe UI, sans-serif", color="#0F172A"))
        fig.update_xaxes(tickangle=-45, tickfont=dict(size=9))
        show(fig)
    if not f["player"]:
        with st.expander("¿Quién aporta más valor en esta selección?"):
            st.dataframe(X.value_by_player(o, x).round(2), hide_index=True, use_container_width=True)
    st.caption(note)


def _lineup_section(result: dict, c: dict, team: str) -> None:
    lu = result.get("_lineups")
    if lu is None:
        lu = X.lineups_by_formation(_starters(c["e"], team), _formation); result["_lineups"] = lu
    if not lu:
        st.info("No hay posiciones de titulares suficientes para dibujar las alineaciones."); return
    opts = [f"{k} · {v['partidos']} partido{'s' if v['partidos'] != 1 else ''}" for k, v in lu.items()]
    pick = st.radio("Dibujos utilizados por el entrenador (de más a menos frecuente)", opts, horizontal=True, key="lineup_pick")
    shape = pick.split(" · ")[0]
    st.pyplot(X.lineup_pitch(shape, lu[shape], team, _shirt_name, POSITION_ES), clear_figure=True, use_container_width=True)
    st.caption("Cada posición muestra al jugador que más veces fue titular en ella con ese dibujo y su alternativa. "
               "El dibujo se reconstruye con las posiciones StatsBomb de los titulares antes del primer cambio.")


def _report_page(result: dict) -> None:
    fr = _fr(result)
    if not fr:
        st.info("Este análisis no tiene informe ejecutivo disponible."); return
    ctx = st.session_state.get("dataset_context") or result.get("dataset_context") or {}
    team, f = fr["equipo"], fr["ficha"]
    cp = result.get("coach_identity") or {}
    coach = ctx.get("coach") or "DT no informado en catálogo"
    formation = (cp.get("estructura") or {}).get("dibujo_principal", "—")
    esi = float(result.get("ESI", 0))

    _page_intro(
        f"Informe Ejecutivo · {team}",
        "La lectura táctica principal del equipo en un solo recorrido: qué define su modelo, dónde gana valor y cómo conviene enfrentarlo.",
        [f"DT: {coach}", f"Dibujo base: {formation}", f"ESI {esi:.1f}/100", f"{f['partidos']} partidos"],
        eyebrow="Coach Story",
    )

    # Coach Story en tres líneas: hechos primero, recomendaciones después.
    strengths = fr.get("fortalezas") or []
    weaknesses = fr.get("debilidades") or []
    plan = fr.get("como_jugarle") or []
    setup = (fr.get("textos") or {}).get("entrenador", "")
    conflict = (f"La principal señal favorable es {strengths[0]['titulo'].lower()} ({strengths[0]['dato']}); "
                f"la principal vulnerabilidad observable es {weaknesses[0]['titulo'].lower()} ({weaknesses[0]['dato']}).") if strengths and weaknesses else (fr.get("textos") or {}).get("regularidad", "")
    resolution = plan[0] if plan else "No aparece una vía diferencial suficientemente clara frente a sus rivales en esta muestra."
    _section_lead("Coach Story en 3 líneas", "Setup → conflicto → resolución para leer al equipo en menos de 60 segundos.")
    st.markdown(f"**Setup.** {setup}\n\n**Conflict.** {conflict}\n\n**Resolution.** {resolution}")

    _section_lead("Tres decisiones para el cuerpo técnico", "Fortaleza, vulnerabilidad y plan de partido derivados de la muestra analizada.")
    a,b,c=st.columns(3)
    with a:
        x=strengths[0] if strengths else {"titulo":"Fortaleza no concluyente","dato":"—","rivales":"—"}
        st.success(f"**FORTALEZA PRINCIPAL**\n\n{x['titulo']}\n\n{x['dato']} · rivales: {x['rivales']}")
    with b:
        x=weaknesses[0] if weaknesses else {"titulo":"Sin vulnerabilidad diferencial","dato":"—","rivales":"—"}
        st.error(f"**VULNERABILIDAD CLAVE**\n\n{x['titulo']}\n\n{x['dato']} · rivales: {x['rivales']}")
    with c:
        st.info(f"**PLAN DE PARTIDO · CÓMO JUGARLE**\n\n{resolution}")
    st.caption(f"Evidencia: {len((result.get('evidence') or {}).get('claims', []))} afirmaciones auditables · Confiabilidad visible en la capa de evidencia del modelo.")

    _section_lead("Descargables ejecutivos", "Llévate el resumen táctico en formato de presentación para staff o jurado.")
    one_page = build_executive_pdf(result, ctx)
    full_pdf = _football_pdf_bytes(result)
    safe = team.replace(" ", "_").replace("/", "-")
    d1,d2=st.columns(2)
    with d1:
        st.download_button("Descargar PDF ejecutivo · 1 página", data=one_page, file_name=f"EFOS_Executive_{safe}.pdf", mime="application/pdf", type="primary", use_container_width=True)
    with d2:
        st.download_button("Descargar informe completo para cuerpo técnico", data=full_pdf, file_name=f"EFOS_Informe_{safe}.pdf", mime="application/pdf", use_container_width=True)
    with st.expander("Vista previa · PDF ejecutivo", expanded=False):
        enc=base64.b64encode(one_page).decode("ascii")
        components.html(f'<embed src="data:application/pdf;base64,{enc}#toolbar=1&navpanes=0" type="application/pdf" width="100%" height="880px"/>',height=900,scrolling=True)

def _coach_page(result: dict) -> None:
    cp=result.get("coach_identity") or {}; ctx=st.session_state.get("dataset_context") or result.get("dataset_context") or {}
    if not cp:
        st.info("No hay perfil de modelo de juego para esta muestra."); return
    team=cp.get("equipo",result.get("focal_team","Equipo")); coach=ctx.get("coach") or "DT no informado en catálogo"
    est=cp.get("estructura",{})
    _page_intro(
        f"Modelo de Juego y DT · {team}",
        "Firma táctica, dibujo predominante y reacción contextual del entrenador a lo largo de la muestra.",
        [f"DT: {coach}", f"Dibujo: {est.get('dibujo_principal','—')}", f"{cp.get('partidos',0)} partidos"],
        eyebrow="Identidad táctica",
    )
    if cp.get("aviso"): st.warning(cp["aviso"])

    _section_lead(f"Dibujo base: {est.get('dibujo_principal','—')} y alineaciones del entrenador", "Reconstrucción visual de la estructura utilizada por el cuerpo técnico.")
    _lineup_section(result, _xcache(result), team)

    _section_lead("Firma Táctica del Entrenador (CTS)", "Radar de seis dimensiones para resumir el modelo de juego en escala EFOS 0–100.")
    show(F.fig_cts_radar(result.get("cts") or {}, team))
    st.caption("Escala 0–100 descriptiva del propio motor EFOS. Adaptación = proporción de ventanas de desajuste que vuelven a estabilidad/adaptación en la siguiente ventana observable.")

    _section_lead("Cómo cambia el equipo según el marcador", "Reacción del sistema cuando gana, empata o pierde.")
    if cp.get("por_marcador"):
        show(F.fig_score_reaction(cp["por_marcador"], team))
    else:
        st.info("No hay muestra suficiente por estado de marcador.")

    _section_lead("Similitud técnica en Liga MX", "Comparación únicamente contra perfiles reales calculados con el mismo motor.")
    st.write("La comparación se habilita únicamente con perfiles CTS calculados de otros equipos de la misma liga y con el mismo motor. EFOS **no muestra porcentajes simulados ni arquetipos europeos**.")
    refs=[]
    profiles_dir=BASE_DIR/"data"/"processed"/"league_profiles"
    if profiles_dir.exists():
        import json as _json
        for fp in profiles_dir.glob("*.json"):
            try:
                obj=_json.loads(fp.read_text(encoding="utf-8")); refs.append(obj)
            except Exception: pass
    sim=rank_similarity(team,result.get("cts") or {},refs)
    if len(sim): show(F.fig_similarity_bars(sim,team))
    else: st.info("Aún no hay al menos un segundo perfil Liga MX validado en el repositorio. Al añadir otros equipos, esta gráfica se genera automáticamente.")

def _transitions_page(result: dict) -> None:
    fr=_fr(result); f,r=_pm_means(result); team,events,_,_,_,_,_=_context(result)
    _page_intro("Transiciones", "La respuesta inmediata del equipo tras pérdida y la amenaza que genera cuando recupera y acelera.", ["<5 s tras pérdida", "<15 s tras recuperación"], eyebrow="Cambios de estado")
    if f is None: st.info("Sin datos suficientes."); return
    _section_lead("Transición defensiva · ataque → defensa", "Capacidad de reaccionar en los segundos siguientes a perder la posesión.")
    a,b=st.columns(2)
    with a: _metric_card("Respuesta inmediata <5 s", f"{100*float(result.get('transition_response_rate',0)):.0f}%", "pérdidas con respuesta defensiva en la ventana EFOS")
    with b: _metric_card("Peligro concedido tras pérdida", f"{f['xg_tras_perder']:.2f} xG/partido", f"rivales: {r['xg_tras_perder']:.2f}")

    _section_lead("Transición ofensiva · defensa → ataque", "Qué tan vertical y dañino es el equipo cuando recupera.")
    a,b=st.columns(2)
    with a: _metric_card("Tiros en <15 s tras recuperar", f"{f['tiros_tras_recuperar']:.1f}/partido", f"rivales: {r['tiros_tras_recuperar']:.1f}")
    with b: _metric_card("xG en <15 s tras recuperar", f"{f['xg_tras_recuperar']:.2f}/partido", f"rivales: {r['xg_tras_recuperar']:.2f}")
    c=_xcache(result); tf=c["tf"]
    _section_lead("Acciones en transición sobre el campo", "Vista espacial del comportamiento colectivo e individual en ambos sentidos de transición.")
    st.caption("Transición defensiva: lo que hace el equipo en los 5 s posteriores a perder el balón. "
               "Transición ofensiva: lo que hace en los 15 s posteriores a recuperarlo, dentro de la misma posesión.")
    _action_explorer("tr", c, X.transition_actions(c["e"], team, tf), "Oranges", "Mapa de calor · acciones en transición")
    _section_lead("Valor acumulado en transición", "Cuánto peligro crea o concede el equipo dentro de las ventanas críticas de transición.")
    off=tf["off"]
    _value_explorer("tr_val", c, off[off["obv_total_net"].notna()], off[off["event_type"].eq("Shot")],
                    "Valor en transición ofensiva (OBV)", "xG en transición",
                    "Suma del OBV y del xG de las acciones del equipo en los 15 s posteriores a recuperar el balón. "
                    "La línea roja (un partido, vista colectiva) es el xG que concede el rival en los 15 s posteriores a una pérdida propia.",
                    conceded_df=tf["opp_shots_after_loss"])

def _set_pieces_page(result: dict) -> None:
    fr=_fr(result); f,r=_pm_means(result); team,events,_,_,_,_,_=_context(result)
    _page_intro("Balón Parado", "Comparativo claro entre lo que el equipo genera y concede en saques de esquina y faltas laterales.", ["A favor vs. en contra", "Trayectorias", "Zonas de remate"], eyebrow="Especialidades")
    if f is None: st.info("Sin datos suficientes."); return
    c=_xcache(result)
    a1,a2=st.columns(2)
    with a1: _metric_card("Peligro generado a balón parado", f"{f['xg_abp']:.2f} xG/partido", f"rivales: {r['xg_abp']:.2f}")
    with a2: _metric_card("Peligro concedido a balón parado", f"{f['xg_abp_contra']:.2f} xG/partido", f"rivales: {r['xg_abp_contra']:.2f}")
    side=st.radio("Balón parado", ["A favor", "En contra"], horizontal=True, key="sp_side")
    ck=f"sp_table_{side}"
    if ck not in c: c[ck]=X.set_piece_table(c["e"], team, against=(side=="En contra"))
    sp=c[ck]
    if sp.empty: st.info("No hay acciones a balón parado identificadas."); return
    present=[k for k in X.SET_PIECE_KINDS if k in set(sp["tipo"])]
    f1,f2=st.columns([2,2])
    with f1: kinds=st.multiselect("Tipo de balón parado", present, default=present, key=f"sp_kind_{side}")
    labels=c["labels"]; inv={v:k for k,v in labels.items()}
    with f2: msel=st.multiselect("Partido(s) · vacío = todo el torneo", list(labels.values()), key=f"sp_matches_{side}")
    d=sp[sp["tipo"].isin(kinds)]
    if msel: d=d[d["match_id"].isin([inv[x] for x in msel])]
    g1,g2=st.columns(2)
    execs=["Todos"]+d["ejecutor"].dropna().value_counts().index.tolist()
    with g1: ex=st.selectbox("Ejecutor (quien saca o lanza)", execs, key=f"sp_exec_{side}")
    if ex!="Todos": d=d[d["ejecutor"].eq(ex)]
    rems=["Todos","Solo jugadas con remate"]+d["rematador"].dropna().value_counts().index.tolist()
    with g2: rm=st.selectbox("Rematador", rems, key=f"sp_rem_{side}")
    if rm=="Solo jugadas con remate": d=d[d["rematador"].notna()]
    elif rm!="Todos": d=d[d["rematador"].eq(rm)]
    k1,k2,k3,k4=st.columns(4)
    with k1: _metric_card("Ejecuciones", f"{len(d):,}", ", ".join(kinds) if len(kinds)<=2 else f"{len(kinds)} tipos")
    with k2: _metric_card("Terminan en remate", f"{100*d['rematador'].notna().mean():.0f} %" if len(d) else "—", f"{int(d['rematador'].notna().sum())} remates")
    with k3: _metric_card("Peligro (xG)", f"{d['xg'].fillna(0).sum():.2f}", "suma de los remates")
    with k4: _metric_card("Goles", f"{int(d['gol'].sum())}", "de esas jugadas")
    who=" · ".join(x for x in [ex if ex!="Todos" else "", rm if rm not in ("Todos",) else ""] if x) or team
    col1,col2=st.columns([1.35,1])
    with col1:
        st.pyplot(X.set_piece_pitch(d, f"Balón parado {side.lower()} · trayectorias", who), clear_figure=True, use_container_width=True)
    with col2:
        st.markdown("#### Por tipo")
        if len(d):
            bt=d.groupby("tipo").agg(Ejecuciones=("tipo","size"),Remates=("rematador","count"),xG=("xg","sum"),Goles=("gol","sum")).reset_index().rename(columns={"tipo":"Tipo"})
            st.dataframe(bt.round(2),hide_index=True,use_container_width=True)
            st.markdown("#### Ejecutores")
            st.dataframe(d.groupby("ejecutor").agg(Ejecuciones=("tipo","size"),Remates=("rematador","count"),xG=("xg","sum")).sort_values("Ejecuciones",ascending=False).head(8).round(2).reset_index().rename(columns={"ejecutor":"Ejecutor"}),hide_index=True,use_container_width=True)
    rem=d[d["rematador"].notna()].copy()
    if len(rem):
        st.markdown("#### Remates de estas jugadas")
        rem["Partido"]=rem["match_id"].map(labels); rem["Minuto"]=rem["minuto"].round().astype("Int64")
        st.dataframe(rem[["Partido","Minuto","tipo","ejecutor","receptor","rematador","xg","gol"]].rename(columns={"tipo":"Tipo","ejecutor":"Ejecutor","receptor":"Primer receptor","rematador":"Rematador","xg":"xG","gol":"Gol"}).round(2),
                     hide_index=True,use_container_width=True)
    st.caption("Tipos: «Tiro libre directo» = falta lanzada a portería; «indirecto» = falta frontal (x ≥ 80, carril central) jugada como pase; "
               "«lateral» = falta desde los costados del último tercio; «lejano» = falta en campo rival antes del último tercio (60 ≤ x < 80). "
               "Los datos de eventos no indican si el árbitro la señaló indirecta; la clasificación es por zona y forma de ejecución. "
               "Rematador = primer remate del mismo equipo en la misma posesión en los 10 s siguientes.")
    st.info("Marcaje zonal vs. personal y el primer contacto exacto requieren información espacial 360/tracking o etiquetado de vídeo. EFOS no los infiere desde event data si no están observados.")

def _video_page(result: dict) -> None:
    clips = _fr(result).get("clips")
    st.markdown("# Vídeo: jugadas para revisar")
    st.caption("Los mejores ejemplos de cada rasgo. Cada conclusión del informe debería comprobarse en vídeo.")
    if not isinstance(clips, pd.DataFrame) or clips.empty:
        st.info("No se encontraron jugadas representativas."); return
    kinds = st.multiselect("Rasgos", sorted(clips["rasgo"].unique()), default=sorted(clips["rasgo"].unique()))
    view = clips[clips["rasgo"].isin(kinds)].rename(columns={"tipo": "A favor / en contra", "rasgo": "Rasgo", "rival": "Rival",
        "parte": "Parte", "minuto": "Minuto", "jugador": "Protagonista", "xg": "xG", "que_ver": "Qué observar", "match_id": "ID partido"})
    st.dataframe(view, hide_index=True, use_container_width=True)
    st.caption("Protagonista: quien remata o, en «salida de balón», el jugador propio que pierde el balón.")


def _section_text_page(result: dict, title: str, caption: str, key: str, cards: list) -> None:
    fr = _fr(result); f, r = _pm_means(result)
    st.markdown(f"# {title}"); st.caption(caption)
    if fr: st.write(fr["textos"][key])
    if f is not None and cards:
        cols = st.columns(len(cards))
        for col, (label, k, fmt) in zip(cols, cards):
            with col: _vs_card(label, fmt.format(f[k]), fmt.format(r[k]))


def _identity_page(result: dict) -> None:
    team, _, dims, esi, _, _, _ = _context(result)
    st.markdown("# Identidad del equipo")
    st.caption("Cómo se organiza, resiste y responde el sistema. Las siglas técnicas quedan como segundo nivel.")
    esi_overall = pd.DataFrame([{**dims, "ESI": esi}])
    show(F.fig_esi_dimensions(esi_overall, team))
    for key,val in sorted(dims.items(), key=lambda kv:kv[1], reverse=True):
        label, meaning = HUMAN_DIMS[key]
        c1,c2 = st.columns([1.2,4.8])
        with c1: st.metric(label, f"{float(val):.1f}/100")
        with c2:
            st.markdown(f"**{meaning}**")
            st.caption(f"Código técnico EFOS: {key}")
    with st.expander("Ver metodología del ESI"):
        st.write("ESI integra OC, HPS, RPS, DS y DER con pesos configurables. El objetivo de esta pantalla es traducir la matemática a lenguaje de entrenador sin ocultar el cálculo.")


def _pressure_page(result: dict) -> None:
    team, _, dims, _, _, _, _ = _context(result)
    pm = result.get("pressure_summary", {}); pi = result.get("pressure_imposed_summary", {}); traps = result.get("trap_metrics", {})
    st.markdown("# Presión")
    st.caption("Qué tan restringido está el equipo, qué presión impone al rival y qué ocurre cuando aparecen traps defensivos.")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Estabilidad bajo presión", f"{float(dims['HPS']):.1f}/100")
    c2.metric("Presión sufrida", f"{float(pm.get('mean_pci',0)):.3f}")
    c3.metric("Presión impuesta", f"{float(pi.get('mean_pci',0)):.3f}")
    c4.metric("Traps detectados", f"{int(traps.get('trap_attempts',0)):,}")
    st.info("PCI representa contexto de restricción. HPS representa la respuesta del equipo a ese contexto: estímulo y respuesta se mantienen separados.")
    rows=[]
    labels={"direct_pressure":"Presión directa","nearby_pressure":"Presión cercana","boundary_constraint":"Uso de banda / confinamiento","defensive_responsibility":"Responsabilidad defensiva (DefR)","control_constraint":"Restricción de control","lane_closure":"Cierre de líneas"}
    for k,v in pi.get("components",{}).items():
        if v.get("mean") is not None: rows.append({"Componente":labels.get(k,k),"Media":v.get("mean"),"Cobertura":v.get("coverage")})
    if rows: st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.warning(f"DTE = {float(traps.get('DTE',0)):.1f}% continúa marcado como EXPERIMENTAL hasta calibrar traps contra video o etiquetado humano.")
    tdf=result.get("traps")
    if isinstance(tdf,pd.DataFrame) and len(tdf):
        with st.expander("Ver secuencias clasificadas como traps"):
            st.dataframe(tdf.head(500),hide_index=True,use_container_width=True)


def _on_ball_page(result: dict) -> None:
    team, events, _, _, n_matches, _, _ = _context(result)
    _page_intro("Ataque Organizado", "Cómo construye el equipo, dónde acelera y qué mecanismos utiliza para transformar posesión en ventaja.", [f"{n_matches} partidos", "Construcción", "Progresión", "Valor ofensivo"], eyebrow="Fase con balón")
    fr=_fr(result); f,r=_pm_means(result)
    if f is not None: st.write(fr["textos"]["ataque_organizado"])

    xc=_xcache(result)
    _section_lead("Acciones sobre el campo", "Explora la distribución espacial del ataque a nivel colectivo o por jugador.")
    _action_explorer("atk", xc, X.attack_actions(xc["e"], team), "Blues", "Mapa de calor · acciones de ataque organizado")

    tf=result.get("coach_story",{}).get("tactical_framework",{}); build=tf.get("construction_progression",{}); off=tf.get("offensive_microconcepts",{})
    _section_lead("Mecanismos de progresión", "Señales observables que explican cómo el equipo salta líneas y gana altura.")
    a,b,c,d=st.columns(4)
    with a: _metric_card("Atracción de presión", _pm_text(build.get("pressure_attraction_passes",{}).get("per_match")), "pases completados bajo presión antes de progresar · proxy")
    with b: _metric_card("Liberación posterior", _pct_text(build.get("pressure_release_success",{}).get("rate")), "secuencias que progresan tras atraer presión")
    with c: _metric_card("Medios espacios", _pm_text(build.get("halfspace_entries",{}).get("per_match")), "pases completados a half-space")
    with d: _metric_card("Tercer hombre", _pm_text(build.get("third_man_progression_proxy",{}).get("per_match")), "A→B→C progresivo · proxy")

    _section_lead("Valor ofensivo acumulado", "Lectura combinada del peligro generado (OBV) y la calidad del remate (xG).")
    me=xc["e"][xc["e"]["team"].eq(team)]
    onball=me[me["event_type"].isin(["Pass","Carries","Carry","Dribble","Shot"])&me["obv_total_net"].notna()]
    _value_explorer("atk_val", xc, onball, me[me["event_type"].eq("Shot")], "Valor ofensivo (OBV)", "Goles esperados (xG)",
                    "OBV: suma del cambio en la probabilidad de marcar (menos la de recibir) que producen pases, conducciones, regates y tiros. "
                    "xG: suma de la probabilidad de gol de cada remate. Con un partido se ve minuto a minuto; con varios, por partido y acumulado.")

def _off_ball_page(result: dict) -> None:
    team, events, _, _, _, _, _ = _context(result); fr=_fr(result); f,r=_pm_means(result)
    _page_intro("Defensa Organizada", "Dónde interviene el equipo, cómo presiona y qué tan bien convierte esa energía en recuperación o contención.", ["Altura de intervención", "Counterpress", "Valor defensivo"], eyebrow="Fase sin balón")
    if f is not None: st.write(fr["textos"]["defensa_organizada"])
    tf=result.get("coach_story",{}).get("tactical_framework",{}); d=tf.get("defensive_profile",{}); traps=result.get("trap_metrics",{})
    if d:
        h=d.get("defensive_action_height",{}); a,b,c,dcol=st.columns(4)
        with a: _metric_card("Altura media de intervención", f"x={float(h.get('value') or 0):.1f}/120", "acciones defensivas · no posición exacta de línea")
        with b: _metric_card("Pases rivales bajo presión", _pct_text(d.get("opponent_passes_under_pressure",{}).get("rate")), "proporción observada")
        with c: _metric_card("Presión tras pérdida", _pm_text(d.get("counterpress",{}).get("per_match")), "counterpress StatsBomb · ≤5 s")
        with dcol: _metric_card("Fueras de juego rivales", _pm_text(d.get("opponent_offside_outcomes",{}).get("per_match")), "proxy; no prueba trampa deliberada")
    c=_xcache(result)
    _section_lead("Acciones defensivas sobre el campo", "Mapa de presiones, recuperaciones e intervenciones en fase sin balón.")
    _action_explorer("def", c, X.defence_actions(c["e"], team), "Greens", "Mapa de calor · acciones defensivas")
    _section_lead("Valor defensivo acumulado", "Qué tanto reduce el equipo el peligro rival cuando interviene.")
    me=c["e"][c["e"]["team"].eq(team)]; opp=c["e"][~c["e"]["team"].eq(team)]
    defn=me[me["event_type"].isin(["Pressure","Ball Recovery","Interception","Duel","Block","Clearance","Foul Committed"])&me["obv_total_net"].notna()]
    _value_explorer("def_val", c, defn, opp[opp["event_type"].eq("Shot")].assign(player=None), "Valor defensivo (OBV)", "xG concedido",
                    "OBV defensivo: suma del valor de intercepciones, duelos, bloqueos, despejes y recuperaciones (positivo = reduce el peligro rival). "
                    "xG concedido: probabilidad de gol de los remates del rival en la selección (solo en vista colectiva).")
    _section_lead("Ejecución de trampas defensivas", "Hipótesis EFOS sobre secuencias de confinamiento y recuperación.")
    st.metric("Tasa experimental de ejecución", f"{float(traps.get('DTE',0)):.1f}%", help="DTE sigue siendo una hipótesis experimental hasta validación contra vídeo/etiquetado humano.")
    st.caption(f"Evidencia: {int(traps.get('trap_attempts',0)):,} intentos detectados · Confiabilidad: EXPERIMENTAL.")

def _moments_page(result: dict) -> None:
    team, _, _, _, _, _, _ = _context(result); windows=result.get("match_windows"); states=result.get("dtc_states")
    _page_intro("Momentos del Partido", "La estabilidad del sistema a lo largo del juego y los momentos que más cambian la historia competitiva del equipo.", ["ESI por tramos", "Lectura in situ", "Momentos clave"], eyebrow="Dinámica temporal")
    if not isinstance(windows,pd.DataFrame) or windows.empty:
        st.info("No hay suficientes ventanas temporales."); return
    show(F.fig_esi_timeline(windows,team,window_minutes=15))
    st.markdown("""
<div class='efos-question'><b>¿Qué es el ESI y cómo se interpreta?</b><br>
El Engine Stability Index (0–100) resume qué tan organizada y estable permanece la estructura del equipo durante el partido. En la lectura operativa de este Sprint, <b>ESI ≥70</b> junto con una respuesta defensiva suficiente se considera una ventana estable; valores entre <b>55 y 70</b> suelen reflejar adaptación, y caídas sostenidas por debajo de esos niveles señalan mayor tensión o sufrimiento. Los umbrales son configurables y todavía no son un benchmark universal de liga.
</div>
""",unsafe_allow_html=True)
    view=st.radio("Profundidad",["Resumen de la muestra","Partido por partido"],horizontal=True)
    if view=="Resumen de la muestra":
        if isinstance(states,pd.DataFrame) and len(states):
            dist=states["state"].value_counts(); rows=[{"Momento":DTC_HUMAN.get(k,k),"Ventanas":int(v),"Share":f"{100*v/len(states):.1f}%"} for k,v in dist.items()]
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    else:
        xc=_xcache(result); labels=xc["labels"]
        pick=st.selectbox("Partido",list(labels.values()),key="mom_match")
        selected=str({v:k for k,v in labels.items()}[pick])
        gf,gc=X.match_score(xc["e"],team,selected)
        st.markdown(f"### {html.escape(pick)} · resultado {team} {gf} – {gc}")
        mw=windows[windows["match_id"].astype(str).eq(selected)].sort_values("window_order")
        import plotly.graph_objects as go
        fig=go.Figure(go.Scatter(x=mw["window_order"]*15+7.5,y=mw["ESI"],mode="lines+markers",line=dict(color="#2563EB",width=3),marker=dict(size=9),name="ESI"))
        fig.update_layout(height=300,margin=dict(t=30),paper_bgcolor="white",plot_bgcolor="white",font=dict(family="Inter, Segoe UI, sans-serif",color="#0F172A"),
                          xaxis_title="Minuto",yaxis_title="ESI",title="Estabilidad del equipo por tramos de 15 minutos")
        fig.update_yaxes(range=[0,100],gridcolor="#E2E8F0"); fig.update_xaxes(range=[0,100],gridcolor="#E2E8F0"); show(fig)
        ms=states[states["match_id"].astype(str).eq(selected)].sort_values("window_order") if isinstance(states,pd.DataFrame) and len(states) and "match_id" in states else pd.DataFrame()
        if len(ms):
            st.caption(" · ".join(f"{int(r.get('window_order',0))*15}′ {DTC_HUMAN.get(str(r.get('state')),str(r.get('state')))} (ESI {float(r.get('ESI',0)):.0f})" for _,r in ms.iterrows()))

        st.markdown("### Momentos más importantes del partido")
        for side in ("A favor","En contra"):
            k=f"sp_table_{side}"
            if k not in xc: xc[k]=X.set_piece_table(xc["e"],team,against=(side=="En contra"))
        km=X.key_moments(xc["e"],team,selected,xc["tf"],xc["sp_table_A favor"],xc["sp_table_En contra"])
        if km.empty:
            st.info("No se identificaron momentos destacados en este partido."); return
        # Línea de tiempo: fase × minuto; tamaño = xG, estrella = gol
        fig=go.Figure()
        for side,col,sym in (("A favor","#2563EB","circle"),("En contra","#B91C1C","diamond")):
            d=km[km["lado"].eq(side)]
            if d.empty: continue
            fig.add_trace(go.Scatter(x=d["minuto"],y=d["fase"].astype(str),mode="markers",name=side,
                marker=dict(color=col,size=(12+40*d["xg"].fillna(0).clip(0,.8)).tolist(),
                            symbol=["star" if g else sym for g in d["gol"]],line=dict(color="white",width=1)),
                customdata=d["momento"],hovertemplate="%{x:.0f}′ · %{customdata}<extra></extra>"))
        fig.update_layout(height=330,paper_bgcolor="white",plot_bgcolor="white",title="Línea de tiempo · tamaño = xG, estrella = gol",
                          font=dict(family="Inter, Segoe UI, sans-serif",color="#0F172A"),legend=dict(orientation="h",y=-0.2),margin=dict(l=10,t=40))
        fig.update_xaxes(range=[0,100],title="Minuto",gridcolor="#E2E8F0")
        fig.update_yaxes(categoryorder="array",categoryarray=list(reversed(X.PHASES)),gridcolor="#E2E8F0")
        show(fig)
        for phase in X.PHASES:
            d=km[km["fase"].astype(str).eq(phase)]
            st.markdown(f"#### {phase}")
            if d.empty:
                st.caption("Sin momentos destacados en esta fase."); continue
            a,b=st.columns(2)
            for col,side in ((a,"A favor"),(b,"En contra")):
                with col:
                    st.markdown(f"**{side}**")
                    ds=d[d["lado"].eq(side)]
                    if ds.empty: st.caption("—")
                    for _,r in ds.iterrows():
                        line=f"**{X._mm(r['minuto'])}** · {r['momento']}"
                        (st.success if (r["gol"] and side=="A favor") else st.error if (r["gol"]) else st.markdown)(line)
        st.caption("Selección automática: por fase y lado se muestran hasta 3 momentos, priorizando goles, después la calidad de la ocasión (xG) "
                   "y el valor de la acción (OBV). Transición = 15 s tras recuperar o perder el balón; balón parado = jugadas con remate. "
                   "Úsalos como guía para el vídeo del partido.")

def _players_page(result: dict) -> None:
    team, _, _, _, _, _, _ = _context(result)
    st.markdown("# Jugadores")
    st.caption("El once tal como juega y quién participa más en el ataque.")
    pos = _fr(result).get("posiciones")
    if isinstance(pos, pd.DataFrame) and len(pos) and pos[["x", "y"]].notna().all(axis=1).sum() >= 5:
        pos = pos.assign(etiqueta=pos["player"].map(_shirt_name), posicion_es=pos["posicion"].map(lambda p: POSITION_ES.get(p, p)))
        show(F.fig_average_positions(pos, team))
    st.markdown("### Participación en el último tercio")
    lap=result.get("lap")
    if isinstance(lap,pd.DataFrame) and len(lap):
        max_actions=max(20,int(lap.get("final_third_actions",pd.Series([20])).max()))
        min_n=st.slider("Mínimo de acciones en último tercio",1,max_actions,min(100,max_actions))
        eligible=lap[lap["final_third_actions"]>=min_n]
        if len(eligible): show(F.fig_lap(lap,team,min_actions=min_n))
        else: st.info("No hay jugadores que superen el mínimo seleccionado.")
        with st.expander("Tabla completa"): st.dataframe(lap,hide_index=True,use_container_width=True)
    else: st.info("No hay suficiente información individual en los archivos cargados.")


def _evidence_page(result: dict) -> None:
    st.markdown("# Evidencia")
    st.caption("Cada conclusión debe poder recorrerse hacia atrás: Coach Story → interpretación → métrica → evento → dato original.")
    ev=result.get("evidence",{})
    claims=ev.get("claims",[]) if isinstance(ev,dict) else []
    if claims:
        rows=[]
        for c in claims:
            rows.append({"Claim":c.get("claim") or c.get("id"),"Fuente":c.get("source"),"n":c.get("n"),"Confianza":c.get("confidence"),"Limitación":c.get("limitation")})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    else: st.info("No hay claims auditables disponibles.")
    with st.expander("Ver principios candidatos"):
        p=result.get("principles")
        if isinstance(p,pd.DataFrame): st.dataframe(p,hide_index=True,use_container_width=True)


def _method_page(result: dict) -> None:
    team, events, _, _, n_matches, n_team_events, _ = _context(result)
    meta=result.get("coach_story",{}).get("analysis_metadata",{})
    input_meta=result.get("input_metadata",{})
    st.markdown("# Método")
    st.caption("Capa técnica para jurado, analistas y auditoría del modelo.")
    st.markdown(f"""
**Equipo focal:** {team}  
**Selección del equipo:** `{result.get('team_resolution',{}).get('mode')}`  
**Archivos consolidados:** {int(input_meta.get('n_files_loaded',1))}  
**Formato(s):** `{', '.join(input_meta.get('source_formats',[input_meta.get('format','CSV')]))}`  
**Partidos analizados:** {n_matches}  
**Eventos del equipo:** {n_team_events:,}  
**Eventos totales:** {len(events):,}  
**Duplicados eliminados al consolidar:** {int(input_meta.get('duplicates_removed',0))}  
**Frames 360:** {int(result.get('frames360_loaded',0))}  
**Perfil de fórmulas:** `{meta.get('formula_profile','EFOS_v0.4.4_CoachStory_TacticalFramework')}`
""")
    st.warning("Los pesos, umbrales y DTE siguen siendo hipótesis del modelo en desarrollo. Fishing, tercer hombre, Aliup, intervalos y offside-trap se reportan como proxies cuando el event data no observa directamente la intención o el movimiento requerido.")
    st.markdown("### Glosario: de EFOS al vestuario")
    st.dataframe(pd.DataFrame([{"En EFOS": k, "En el vestuario": v[0], "Qué significa": v[1]} for k, v in GLOSSARY.items()]),
                 hide_index=True, use_container_width=True)


def _technical_page(result: dict) -> None:
    st.caption("Capa técnica de EFOS para analistas y jurado: el Coach Story original, el índice de regularidad y el modelo de presión.")
    view = st.radio("Vista técnica", ["Coach Story EFOS", "Regularidad del juego", "Presión"], horizontal=True)
    if view == "Coach Story EFOS": _coach_story_page(result)
    elif view == "Regularidad del juego": _identity_page(result)
    else: _pressure_page(result)


def _render_active_page(result: dict) -> None:
    page=st.session_state["nav"]
    if page=="Selección de Equipo": _selection_panel()
    elif page=="★ Informe Ejecutivo": _report_page(result)
    elif page=="Modelo de Juego y DT": _coach_page(result)
    elif page=="Ataque Organizado": _on_ball_page(result)
    elif page=="Defensa Organizada": _off_ball_page(result)
    elif page=="Transiciones": _transitions_page(result)
    elif page=="Balón Parado": _set_pieces_page(result)
    elif page=="Momentos del Partido": _moments_page(result)


_init_state()
if not st.session_state["authenticated"]:
    _login_page(); st.stop()

_header()
if st.session_state.get("analysis") is None:
    _selection_panel()
else:
    _render_active_page(st.session_state["analysis"])
