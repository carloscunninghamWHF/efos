"""EFOS v0.4.7 — authenticated, repository-first, football-native Streamlit portal.

Run from efos/:
    python -m streamlit run visualization/efos_dashboard.py

Flow:
    Login -> Liga -> Temporada -> Equipo -> Periodo -> EFOS -> Informe Ejecutivo.
"""
from __future__ import annotations

import hashlib
import time
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
import set_piece_story_maps as SPM  # noqa: E402
import set_piece_story_3d as SP3  # noqa: E402
import defense_story_maps as DSM  # noqa: E402
import smart_defense_maps as SDM  # noqa: E402
from defensive_open_play_app import render_defensive_module  # noqa: E402
from intelligence.smart_defense_tactics import (SITUATIONS, MOMENTS, summarize_smart_defense)  # noqa: E402
from intelligence.set_piece_patterns import (  # noqa: E402
    KINDS, SCOPE, FLANKS, narrative_findings, context_finding, summarize_sample, premium_story_profile
)
from coach_story.coach_profile import _starters, _formation  # noqa: E402
from coach_story.report_generator import render_coach_story_md  # noqa: E402
from coach_story.pdf_report import build_coach_story_pdf  # noqa: E402
from coach_story.football_pdf import build_football_pdf, _shirt_name  # noqa: E402
from coach_story.executive_pdf import build_executive_pdf  # noqa: E402
from coach_story.football_report import GLOSSARY, POSITION_ES, DTC_FOOTBALL  # noqa: E402
from coach_story.executive_narrative import build_executive_chapters  # noqa: E402
from coach_story.executive_brief import build_executive_brief  # noqa: E402
from ingestion.input_adapter import load_event_csvs  # noqa: E402
from intelligence.team_scope import team_coverage  # noqa: E402
from run_sprint4 import run as run_sprint4  # noqa: E402
from ui.data_catalog import scan_catalog, period_options, paths_for_selection, context_for_selection  # noqa: E402
from ui.upload import persist_csv_bytes  # noqa: E402
from ui import supabase_bridge as SB  # noqa: E402
from ui.cloud_auth_config import require_cloud_config  # noqa: E402
from ui.analysis_identity import signature as analysis_signature, scope_key  # noqa: E402
from ui.auto_csv import inspect_uploaded_paths, match_labels  # noqa: E402
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
  background:linear-gradient(125deg,#111719 0%,#1B2326 90%); color:#F3F1EC;
  border:1px solid rgba(202,165,105,.19); border-radius:14px;
  padding:14px 18px; min-height:78px; box-shadow:0 10px 28px rgba(14,19,21,.12);
  margin-bottom:10px;
}
.efos-topbar .efos-logo-text {color:#F3F1EC;}
.efos-topbar .efos-logo-circle.c1,.efos-topbar .efos-logo-circle.c2 {background:rgba(255,255,255,.18);}
.efos-topbar .efos-logo-circle.c3,.efos-topbar .efos-logo-circle.c4 {background:rgba(255,255,255,.28);}
.efos-topbar .efos-context-title,.efos-topbar .efos-brand-sub {color:#D2AE75;}
.efos-topbar .efos-files {color:#F1F0EC;}
.efos-topbar .efos-user-chip {color:#F1F0EC;background:rgba(255,255,255,.08);}
[class*='st-key-efos_primary_nav'] div[role='radiogroup'] {
  background:#172024; border:1px solid #273438; padding:7px;
  box-shadow:0 6px 20px rgba(16,23,27,.09);
}
[class*='st-key-efos_primary_nav'] div[role='radiogroup'] label {color:#C3CECF;}
[class*='st-key-efos_primary_nav'] div[role='radiogroup'] label p {color:#C3CECF;}
[class*='st-key-efos_primary_nav'] div[role='radiogroup'] label:has(input:checked) {
  background:#C9A46A!important;color:#0C1213!important;
}
[class*='st-key-efos_primary_nav'] div[role='radiogroup'] label:has(input:checked) p {color:#0C1213!important;font-weight:750;}
@media (max-width:850px){
  .efos-topbar {min-height:0;padding:11px 13px;}
  [class*='st-key-efos_primary_nav'] div[role='radiogroup'] {flex-wrap:wrap;}
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


/* Set Piece Story Premium — reads as an editorial report, not a metric grid. */
.efos-sp-hero {background:linear-gradient(110deg,#0F1A2A,#18263D 78%,#3D3324);
  border:1px solid rgba(201,166,96,.24);border-radius:22px;padding:27px 31px 25px;
  color:#FFFFFF;margin:10px 0 17px;box-shadow:0 14px 36px rgba(15,23,42,.1);}
.efos-sp-hero .sp-kicker {font-size:.7rem;letter-spacing:.14em;font-weight:750;color:#E4BE6B;text-transform:uppercase;}
.efos-sp-hero .sp-title {font-weight:790;letter-spacing:-.035em;font-size:1.55rem;line-height:1.23;margin:10px 0;}
.efos-sp-hero .sp-intro {font-size:.96rem;line-height:1.65;color:#E2E7EE;max-width:67rem;}
.efos-sp-hero .sp-meta {display:flex;flex-wrap:wrap;gap:9px;margin-top:16px;}
.efos-sp-hero .sp-meta span {border:1px solid rgba(255,255,255,.15);border-radius:9px;
 padding:6px 10px;color:#F3E9D6;font-size:.77rem;background:rgba(255,255,255,.065);}
.efos-sp-pattern {background:#FFFFFF;border:1px solid rgba(15,23,42,.085);
 border-radius:17px;padding:20px 22px 18px;min-height:140px;box-shadow:0 4px 18px rgba(15,23,42,.045);}
.efos-sp-pattern.sp-gold {border-top:3px solid #C89B3C;}
.efos-sp-pattern.sp-blue {border-top:3px solid #426B98;}
.efos-sp-pattern .sp-eyebrow {text-transform:uppercase;font-size:.7rem;font-weight:800;letter-spacing:.08em;color:#758294;}
.efos-sp-pattern .sp-value {font-size:1.16rem;font-weight:760;letter-spacing:-.03em;color:#0B1220;margin:8px 0 7px;}
.efos-sp-pattern .sp-details {font-size:.86rem;line-height:1.6;color:#566478;}
.efos-sp-side {background:#F9FAFC;border:1px solid rgba(15,23,42,.07);border-radius:13px;
 padding:11px 16px;line-height:1.48;color:#536175;font-size:.84rem;margin:7px 0 17px;}
.efos-sp-side strong {color:#152238;}
.efos-sp-sequence {border:1px solid rgba(200,155,60,.30);background:linear-gradient(125deg,#FCF9F1,#FFFFFF);
 border-radius:16px;padding:18px 22px;margin:17px 0 19px;}
.efos-sp-sequence .sp-path {font-size:1rem;font-weight:690;color:#202B3D;line-height:1.8;}
.efos-sp-sequence .sp-sub {color:#718096;font-size:.8rem;margin-top:5px;line-height:1.5;}


/* EFOS v0.4.21: executive story before metrics, evidence immediately after. */
.efos-executive-lede {background:linear-gradient(115deg,#0D1829 0%,#17283D 76%,#4C3A22 140%);
  border-radius:21px;padding:26px 30px;margin:8px 0 17px;color:#F7F8FB;
  box-shadow:0 11px 32px rgba(15,23,42,.12);}
.efos-executive-lede .eyebrow {font-size:.71rem;letter-spacing:.15em;color:#E7BE69;font-weight:750;}
.efos-executive-lede .main {font-size:1.13rem;line-height:1.67;color:#F7F8FB;margin:12px 0 10px;max-width:74rem;}
.efos-executive-lede .question {color:#D0DAE5;font-size:.9rem;line-height:1.58;margin:0;}
.efos-exec-card {background:rgba(255,255,255,.89);border:1px solid rgba(15,23,42,.11);
  border-radius:17px;padding:18px 20px;min-height:212px;box-shadow:0 4px 16px rgba(15,23,42,.038);}
.efos-exec-card .kicker {font-size:.72rem;color:#8A6A21;letter-spacing:.1em;font-weight:800;}
.efos-exec-card .name {font-size:.96rem;color:#17243A;font-weight:760;margin-top:8px;line-height:1.3;}
.efos-exec-card .value {font-size:1.85rem;font-weight:800;color:#101B2B;line-height:1.3;margin:8px 0 2px;}
.efos-exec-card .note {font-size:.81rem;color:#5E6B7B;line-height:1.5;}
.efos-exec-card .quality {font-size:.73rem;color:#866324;margin-top:9px;font-weight:680;}
.efos-exec-note {border-left:3px solid #C89B3C;background:rgba(255,250,239,.72);
  padding:14px 18px;border-radius:0 12px 12px 0;margin:6px 0 18px;line-height:1.6;
  color:#324054;font-size:.94rem;}
@media(max-width:800px){.efos-executive-lede{padding:20px}.efos-exec-card{min-height:auto;padding:16px}}
/* v0.4.31 — anchored navigation: menu remains available while scrolling. */
[class*="st-key-efos_sticky_header"] {
  position: sticky !important;
  top: 0 !important;
  z-index: 950 !important;
  background: rgba(247,248,249,.97);
  border: 1px solid rgba(15,23,42,.09);
  border-radius: 15px;
  padding: 8px 11px 12px;
  box-shadow: 0 6px 24px rgba(15,23,42,.09);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
[class*="st-key-efos_sticky_header"] [data-testid="stVerticalBlock"] {gap:.42rem;}
[class*="st-key-efos_sticky_header"] .efos-topbar {min-height:58px; padding:9px 13px;margin-bottom:0;}
[class*="st-key-efos_sticky_header"] [class*="st-key-efos_primary_nav"] div[role="radiogroup"] {
  overflow-x: auto;flex-wrap: nowrap !important;scrollbar-width:thin;
}
[class*="st-key-efos_sticky_header"] [class*="st-key-efos_primary_nav"] label {white-space:nowrap; flex-shrink:0;}
/* Question menus stay underneath the global menu, with local context. */
[class*="st-key-efos_sticky_questions"] {
  position: sticky !important;
  top: 188px;
  z-index: 910 !important;
  background: rgba(249,250,251,.98);
  border:1px solid rgba(15,23,42,.10);
  border-radius:12px;
  padding:7px 11px;
  box-shadow:0 4px 14px rgba(15,23,42,.065);
  backdrop-filter:blur(16px);
}
[class*="st-key-efos_sticky_questions"] [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
.efos-line-divider {height:1px;background:linear-gradient(90deg,transparent,rgba(15,23,42,.16),transparent);margin:24px 0;}
.efos-global-footer {border-top:1px solid rgba(15,23,42,.14);margin:34px 0 6px;
  padding:18px 0 6px;display:flex;align-items:center;justify-content:space-between;gap:12px;
  flex-wrap:wrap;color:#64748b;font-size:.74rem;letter-spacing:.012em;}
.efos-global-footer b {color:#876A38;letter-spacing:.14em;font-size:.72rem;}
.stApp:has(.efos-login-hook) .efos-global-footer {border-color:#404449;color:#AAB2B4;}
.stApp:has(.efos-login-hook) .efos-global-footer b {color:#D3AE72;}
@media (max-width:760px) {
  [class*="st-key-efos_sticky_header"] {top:0;padding:4px 6px 8px;}
  [class*="st-key-efos_sticky_header"] .efos-topbar{min-height:45px;padding:7px 9px;}
  [class*="st-key-efos_sticky_questions"] {top:226px;}
  [class*="st-key-efos_sticky_header"] .efos-logo-text.compact{font-size:1rem;}
}
</style>
"""
st.markdown(ENTERPRISE_CSS, unsafe_allow_html=True)

NAV_ITEMS = ["Equipo y datos", "★ Informe Ejecutivo", "Modelo de Juego", "Con balón", "Sin balón", "Balón parado"]
# The old labels Cómo ataca and Cómo defiende have been consolidated into the new menu.
# Old deep links
NAV_ALIASES = {
    "Selección de Equipo":"Equipo y datos", "Modelo de Juego y DT":"Modelo de Juego",
    "Cómo ataca":"Con balón", "Ataque Organizado":"Con balón", "Cómo defiende":"Sin balón",
    "Defensa Organizada":"Sin balón", "Transiciones":"Sin balón",
    "Balón Parado":"Balón parado", "Momentos del Partido":"★ Informe Ejecutivo",
}
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


def _footer() -> None:
    year = time.localtime().tm_year
    st.markdown(
        f'<div class="efos-global-footer"><span><b>EFOS.</b> &nbsp; Emerging Football Operating System</span>'
        f'<span>© {year} EFOS · Todos los derechos reservados. · Datos sujetos a permisos de uso.</span></div>',
        unsafe_allow_html=True,
    )


def _divider() -> None:
    st.markdown('<div class="efos-line-divider" aria-hidden="true"></div>', unsafe_allow_html=True)


def _init_state() -> None:
    defaults = {
        "authenticated": False, "username": None, "role": None,
        "analysis": None, "analysis_digest": None,
        "upload_names": [], "upload_paths": [],
        "ambiguous_upload_paths": [], "ambiguous_upload_digest": None,
        "ambiguous_upload_names": [], "ambiguous_teams": [],
        "dataset_context": None,
        "supabase_session": None, "supabase_user_id": None,
        "nav": "Equipo y datos",
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
        st.session_state["nav"] = "Equipo y datos"


def _logout() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# EFOS Access: project reference / efos_login_preview.html — dark, responsive,
# six-node relational identity. Scoped selectors do not affect the workspace.
_ACCESS_CSS = """
<style>
.stApp:has(.efos-login-hook){background:#080A0C!important;color:#F3F2EE!important;}
.stApp:has(.efos-login-hook) .block-container{max-width:1260px;padding:clamp(16px,5vh,55px) 24px 30px;}
.efos-login-hook{display:block;height:0;overflow:hidden;}
.efos-access-graphic{min-height:620px;position:relative;overflow:hidden;border-radius:22px;
  padding:34px 40px;display:flex;flex-direction:column;justify-content:space-between;
  background:radial-gradient(circle at 60% 40%,rgba(197,162,100,.09),transparent 46%),#101315;
  border:1px solid #363632;}
.efos-access-graphic:after{content:"";position:absolute;inset:0;pointer-events:none;opacity:.25;
  background:repeating-linear-gradient(100deg,transparent 0,transparent 55px,#4A4E4B 56px,#4A4E4B 57px,transparent 58px);}
.efos-access-brand{color:#F5F2EC;font-size:1.23rem;letter-spacing:.13em;font-weight:700;position:relative;z-index:1;}
.efos-access-glyph{width:min(260px,75%);margin:35px auto;display:block;position:relative;z-index:1;}
.efos-access-lefttitle{color:#F5F2EC;font-size:clamp(1.55rem,2.6vw,2.75rem);line-height:1.15;letter-spacing:-.045em;position:relative;z-index:1;}
.efos-access-lefttitle em{font-style:normal;color:#A9ADAE;}
.efos-access-lefttext{font-size:.95rem;color:#B9C0BE;line-height:1.7;margin-top:14px;position:relative;z-index:1;}
.efos-access-stages{color:#C4A36B;letter-spacing:.11em;font-size:.68rem;margin-top:28px;position:relative;z-index:1;}
.efos-access-panel{min-height:250px;border-radius:22px;background:linear-gradient(145deg,#1B1F22,#121518);
  border:1px solid #333638;padding:45px 40px 12px;}
.efos-access-mini{color:#D7B478;font-size:.7rem;letter-spacing:.17em;font-weight:700;}
.stApp:has(.efos-login-hook) [data-testid="stColumn"]:has(.efos-access-panel){background:#171A1C;border:1px solid #373A3C;border-radius:22px;padding:12px 22px;}
.efos-access-heading{color:#F7F5F0;font-size:clamp(2.2rem,3vw,3.5rem);margin:55px 0 15px;line-height:1.05;letter-spacing:-.04em;}
.efos-access-body{color:#ADB5B5;font-size:.96rem;line-height:1.7;}
.stApp:has(.efos-login-hook) [data-testid=stForm]{background:transparent!important;border:0!important;box-shadow:none!important;
 padding:10px 0!important;backdrop-filter:none!important;}
.stApp:has(.efos-login-hook) [data-testid=stTextInput] label p{color:#D2D5D4!important;}
.stApp:has(.efos-login-hook) input{background:#272C2E!important;border-radius:8px!important;
 color:white!important;caret-color:#D7B478!important;}
.stApp:has(.efos-login-hook) [data-testid=stFormSubmitButton] button{background:#F1EDE5!important;
 color:#111515!important;border:0!important;min-height:51px;font-weight:730!important;}
.stApp:has(.efos-login-hook) [data-testid=stFormSubmitButton] button:hover{background:#D7B478!important;}
.stApp:has(.efos-login-hook) .stCaption, .stApp:has(.efos-login-hook) .stCaption p{color:#9DA6A6!important;}
@media(max-width:800px){.efos-access-graphic{min-height:335px;padding:20px 24px;}.efos-access-glyph{width:100px;margin:7px auto;}
.efos-access-panel{min-height:auto;padding:18px 24px 5px;}.efos-access-heading{margin:12px 0;}.efos-access-stages{margin-top:8px;}}
</style>
"""


def _cloud_config():
    """Require Supabase Auth (fail closed). Resolve secrets from project root.

    Never silently fall back to legacy auth/users.txt when the current working
    directory differs from the directory of the Streamlit application.
    """
    return require_cloud_config(BASE_DIR, st.secrets)


def _cloud_token() -> str:
    cfg = _cloud_config()
    if cfg is None:
        raise SB.CloudError('Supabase no está configurado.')
    session = st.session_state.get('supabase_session')
    if not isinstance(session, dict):
        raise SB.CloudError('Inicia sesión con Supabase Auth.')
    session = SB.refresh(cfg, session)
    st.session_state['supabase_session'] = session
    return session['access_token']


def _login_page() -> None:
    st.markdown(_ACCESS_CSS,unsafe_allow_html=True)
    st.markdown('<span class="efos-login-hook" aria-hidden="true"></span>',unsafe_allow_html=True)
    left,right=st.columns([1.12,0.88],gap='small')
    with left:
        st.markdown("""
<div class="efos-access-graphic">
  <div class="efos-access-brand">EFOS<span style="color:#C6A26A">.</span></div>
  <svg class="efos-access-glyph" viewBox="0 0 280 280" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Seis nodos conectados">
    <path d="M67 61V219M67 61H211M67 140H182M67 219H211" stroke="#F2F0EB" stroke-width="3"/>
    <path d="M67 61L182 140L211 219M211 61L182 140L67 219" stroke="#9FA6A5" stroke-opacity=".43"/>
    <path d="M67 61L211 219" stroke="#C5A266" stroke-dasharray="5 8" stroke-opacity=".6"/>
    <circle cx="67" cy="61" r="6" fill="#F2F0EB"/><circle cx="211" cy="61" r="6" fill="#F2F0EB"/>
    <circle cx="67" cy="140" r="6" fill="#F2F0EB"/><circle cx="182" cy="140" r="8" fill="#C5A266"/>
    <circle cx="67" cy="219" r="6" fill="#F2F0EB"/><circle cx="211" cy="219" r="6" fill="#F2F0EB"/>
  </svg>
  <div><div class="efos-access-lefttitle">Cada acción importa.<br><em>La relación lo explica.</em></div>
  <div class="efos-access-lefttext">Inteligencia táctica que conecta comportamientos, rivales y momentos con evidencia verificable.</div>
  <div class="efos-access-stages">OBSERVAR  ·  INTERPRETAR  ·  DECIDIR</div></div>
</div>
""",unsafe_allow_html=True)
    with right:
        st.markdown("""<div class="efos-access-panel"><div class="efos-access-mini">EMERGING FOOTBALL OPERATING SYSTEM</div>
            <div class="efos-access-heading">Acceso a<br>EFOS.</div>
            <p class="efos-access-body">Una visión conectada del juego, desde cada acción hasta el comportamiento colectivo.</p>
            </div>""",unsafe_allow_html=True)
        try:
            cfg = _cloud_config()
        except SB.CloudError as exc:
            st.error(f'Configuración de Supabase incompleta: {exc}')
            st.stop()
        with st.form('login_form',clear_on_submit=False):
            username=st.text_input('Correo electrónico',placeholder='Correo de Supabase Auth')
            password=st.text_input('Contraseña',type='password',placeholder='••••••••')
            submitted=st.form_submit_button('Entrar a EFOS  →',use_container_width=True,type='primary')
        if submitted:
            try:
                session=SB.sign_in(cfg,username,password)
                # Verificar que la cuenta tiene acceso al catálogo protegido por RLS.
                SB.catalog(cfg,session['access_token'])
            except SB.CloudError as exc:
                st.error(str(exc));return
            st.session_state['supabase_session']=session
            st.session_state['supabase_user_id']=session['user']['id']
            st.session_state['username']=str(session['user'].get('email') or username)
            st.session_state['role']='authenticated'

            st.session_state['authenticated']=True
            _clear_analysis()
            st.rerun()

def _safe_output_dir(username: str, digest: str) -> Path:
    token = hashlib.sha256(username.encode("utf-8")).hexdigest()[:10]
    return RUNTIME_DIR / "outputs" / token / digest[:16]


def _digest_many(digests: list[str]) -> str:
    payload = "|".join(sorted(digests)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _analysis_progress():
    """Steps reflect milestones, not synthetic percentages of the engine runtime."""
    text = st.empty()
    bar = st.progress(0, text='Esperando validación de datos…')
    return bar, text


def _analyze_with_progress(paths, digest, names, focal_team, match_ids=None, *, caption=''):
    bar, status = _analysis_progress()
    try:
        bar.progress(20, text='1/3 · Validando los archivos y la muestra seleccionada')
        status.caption(caption or 'EFOS está comprobando la muestra.')
        for path in paths:
            if not Path(path).is_file():
                raise FileNotFoundError('No está disponible uno de los archivos de origen.')
        if not paths:
            raise ValueError('Selecciona al menos un archivo.')
        bar.progress(55, text='2/3 · Procesando eventos y reconstruyendo el diagnóstico')
        with st.spinner('EFOS está ejecutando sus motores. El tiempo depende del número de partidos…'):
            _analyze_paths(paths, digest, names, focal_team=focal_team, match_ids=match_ids)
        bar.progress(100, text='3/3 · Análisis disponible')
        status.empty()
    except Exception:
        bar.empty()
        status.empty()
        raise


def _analyze_paths(paths: list[Path], digest: str, names: list[str], focal_team: str = "auto", match_ids=None) -> None:
    outdir = _safe_output_dir(str(st.session_state["username"]), digest)
    result = run_sprint4(paths, focal_team=focal_team, outdir=outdir, match_ids=match_ids)
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


def _nav_changed() -> None:
    st.session_state['nav']=st.session_state['efos_primary_nav']


def _header() -> None:
    with st.container(key="efos_sticky_header"):
        _header_body()


def _header_body() -> None:
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
    active_options = NAV_ITEMS if st.session_state.get("analysis") is not None else ["Equipo y datos"]
    st.session_state["nav"] = NAV_ALIASES.get(st.session_state.get("nav"), st.session_state.get("nav"))
    if st.session_state.get("nav") not in active_options:
        st.session_state["nav"] = active_options[0]
    # Separate widget state from the destination so cross-module buttons may
    # navigate without mutating an already-instantiated Streamlit widget.
    if st.session_state.get('efos_primary_nav') != st.session_state['nav']:
        st.session_state['efos_primary_nav']=st.session_state['nav']
    st.radio('Navegación',active_options,horizontal=True,label_visibility='collapsed',
             key='efos_primary_nav',on_change=_nav_changed)
    if st.session_state.get("analysis") is not None and st.session_state["nav"] != "Equipo y datos":
        _global_context_controls(st.session_state["analysis"])

def _current_scope_matches(result: dict):
    """None = complete sample. A list = exact match IDs from shared header."""
    events=result.get('events')
    if not isinstance(events,pd.DataFrame) or not {'match_id','team'}.issubset(events.columns):
        return None
    team=result.get('focal_team')
    possible=set(events.loc[events.team.eq(team),'match_id'].dropna().astype(str))
    wanted=st.session_state.get('efos_global_match','Todos los partidos')
    opponent=st.session_state.get('efos_global_opponent','Todos los rivales')
    pool=events[events.team.ne(team)&events.match_id.astype(str).isin(possible)]
    if opponent!='Todos los rivales':
        allowed=set(pool.loc[pool.team.eq(opponent),'match_id'].astype(str))
        possible &= allowed
    if wanted!='Todos los partidos':
        return [wanted] if wanted in possible else []
    return sorted(possible) if opponent!='Todos los rivales' else None


def _global_context_controls(result: dict) -> None:
    events=result.get('events');team=result.get('focal_team')
    if not isinstance(events,pd.DataFrame) or not {'team','match_id'}.issubset(events.columns):
        return
    from intelligence.offensive_story import readable_match_labels
    own=set(events.loc[events.team.eq(team),'match_id'].dropna().astype(str))
    pool=events[events.match_id.astype(str).isin(own)&events.team.ne(team)]
    opponents=['Todos los rivales']+sorted(pool.team.dropna().astype(str).unique().tolist())
    left,right=st.columns([1,1.7],gap='small')
    with left:
        if st.session_state.get('efos_global_opponent') not in opponents:
            st.session_state['efos_global_opponent']='Todos los rivales'
        selected=st.selectbox('Rival · contexto global',opponents,key='efos_global_opponent')
    mids=sorted(set(pool.loc[pool.team.eq(selected),'match_id'].astype(str))) if selected!='Todos los rivales' else sorted(own)
    labels=readable_match_labels(events,team,mids)
    choices=['Todos los partidos']+mids
    with right:
        if st.session_state.get('efos_global_match') not in choices:
            st.session_state['efos_global_match']='Todos los partidos'
        st.selectbox('Partido · contexto global',choices,key='efos_global_match',
            format_func=lambda mid: mid if mid=='Todos los partidos' else labels.get(mid,f'Partido {mid}'))
    if selected!='Todos los rivales' or st.session_state.get('efos_global_match')!='Todos los partidos':
        st.caption('Selección compartida entre diagnóstico, Ataque, Defensa y comparaciones. Los indicadores históricos de CTS se identifican como temporada completa.')


def _scoped_result(result: dict):
    """Rebuild observations from the selected events; no stale season-wide stories."""
    ids=_current_scope_matches(result)
    if ids is None:
        return result
    signature=(st.session_state.get('analysis_digest'),tuple(ids),id(result))
    existing=st.session_state.get('efos_scoped_cache')
    if isinstance(existing,tuple) and len(existing)==2 and existing[0]==signature:
        return existing[1]
    from visualization.connected_diagnosis import choose_events
    events=choose_events(result.get('events'),ids)
    derived=dict(result)
    derived['events']=events
    derived['organized_attack_data']=None
    derived['offensive_story']=None
    derived['defensive_open_play_possessions']=pd.DataFrame()
    derived['defensive_open_play_events']=pd.DataFrame()
    derived['tactical_reasoning']=None
    derived['transition_response_rate']=None   # not recomputed for this subset
    derived['transition_change_count']=None
    # Keep transition observations on precisely the same global match sample.
    transitions=result.get('transitions')
    if isinstance(transitions,pd.DataFrame) and 'match_id' in transitions:
        derived['transitions']=transitions.loc[transitions.match_id.astype(str).isin(set(map(str,ids)))].copy()
    else:
        derived['transitions']=pd.DataFrame()
    if events.empty:
        st.session_state['efos_scoped_cache']=(signature,derived)
        return derived
    try:
        from intelligence.organized_attack import prepare_attack, possession_table
        from intelligence.offensive_story import build_offensive_story
        d=prepare_attack(events,derived['focal_team'])
        t=possession_table(d)
        derived['organized_attack_data']=(d,t)
        if not t.empty:
            derived['offensive_story']=build_offensive_story(d,t)
    except (KeyError,ValueError,TypeError,AttributeError):
        pass
    try:
        from intelligence.defensive_open_play import analyze as analyze_defense
        dp,de=analyze_defense(events,derived['focal_team'])
        derived['defensive_open_play_possessions']=dp
        derived['defensive_open_play_events']=de
    except (KeyError,ValueError,TypeError,AttributeError):
        pass
    st.session_state['efos_scoped_cache']=(signature,derived)
    return derived


def _catalog() -> pd.DataFrame:
    return scan_catalog(BASE_DIR / "data" / "raw" / "statsbomb", BASE_DIR / "config" / "team_metadata.yaml")


def _supabase_selection_panel() -> None:
    """Private source catalog; no local admin credentials or public Storage URLs."""
    cfg = _cloud_config()
    if cfg is None:
        st.info('Configura EFOS_SUPABASE_URL y EFOS_SUPABASE_ANON_KEY para habilitar el catálogo privado.')
        return
    _page_intro('Catálogo conectado · Supabase',
                'Elige la competición, temporada, equipo y partido. EFOS utiliza los CSV.GZ privados ya catalogados.',
                ['Supabase Auth', 'Dataset verificado', 'Sin datos sintéticos'], eyebrow='EFOS · FUENTE PRIVADA')
    try:
        token = _cloud_token()
        rows = SB.catalog(cfg, token)
    except SB.CloudError as exc:
        st.error(str(exc));return
    if not rows:
        st.warning('Esta cuenta todavía no tiene datasets visibles por RLS. Solicita acceso a una organización EFOS.')
        return
    frame = pd.DataFrame(rows)
    required = {'competition','season','period','team_name','dataset_id','provider_match_id'}
    if not required.issubset(frame.columns):
        st.error('El esquema del catálogo no coincide con el esperado.');return
    frame = frame.dropna(subset=list(required)).copy()
    c1,c2,c3,c4 = st.columns(4)
    with c1:
        competition = st.selectbox('Liga', sorted(frame.competition.unique()), key='sb_competition')
    frame = frame[frame.competition.eq(competition)]
    with c2:
        season = st.selectbox('Temporada', sorted(frame.season.unique(),reverse=True), key='sb_season')
    frame = frame[frame.season.eq(season)]
    with c3:
        team = st.selectbox('Equipo', sorted(frame.team_name.unique()), key='sb_team')
    frame = frame[frame.team_name.eq(team)]
    with c4:
        period = st.selectbox('Periodo', sorted(frame.period.unique()), key='sb_period')
    frame = frame[frame.period.eq(period)]
    if frame.empty:
        st.info('No hay partidos para esta combinación.');return
    # May contain multiple datasets, but a single analysis is scoped to one source dataset.
    options = sorted(frame.dataset_id.astype(str).unique().tolist())
    dataset_id = options[0] if len(options)==1 else st.selectbox('Dataset registrado',options,key='sb_dataset')
    # Keep all authorized rows to label opponents without inventing home/away.
    full_catalog = pd.DataFrame(rows)
    frame = frame[frame.dataset_id.astype(str).eq(dataset_id)].drop_duplicates('provider_match_id')
    def match_label(mid):
        r = frame.loc[frame.provider_match_id.astype(str).eq(str(mid))].iloc[0]
        date = str(r.get('match_date') or '').split('T')[0]
        if r.get('home_team') and r.get('away_team'):
            return f"{date + ' · ' if date and date != 'None' else ''}{r['home_team']} vs {r['away_team']} · {mid}"
        pair = full_catalog[(full_catalog.dataset_id.astype(str) == str(dataset_id)) &
                            (full_catalog.provider_match_id.astype(str) == str(mid))]
        opponents = sorted(set(pair.team_name.dropna().astype(str)) - {team})
        opponent = opponents[0] if len(opponents) == 1 else 'Rival no identificado'
        return f"{team} vs {opponent} · Partido {mid} (localía sin confirmar)"
    mids = frame.provider_match_id.astype(str).tolist()
    # Stable within a dataset and team, reset automatically when those filters change.
    selection_key = 'sb_match_ids_' + hashlib.sha256(f'{dataset_id}|{team}'.encode()).hexdigest()[:12]
    matches = st.multiselect('Partidos que quieres analizar', mids, default=mids,
                             format_func=match_label, key=selection_key)
    st.caption(f'{len(mids)} partidos accesibles · {len(matches)} seleccionados. '
               'El archivo original puede incluir acciones de ambos equipos.')
    if not matches:
        st.info('Selecciona al menos un partido.');return
    _divider()
    try:
        version, engine_hash = analysis_signature()
        snapshot = SB.ready_run(cfg, token, str(dataset_id), team, matches, version, engine_hash)
    except SB.CloudError as exc:
        st.error(f'No se pudo consultar la disponibilidad del análisis: {exc}')
        return
    if snapshot:
        st.success('Análisis persistente disponible. No necesitas descargar ni procesar el CSV.')
        if st.button('Abrir análisis guardado', type='primary', use_container_width=True, key='sb_open_snapshot'):
            try:
                token = _cloud_token()
                # Membership and ready status are revalidated by RLS on every request.
                confirmed = SB.ready_run(cfg, token, str(dataset_id), team, matches, version, engine_hash)
                if not confirmed or confirmed['id'] != snapshot['id']:
                    raise SB.CloudError('El análisis dejó de estar disponible para esta sesión.')
                with st.spinner('Recuperando evidencia, mapas y narrativa táctica…'):
                    result = SB.archived_analysis(cfg, token, snapshot['id'])
                ctx = {'league':competition,'season':season,'team':team,'period':period,
                       'files':['Análisis persistente privado'],'coach':None,
                       'supabase_dataset_id':dataset_id,'origin':'Supabase · análisis persistente'}
                result['dataset_context'] = ctx
                st.session_state['analysis'] = result
                st.session_state['analysis_digest'] = str(snapshot['id'])
                st.session_state['dataset_context'] = ctx
                st.session_state['upload_names'] = ['Análisis persistente']
                st.session_state['upload_paths'] = []
                st.session_state['nav'] = '★ Informe Ejecutivo'
                st.rerun()
            except (SB.CloudError, OSError, ValueError, KeyError) as exc:
                st.error(f'No se pudo abrir el análisis persistente: {exc}')
    else:
        st.info('Esta selección aún no está precalculada para la versión actual del motor EFOS. '
                'El administrador puede generarla desde el worker de Supabase. '
                'Mientras tanto es posible analizarla bajo demanda, con una espera mayor.')
    # Deliberate fallback for exploration; never silently launch expensive work.
    with st.expander('Análisis bajo demanda (más lento)', expanded=False):
        analyze_on_demand = st.button('Descargar y procesar esta muestra',
                                      use_container_width=True, key='sb_analyze')
    if analyze_on_demand:
        bar, status = _analysis_progress()
        try:
            # Re-check membership and source authorization on every analysis request.
            token = _cloud_token()
            allowed = SB.catalog(cfg,token)
            allowed_pairs = {(str(x.get('dataset_id')),str(x.get('team_name')),str(x.get('provider_match_id'))) for x in allowed}
            if not all((dataset_id,team,mid) in allowed_pairs for mid in matches):
                raise SB.CloudError('La selección ya no está autorizada para la sesión actual.')
            sources = SB.authorized_sources(cfg,token,dataset_id)
            if not sources:
                raise SB.CloudError('Dataset catalogado sin archivo original accesible. Revisa los registros del worker.')
            bar.progress(15,text='1/4 · Verificando acceso al dataset y las rutas privadas')
            cache_dir = RUNTIME_DIR / 'supabase_cache' / hashlib.sha256(
                str(st.session_state['supabase_user_id']).encode('utf-8')).hexdigest()[:16]
            paths = []
            for i, source in enumerate(sources):
                bar.progress(15 + int(32*i/len(sources)), text=f'2/4 · Descargando origen {i+1} de {len(sources)}')
                paths.append(SB.cache_source(cfg,token,source,cache_dir))
            bar.progress(52,text='3/4 · Reconstruyendo comportamientos con los motores EFOS')
            digest = _digest_many([dataset_id,team,*sorted(matches),
                                   *sorted(str(x['file_sha256']) for x in sources)])
            with st.spinner('EFOS está analizando los eventos seleccionados…'):
                _analyze_paths(paths,digest,[f'Supabase · {competition} · {season} · {period}'],
                               focal_team=team,match_ids=matches)
            ctx={'league':competition,'season':season,'team':team,'period':period,
                 'files':[str(x['storage_path']).split('/')[-1] for x in sources],
                 'coach':None,'supabase_dataset_id':dataset_id,'origin':'Supabase (RLS)'}
            st.session_state['dataset_context']=ctx
            if st.session_state.get('analysis') is not None:
                st.session_state['analysis']['dataset_context']=ctx
            bar.progress(100,text='4/4 · Informe disponible')
            status.empty()
            st.rerun()
        except (SB.CloudError,ValueError,OSError,KeyError) as exc:
            bar.empty();status.empty()
            st.error(f'No se pudo preparar esta muestra: {exc}')


def _automatic_csv_upload() -> None:
    """Send recognized StatsBomb/EFOS files through the full tactical pipeline."""
    st.markdown("## Cargar y analizar partidos")
    st.caption("EFOS reconoce automáticamente los CSV de StatsBomb y EFOS. "
               "El mapeo técnico solo aparece para formatos que no conocemos.")
    uploads = st.file_uploader("Archivos CSV de uno o varios partidos", type=["csv"],
                               accept_multiple_files=True, key="efos_native_csv_upload")
    if not uploads:
        st.info("Selecciona tus archivos. EFOS verificará el formato antes de iniciar el análisis.")
        return
    try:
        # Content-addressed persistence avoids writing the same large file on each rerun.
        saved = [persist_csv_bytes(file.getvalue(), file.name, RUNTIME_DIR, str(st.session_state["username"]))
                 for file in uploads]
        paths = [item[0] for item in saved]
        source_digest = _digest_many([item[1] for item in saved])
        summary = inspect_uploaded_paths(paths)
    except (ValueError, UnicodeError, pd.errors.ParserError, OSError) as exc:
        st.error(f"No fue posible revisar el CSV: {exc}")
        return

    if not summary["recognized"]:
        st.warning("El archivo no tiene el esquema nativo de StatsBomb/EFOS. "
                   "Se habilita el asistente para otros proveedores; no se asumirá que sus columnas "
                   "tienen el mismo significado.")
        with st.expander("Configurar CSV de otro proveedor", expanded=True):
            from visualization.csv_workbench import render_csv_workbench
            render_csv_workbench()
        return

    st.success("Formato reconocido: " + ", ".join(summary["formats"]))
    c1, c2, c3 = st.columns(3)
    c1.metric("Eventos únicos", f'{summary["unique_events"]:,}' if summary["unique_events"] is not None else "No disponible")
    c2.metric("Partidos identificados", len(summary["matches"]))
    c3.metric("Archivos", summary["n_files"])
    st.caption(f'{summary["rows"]:,} filas originales antes de consolidar.')
    st.caption("Los eventos repetidos por freeze frame y formación se consolidan dentro del pipeline; "
               "los datos auxiliares del CSV original se conservan por separado.")

    candidates = summary["teams"]
    team = st.selectbox("Equipo que quieres analizar", candidates,
                        format_func=lambda t: f'{t} · {summary["team_matches"].get(t, 0)} partidos',
                        key="efos_native_focal_team")
    labels = match_labels(summary, team)
    possible = [mid for mid in summary["matches"] if team in summary["match_teams"].get(mid, [])]
    if not possible:
        st.warning("No hay partidos para este equipo.")
        return
    chosen = st.multiselect("Partidos incluidos en el análisis", possible, default=possible,
                            format_func=lambda mid: labels.get(mid, mid), key="efos_native_match_filter")
    if not chosen:
        st.info("Selecciona al menos un partido.")
        return
    if any(len(summary["match_teams"].get(mid, [])) < 2 for mid in chosen):
        st.warning("Algunos partidos no incluyen acciones de ambos equipos: "
                   "la lectura de la oposición y las transiciones puede ser incompleta.")

    with st.expander("Detalle técnico de importación (opcional)"):
        st.write("Esquemas detectados:", ", ".join(summary["formats"]))
        st.write("Partidos seleccionados:", len(chosen), "de", len(possible))
        st.caption("No se inventan jugadores, datos 360, fechas ni resultados. "
                   "Los freeze frames de tiros no equivalen a StatsBomb 360.")
    if st.button("Analizar en EFOS", type="primary", use_container_width=True, key="efos_native_analyze"):
        selected_digest = _digest_many([source_digest, team, *sorted(chosen)])
        try:
            _analyze_with_progress(paths, selected_digest, [file.name for file in uploads], team,
                                   match_ids=chosen, caption=f'{len(chosen)} partidos seleccionados')
            from ui.data_catalog import _parse_filename, PERIOD_LABELS
            first_name = Path(uploads[0].name)
            league, season, period = _parse_filename(first_name)
            context = {"league": league if season != "Sin temporada" else "CSV importado",
                       "season": season if season != "Sin temporada" else None,
                       "team": team,
                       "period": PERIOD_LABELS.get(period, "Archivo completo") if len(chosen) == len(possible)
                       else f"{len(chosen)} partidos seleccionados",
                       "files": [file.name for file in uploads], "coach": None}
            st.session_state["dataset_context"] = context
            if st.session_state.get("analysis") is not None:
                st.session_state["analysis"]["dataset_context"] = context
                st.session_state["nav"] = "★ Informe Ejecutivo"
            st.rerun()
        except Exception as exc:
            st.error(f"No fue posible procesar esta muestra: {exc}")


def _selection_panel() -> None:
    sources = (['Supabase · catálogo privado','Cargar CSV de cualquier equipo','Repositorio local']
               if _cloud_config() is not None else ['Repositorio local','Cargar CSV de cualquier equipo'])
    if st.session_state.get('data_source') not in sources:
        st.session_state['data_source'] = sources[0]
    source=st.radio('Origen de los datos',sources,horizontal=True,key='data_source')
    if source=='Supabase · catálogo privado':
        _supabase_selection_panel()
        return
    if source=='Cargar CSV de cualquier equipo':
        _automatic_csv_upload()
        return
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
            _analyze_with_progress(paths, digest, [p.name for p in paths], team,
                                   caption=f'{season} · {period}')
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
            st.session_state["nav"] = "Equipo y datos"
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

    from visualization.tactical_context_ui import render_context
    render_context('connections')

    # --- Con balón ----------------------------------------------------------
    _story_section("Con balón", "Cómo progresa, atrae presión y ocupa los espacios de avance.")
    build = tf.get("construction_progression", {}) if isinstance(tf, dict) else {}
    off = tf.get("offensive_microconcepts", {}) if isinstance(tf, dict) else {}
    value = tf.get("value_purpose", {}) if isinstance(tf, dict) else {}
    row1 = st.columns(4)
    with row1[0]: _metric_card("Pases completos bajo presión", _pm_text(build.get("pressure_attraction_passes", {}).get("per_match")), "primeros dos tercios · regla de eventos")
    with row1[1]: _metric_card("Liberación posterior", _pct_text(build.get("pressure_release_success", {}).get("rate")), "progresión tras atraer presión")
    with row1[2]: _metric_card("Half-space", _pm_text(build.get("halfspace_entries", {}).get("per_match")), "entradas completadas por partido")
    with row1[3]: _metric_card("Combinaciones A→B→C", _pm_text(build.get("third_man_progression_proxy", {}).get("per_match")), "proxy A→B→C progresivo")
    row2 = st.columns(4)
    with row2[0]: _metric_card("Pases a zonas interiores", _pm_text(off.get("interval_entries", {}).get("per_match")), "destino geométrico interior")
    with row2[1]: _metric_card("Centro a zona peligrosa", _pm_text(off.get("cross_to_danger_zone_proxy", {}).get("per_match")), "destino profundo configurado")
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
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.pyplot(X.lineup_pitch(shape, lu[shape], team, _shirt_name, POSITION_ES), clear_figure=True, use_container_width=True)
        st.caption("Cada posición muestra al jugador que más veces fue titular en ella con ese dibujo y su alternativa. "
                   "El dibujo se reconstruye con las posiciones StatsBomb de los titulares antes del primer cambio.")
    with right:
        from visualization.coach_formation_ui import render_formation_matches
        render_formation_matches(result, shape)


def _executive_signal_cards(brief: dict, *, prefix: str) -> None:
    """Three quick executive signals. Full traceability lives below the fold."""
    cards = st.columns(3, gap='medium')
    for idx, (col, signal) in enumerate(zip(cards, brief['signals'])):
        with col:
            quality = ('Muestra limitada · explorar con cautela' if signal['status'] == 'SMALL_SAMPLE'
                       else 'No evaluable' if signal['status'] == 'INSUFFICIENT' else '')
            st.markdown(
                "<div class='efos-exec-card'>"
                f"<div class='kicker'>{html.escape(signal['section'])}</div>"
                f"<div class='name'>{html.escape(signal['headline'])}</div>"
                f"<div class='value'>{html.escape(signal['value'])}</div>"
                f"<div class='note'>{html.escape(signal['caption'])}</div>"
                + (f"<div class='quality'>{html.escape(quality)}</div>" if quality else '')
                + "</div>", unsafe_allow_html=True)
            if st.button('Explorar ' + signal['module'] + ' →',
                         key=f'{prefix}_signal_{idx}', use_container_width=True):
                st.session_state['nav'] = NAV_ALIASES.get(signal['module'], signal['module'])
                st.rerun()


def _executive_lede(brief: dict, reasoning: dict | None = None) -> None:
    connected = reasoning.get('identity') if isinstance(reasoning,dict) and reasoning.get('coverage') else None
    story = connected or brief['story']
    st.markdown(
        "<div class='efos-executive-lede'>"
        "<div class='eyebrow'>LA LECTURA DEL EQUIPO · 30 SEGUNDOS</div>"
        f"<div class='main'>{html.escape(story)}</div>"
        f"<p class='question'><b>La pregunta táctica:</b> {html.escape(brief['conflict'])}</p>"
        "</div>", unsafe_allow_html=True)


def _report_page(result: dict) -> None:
    """One tactical thesis, three linked observations, one real sequence."""
    from visualization.connected_diagnosis import coherent_observations
    sample=_scoped_result(result)
    team=sample.get('focal_team','Equipo')
    diagnosis=coherent_observations(sample)
    ids=_current_scope_matches(result)
    n=diagnosis.get('matches')
    input_meta = sample.get('input_metadata', {})
    all_dataset_matches = input_meta.get('available_matches_before_filter')
    # The worker analyzes only a team's selected matches. Do not call a
    # three-match sample a complete league season.
    full_sample_label = ('Muestra seleccionada · no temporada completa'
                         if n is not None and (not all_dataset_matches or int(n) < int(all_dataset_matches))
                         else 'Muestra del archivo')
    _page_intro(f'¿Qué está ocurriendo con {team}?',
                'Una lectura para el cuerpo técnico: comportamiento, evidencia y contraste.',
                [f'{n} partidos' if n is not None else 'Sin conteo de partidos',
                 full_sample_label if ids is None else 'Muestra filtrada'], eyebrow='EFOS · DIAGNÓSTICO')
    st.markdown('<div class="efos-executive-lede"><div class="eyebrow">UNA HISTORIA, NO UN TABLERO DE ESTADÍSTICAS</div>'
                f'<p class="main">{html.escape(diagnosis["lead"])}</p></div>',unsafe_allow_html=True)
    if n is not None and n<3:
        st.warning('Muestra exploratoria: menos de tres partidos. No se presenta como identidad recurrente del equipo.')
    if not diagnosis['findings']:
        st.info('Los eventos de esta selección no permiten un diagnóstico ligado a posesiones. Cambia el partido o revisa el CSV.')
        return
    st.markdown('### Lecturas para interpretar el juego')
    cols=st.columns(min(3,len(diagnosis['findings'])),gap='medium')
    for i,(col,finding) in enumerate(zip(cols,diagnosis['findings'])):
        with col:
            st.markdown('<div class="efos-exec-card">'
                f'<div class="kicker">0{i+1} · {html.escape(finding["target"].upper())}</div>'
                f'<div class="name">{html.escape(finding["title"])}</div>'
                f'<div class="note">{html.escape(finding["text"])}</div>'
                '</div>',unsafe_allow_html=True)
            with st.expander('Qué significa y cómo comprobarlo'):
                st.write(finding['meaning']); st.caption(finding['scope'])
            if st.button('Profundizar →',key=f'exec_joined_{i}',use_container_width=True):
                st.session_state['nav']=finding['target'];st.rerun()
    attack_data=sample.get('organized_attack_data')
    if isinstance(attack_data,(tuple,list)) and len(attack_data)==2 and isinstance(attack_data[1],pd.DataFrame) and len(attack_data[1]):
        from visualization.attack_story_figures import figure_sequence_board, sequence_script
        from visualization.organized_attack_app import _representatives
        from intelligence.offensive_story import readable_match_labels
        d,t=attack_data
        reps=_representatives(t,limit=10)
        if len(reps):
            _section_lead('La evidencia sobre el campo','Una secuencia REAL que permite comprobar cómo se enlazan acciones y qué desenlace tuvieron.')
            options={str(r.key):r for r in reps.itertuples(index=False)}
            labels=readable_match_labels(sample['events'],team,t.match_id.astype(str).unique())
            chosen=st.selectbox('Jugada observada',list(options),key='efos_hero_sequence',
                format_func=lambda k:f"{labels.get(str(options[k].match_id),'Partido')} · {float(options[k].minute):.0f}′ · {options[k].outcome}")
            r=options[chosen]
            st.markdown(f'**Qué pasó:** {int(r.actions)} acciones registradas, {int(r.box_entries)} entradas al área y '
                        f'{int(r.shots)} remates. **Desenlace:** {r.outcome}.')
            # `chosen` is a Streamlit-friendly string. The scientific event
            # frame uses the original tuple key, not its printed repr.
            sequence_key = r.key
            st.plotly_chart(figure_sequence_board(d,sequence_key),use_container_width=True,key='efos_executive_field',config={'displaylogo':False})
            chain=sequence_script(d,sequence_key)
            if chain: st.caption('Secuencia: '+' → '.join(chain))
            st.caption('Ejemplo observado; no constituye una jugada promedio ni prueba desmarques sin balón.')
    st.caption(diagnosis['limit'])
    with st.expander('Trazabilidad · eventos y límites metodológicos'):
        for f in diagnosis['findings']:
            st.markdown('**'+f['title']+'**');st.write(f['text']);st.caption(f['scope'])
    # The PDF is built from exactly the same scoped diagnosis. Never export a
    # season PDF under a selected-match heading.
    try:
        from coach_story.connected_pdf import build_connected_pdf
        pdf=build_connected_pdf(diagnosis)
        st.download_button('Descargar diagnóstico ejecutivo · PDF',pdf,
                           file_name='EFOS_Diagnostico_'+''.join(c if c.isalnum() else '_' for c in team)+'.pdf',
                           mime='application/pdf',key='efos_diag_pdf')
    except ImportError:
        st.caption('PDF no disponible en esta instalación; consulta dependencias de ReportLab.')


def _coach_page(result: dict) -> None:
    """Football-first coach view: one formation, one comparison, optional research."""
    team=result.get('focal_team','Equipo'); cp=result.get('coach_identity') or {}
    ctx=st.session_state.get('dataset_context') or result.get('dataset_context') or {}
    shape=(cp.get('estructura') or {}).get('dibujo_principal') or 'No identificado'
    _page_intro('¿Cómo se organiza el equipo?',
                'El dibujo inicial es un punto de partida; las conexiones y los contextos revelan su comportamiento.',
                [f'Equipo: {team}',f'Entrenador: {ctx.get("coach") or "No informado"}',f'Dibujo frecuente: {shape}'],
                eyebrow='EFOS · MODELO DE JUEGO')
    _section_lead('Organización inicial y protagonistas',
                  'Dibujo inicial de la temporada completa. La selección de partido se aplica al perfil comparativo inferior, no a este once histórico.')
    if cp:
        _lineup_section(result,_xcache(result),team)
    else:
        st.info('No hay alineaciones suficientes en la muestra.')
    _section_lead('¿Qué cambia frente al rival?',
                  'Ocho observaciones comparables para los mismos partidos. Sin inventar percentiles de liga.')
    from visualization.phase_profile import render_phase_profile
    render_phase_profile(result,team,match_ids=_current_scope_matches(result))
    with st.expander('Investigación avanzada · CTS, formación y modelo matemático',expanded=False):
        if _current_scope_matches(result) is not None:
            st.warning('El CTS de esta sección es la temporada completa; no está recalculado para el partido filtrado. La comparación anterior sí utiliza el filtro global.')
        from visualization.coach_formation_ui import render_cts_by_formation
        render_cts_by_formation(result,team)
        st.caption('CTS = escala experimental interna 0–100, no percentil de liga ni formación dinámica demostrada.')
        with st.expander('Leer los índices en profundidad'):
            from visualization.coach_season_reading import render_radar_reading
            render_radar_reading(result)
            from visualization.reasoning_ui import render_reasoning
            render_reasoning(result, 'all')


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
    with st.expander('Ver animación 2D con StatsBomb 360 · cuando haya fotografías',expanded=False):
        from visualization.transition_360_ui import render_transition_360
        render_transition_360(result,team)

def _set_pieces_page(result: dict) -> None:
    """Editorial storytelling: narrative > 2D pattern evidence > optional 3D > audit trail."""
    team, events, _, _, _, _, _ = _context(result)
    _page_intro("Balón Parado", "Una historia por banda: qué repite el equipo, dónde busca el espacio y qué peligro genera.",
                ["Patrón", "Territorio", "Consecuencia"], eyebrow="INTELIGENCIA TÁCTICA")
    seq = result.get("set_piece_sequences")
    if not isinstance(seq,pd.DataFrame) or seq.empty:
        missing=result.get("set_piece_summary",{}).get("missing",[])
        st.info("No hay secuencias de balón parado disponibles para esta selección." +
                (f" Faltan campos: {', '.join(missing)}" if missing else ""))
        return
    selected_global=_current_scope_matches(result)
    if selected_global is not None:
        seq=seq[seq.match_id.astype(str).isin(set(selected_global))].copy()
    if seq.empty:
        st.info("Sin acciones de balón parado para el partido o rival seleccionado.");return
    available = seq.groupby(['kind','side'], observed=True).size()
    coverage = [f'{kind_label}: ' + ' / '.join(
        f'{side_label} {int(available.get((kind_label, side_label), 0))}'
        for side_label in SCOPE) for kind_label in KINDS]
    st.caption('Ejecuciones identificadas en esta selección: ' + ' · '.join(coverage))
    if not any(available.get((k,s),0) for k in KINDS for s in SCOPE):
        st.info('No existen ejecuciones clasificadas como córners, tiros libres o saques de banda en estos partidos. '
                'No se generarán gráficos ni patrones ficticios.')
        return
    select1,select2,select3=st.columns([1.5,1,1.5])
    with select1:
        active_kind = st.session_state.get('sp_story_kind')
        if active_kind not in KINDS or not any(available.get((active_kind,scope),0) for scope in SCOPE):
            st.session_state['sp_story_kind'] = next(k for k in KINDS if any(available.get((k,s),0) for s in SCOPE))
        kind=st.selectbox("Tipo de jugada",KINDS,key="sp_story_kind")
    with select2:
        active_side = st.session_state.get('sp_story_side')
        if active_side not in SCOPE or not available.get((kind,active_side),0):
            st.session_state['sp_story_side'] = next((s for s in SCOPE if available.get((kind,s),0)),SCOPE[0])
        side=st.radio("Perspectiva",SCOPE,horizontal=True,key="sp_story_side")
    c=_xcache(result)
    labels=c.get("labels",{})
    reverse={v:k for k,v in labels.items()}
    with select3:
        chosen_matches=st.multiselect("Partidos · vacío = muestra completa",list(labels.values()),key="sp_story_matches")
    base=seq[seq["match_id"].astype(str).isin({str(reverse[x]) for x in chosen_matches})].copy() if chosen_matches else seq
    d=base[(base["kind"]==kind)&(base["side"]==side)].copy()
    overall=summarize_sample(d)
    n=overall["n"]
    if not n:
        st.info("No hay ejecuciones para este tipo, perspectiva y filtro de partidos. "
                "Revisa los recuentos anteriores o elimina el filtro de partidos; no es un error de carga.")
        return
    profile=premium_story_profile(base,kind,side)
    findings=narrative_findings(base,side,kind)
    contextual=context_finding(base,kind,side)

    # The narrative is generated from the filtered sample, never from a static demo.
    hero_title=html.escape(profile["headline"])
    hero_intro=html.escape(profile["intro"])
    metric_shot=overall.get("shot_rate_pct")
    shot_text=f"{metric_shot:.1f}% con remate en 10 s" if metric_shot is not None else "Remate no evaluable"
    st.markdown(
        "<div class='efos-sp-hero'>"
        f"<div class='sp-kicker'>LO QUE CUENTAN LOS DATOS · {html.escape(kind.upper())} · {html.escape(side.upper())}</div>"
        f"<div class='sp-title'>{hero_title}</div>"
        f"<div class='sp-intro'>{hero_intro}</div>"
        "<div class='sp-meta'>"
        f"<span>{n} ejecuciones</span><span>{overall['n_matches']} partidos</span>"
        f"<span>{shot_text}</span>"
        "</div></div>",unsafe_allow_html=True)

    observations=[f for f in findings if f.get("status")=="observed" and f.get("title") not in
                  ("Patrón más repetido","Patrón con mayor xG por ejecución")]
    if contextual:
        observations.append(contextual)
    # Max two secondary findings: prevents repeating all the cards seen below.
    observations=observations[:2]
    if observations:
        mini_cols=st.columns(len(observations))
        for idx,(col,ins) in enumerate(zip(mini_cols,observations)):
            with col:
                st.markdown(
                    "<div class='efos-sp-pattern'>"
                    f"<div class='sp-eyebrow'>LECTURA {idx+1:02d}</div>"
                    f"<div class='sp-value'>{html.escape(ins['title'])}</div>"
                    f"<div class='sp-details'>{html.escape(ins['detail'])}</div>"
                    "</div>",unsafe_allow_html=True)

    st.markdown("### ¿Hacia dónde se dirigen los servicios?")
    map_mode=st.radio("Mapa principal",["Zonas dominantes","Trayectorias observadas"],horizontal=True,
                      key="sp_story_map_mode")
    map_fig=SPM.dual_destination_map(base,kind,side,mode="trayectorias" if map_mode=="Trayectorias observadas" else "zonas")
    st.pyplot(map_fig,clear_figure=True,use_container_width=True)
    halves=profile["by_flank"]
    card_cols=st.columns(2)
    for col,p in zip(card_cols,halves):
        with col:
            if p["status"]=="observed":
                txt=f"<strong>Desde {html.escape(p['flank'].lower())}:</strong> {html.escape(str(p['zone']))} · {p['count']} de {p['n']} ({p['share_pct']:.0f}%) en {p['n_matches']} partidos."
            elif p["n"]:
                txt=f"<strong>{html.escape(p['flank'])}:</strong> {p['n']} destinos observados; muestra insuficiente para atribuir un patrón recurrente."
            else:
                txt=f"<strong>{html.escape(p['flank'])}:</strong> sin destinos con coordenadas en esta muestra."
            st.markdown(f"<div class='efos-sp-side'>{txt}</div>",unsafe_allow_html=True)
    st.caption("Destinos registrados del pase, no punto de caída ni primer contacto. "
               "Las líneas del mapa 2D unen ubicaciones observadas o promedios descriptivos de grupos.")

    st.markdown("### Lo habitual no siempre es lo más peligroso")
    col1,col2=st.columns(2)
    frequent=profile.get("frequent")
    productive=profile.get("productive")
    with col1:
        if frequent:
            f_title=f"{frequent['flank']} → {frequent['zone']}"
            f_detail=f"{frequent['n']} ejecuciones en {frequent['n_matches']} partidos · {frequent['shots']} con remate registrado"
        else:
            f_title="Sin un patrón recurrente defendible"
            f_detail="La muestra seleccionada no alcanza el mínimo de repeticiones en tres partidos."
        st.markdown("<div class='efos-sp-pattern sp-gold'><div class='sp-eyebrow'>MÁS REPETIDO</div>"
            f"<div class='sp-value'>{html.escape(f_title)}</div>"
            f"<div class='sp-details'>{html.escape(f_detail)}</div></div>",unsafe_allow_html=True)
    with col2:
        if productive:
            p_title=f"{productive['flank']} → {productive['zone']}"
            p_detail=(f"{productive['xg_mean']:.3f} xG por ejecución con cobertura · "
                     f"{productive['n']} jugadas en {productive['n_matches']} partidos · "
                     f"{productive['n_xg_valid']}/{productive['n']} con xG evaluable")
        else:
            p_title="Sin comparación de peligro sólida"
            p_detail="Se necesitan más remates, ejecuciones y cobertura de xG para clasificar patrones."
        st.markdown("<div class='efos-sp-pattern sp-blue'><div class='sp-eyebrow'>MAYOR xG POR EJECUCIÓN</div>"
            f"<div class='sp-value'>{html.escape(p_title)}</div>"
            f"<div class='sp-details'>{html.escape(p_detail)}</div></div>",unsafe_allow_html=True)

    chain=profile.get("sequence")
    if chain:
        steps=[chain["executor"],chain["target_zone"],chain["first_registered_player"],chain["first_shooter"]]
        line=" <span style='color:#B38A41'>→</span> ".join(html.escape(str(v)) for v in steps)
        st.markdown("<div class='efos-sp-sequence'><div class='efos-kicker'>SECUENCIA REGISTRADA RECURRENTE</div>"
            f"<div class='sp-path'>{line}</div>"
            f"<div class='sp-sub'>Misma combinación observada {chain['n']} veces en {chain['n_matches']} partidos. "
            "P1 es la primera intervención REGISTRADA: no confirma contacto ni intención de la jugada."
            "</div></div>",unsafe_allow_html=True)

    # 3D is supplemental and deliberately opt-in; isolated from evidence claims.
    if kind in ("Córners","Tiros libres"):
        with st.expander("Explorar patrón en 3D · representación ilustrativa",expanded=False):
            st.caption("La profundidad y el relieve facilitan inspeccionar el envío. "
                       "NO son tracking ni la trayectoria física o altura medida del balón. "
                       "Cuando StatsBomb etiqueta la altura, el relieve únicamente distingue su categoría.")
            views=SP3.available_views(d,profile)
            if views:
                left,right=st.columns([2,1])
                with left:
                    view=st.selectbox("Patrón que quieres observar",views,key="sp_story_3d_view")
                with right:
                    max_shown=st.select_slider("Envíos visibles",options=[3,5,8],value=5,key="sp_story_3d_limit")
                active=st.checkbox("Mostrar vista espacial 3D",value=False,key="sp_story_3d_enable")
                if active:
                    selected=SP3.select_view(d,profile,view)
                    fig,meta=SP3.spatial_illustration(selected,max_events=max_shown)
                    st.plotly_chart(fig,use_container_width=True,config={"displayModeBar":False})
                    st.caption(f"{meta['drawn']} ejemplos dibujados de {meta['observations_with_coordinates']} "
                               "ejecuciones con coordenadas en este filtro, ordenadas por partido y tiempo. "
                               f"{meta['drawn_with_labeled_height_relief']} con una categoría de altura registrada por StatsBomb. "
                               "El eje vertical carece de unidades físicas.")
            else:
                st.info("No hay datos espaciales suficientes para habilitar esta vista.")

    if side=="En contra":
        st.markdown("### ¿Dónde terminan rematando los rivales?")
        shot_fig=SPM.shot_origin_map(base,kind,side)
        st.pyplot(shot_fig,clear_figure=True,use_container_width=True)
        st.caption("Primer remate rival registrado por ejecución; no determina el marcaje usado por la defensa.")

    # Evidence remains deliberately collapsed. It is the methodological audit trail.
    with st.expander("Evidencia jugada por jugada · P0 → P1 → P2",expanded=False):
        a,b=st.columns(2)
        with a:
            executors=["Todos"]+d["executor"].dropna().astype(str).value_counts().index.tolist()
            selected_executor=st.selectbox("Ejecutor",executors,key="sp_story_executor")
        with b:
            flanks=st.multiselect("Banda",FLANKS,default=FLANKS,key="sp_story_flanks")
        e=d[d["flank"].isin(flanks)]
        if selected_executor!="Todos":e=e[e["executor"].eq(selected_executor)]
        cols=["match_id","minute","side","flank","executor","target_zone","first_registered_player",
              "shot_generated","shot_zone","xg","goal","xg_coverage","set_piece_id"]
        rename={"match_id":"Partido","minute":"Minuto","side":"Perspectiva","flank":"Banda",
                "executor":"Ejecutor","target_zone":"Destino registrado","first_registered_player":"Primera intervención (proxy)",
                "shot_generated":"Con remate","shot_zone":"Zona del primer remate","xg":"xG","goal":"Gol",
                "xg_coverage":"Cobertura xG","set_piece_id":"ID de evento"}
        st.dataframe(e[[col for col in cols if col in e]].rename(columns=rename),
                     hide_index=True,use_container_width=True)
        st.caption("El primer interviniente registrado no equivale necesariamente al primer contacto. "
                   "xG=0 sólo cuando no hay remate; si hubo remate pero falta xG, se muestra como dato faltante. "
                   f"Cobertura de xG: {overall['xg_coverage_pct']:.1f}%.")
        if not e.empty:
            st.download_button("Exportar evidencia CSV",e.to_csv(index=False).encode("utf-8-sig"),
                               file_name="efos_evidencia_balon_parado.csv",mime="text/csv",key="sp_story_export")
    st.caption("EFOS CSE: una ejecución P0 → intervención registrada P1 → remates P2 del mismo equipo, "
               "partido, periodo y posesión dentro de 10 s. Reinicios posteriores truncan la secuencia. "
               "En faltas y laterales se consideran ejecuciones desde el último tercio (x≥80). "
               "Las zonas son heurísticas de EFOS, sujetas a contraste en vídeo.")

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
    from visualization.organized_attack_app import render_attack_module
    sample=_scoped_result(result)
    team=sample.get('focal_team')
    events=sample.get('events')
    if not isinstance(events,pd.DataFrame) or events.empty:
        st.info('No hay eventos del partido seleccionado.');return
    render_attack_module(events,team,precomputed=sample.get('organized_attack_data'),
                         frames_360=result.get('defensive_360_frames'),result=None)


def _off_ball_page(result: dict) -> None:
    sample=_scoped_result(result)
    team=sample.get('focal_team');events=sample.get('events')
    if not isinstance(events,pd.DataFrame) or events.empty:
        st.info('No hay eventos del partido seleccionado.');return
    pre=(sample.get('defensive_open_play_possessions'),sample.get('defensive_open_play_events'))
    if not all(isinstance(d,pd.DataFrame) for d in pre):pre=None
    from defensive_open_play_app import render_defense_questions
    render_defense_questions(events,team,result=None,frames_360=result.get('defensive_360_frames'),precomputed=pre)


def _off_ball_page_integral(result: dict) -> None:
    team, events, _, _, _, _, _ = _context(result)
    story=result.get("defensive_story") or {}
    detail=result.get("smart_defense_possessions")
    players=result.get("smart_defense_players")
    summary=result.get("smart_defense_summary") or {}
    st.caption("Vista previa v0.4.12: también abarca córners, tiros libres y laterales rivales. "
               "Los denominadores y clasificaciones difieren del atlas exclusivamente de juego abierto.")
    st.markdown("### La respuesta defensiva cambia con el contexto")
    st.write(story.get("summary") or "No hay suficiente información para una identidad general.")
    if not isinstance(detail,pd.DataFrame) or detail.empty:
        st.info("No hay posesiones rivales con propietario explícito suficiente para reconstruir Smart Tactics. No se estiman formaciones ni marcajes.")
        return
    situation_options=[s for s in SITUATIONS if s in set(detail["scenario"])]
    f1,f2,f3=st.columns([1.7,1,1])
    with f1:
        situation=st.selectbox("¿Cómo ataca el rival?",situation_options,
                     index=situation_options.index("Contraataque etiquetado") if "Contraataque etiquetado" in situation_options else 0,
                     key="smart_def_situation")
    with f2:
        period=st.selectbox("Momento del partido",["Todo el partido"]+list(MOMENTS),key="smart_def_moment")
    with f3:
        score_choice=st.selectbox("Marcador",["Todos", "Empatando", "Ganando", "Perdiendo"],key="smart_def_score")
    selected=detail[detail["scenario"].eq(situation)].copy()
    code_state={"Empatando":"drawing","Ganando":"winning","Perdiendo":"losing"}
    if score_choice in code_state:
        selected=selected[selected["score_state"].eq(code_state[score_choice])]
    if period!="Todo el partido":
        selected=selected[selected["moment"].eq(period)]
    if selected.empty:
        st.info("No hay posesiones rivales de este tipo en el momento seleccionado."); return
    if isinstance(players,pd.DataFrame) and not players.empty:
        participating=players[players["possession_id"].isin(selected["possession_id"])].copy()
    else:participating=pd.DataFrame()
    snap=summarize_smart_defense(selected,participating)
    aggregate=snap["scenarios"].get(situation,{})
    n=aggregate.get("n_possessions",0);matches=aggregate.get("matches",0)
    st.markdown(f"#### ¿Qué ocurrió en {n:,} posesiones rivales de esta categoría?")
    if aggregate.get("status")=="EXPLORATORY":
        st.caption(f"Muestra exploratoria: {n} posesiones en {matches} partidos. No se afirma un patrón estable del entrenador.")
    else:
        st.caption(f"Patrón descriptivo observado en {matches} partidos. No demuestra un esquema de marcaje ni causalidad.")
    a,b,c=st.columns(3)
    with a:_metric_card("Presiones por 100 posesiones",f"{aggregate.get('pressures_per_100_possessions',0):.0f}","Intensidad de acciones registradas; puede superar 100")
    with b:_metric_card("Posesiones con remate rival",f"{aggregate.get('shot_rate_pct',0):.1f}%",f"{aggregate.get('n_shot_possessions',0)} posesiones")
    xg=aggregate.get("xg_per_possession_complete")
    with c:_metric_card("xG concedido / posesión",f"{xg:.3f}" if xg is not None else "Sin dato",f"Cobertura: {aggregate.get('xg_coverage_pct',0):.0f}%")
    dom=aggregate.get("dominant_action_zone")
    dominant_action=aggregate.get("dominant_action_type")
    if dom and dominant_action:
        st.markdown(f"**Lectura táctica:** frente a **{situation.lower()}**, la intervención más registrada fue "
                    f"**{dominant_action}** ({aggregate['dominant_action_type_share_pct']:.0f}% de acciones individuales), "
                    f"con mayor concentración en **{dom.lower()}** "
                    f"({aggregate['dominant_action_zone_share_pct']:.0f}% de las acciones ubicadas). "
                    "Es un patrón de intervenciones observadas, no una formación ni un marcaje demostrado.")
    elif dom:
        st.markdown(f"Las intervenciones se concentraron en **{dom.lower()}**; no se puede inferir una estructura táctica fija.")
    else:
        st.caption("No hay intervenciones suficientes con ubicación para definir una respuesta predominante.")
    st.markdown("### Dónde interviene el equipo y desde dónde remata el rival")
    st.pyplot(SDM.scenario_map(events,selected,team),clear_figure=True,use_container_width=True)
    st.caption("Ambos mapas están orientados a la portería propia del equipo. Los puntos representan eventos: no son posiciones simultáneas ni movimientos sin balón. "
               "En contraataques sólo usamos el patrón explícito ‘From Counter’ de StatsBomb.")
    st.markdown("### ¿Quién participa en esa respuesta defensiva?")
    leaders=aggregate.get("players",[])
    if leaders:
        for i,pl in enumerate(leaders[:4]):
            st.markdown(f"**{i+1}. {pl['player']}** · {pl['events']} acciones registradas "
                        f"en {pl['matches']} partidos · acción principal: {pl['dominant_action']} · "
                        f"{pl['share_of_observed_actions_pct']:.1f}% de la muestra individual")
        st.caption("Ranking por cantidad de acciones observadas en posesiones rivales de esta categoría; no por calidad del jugador ni minutos disputados.")
    else:st.caption("Sin intervenciones atribuibles a jugadores en esta selección.")
    if situation in ("Córner rival", "Tiro libre rival", "Saque lateral rival"):
        st.caption("Para ver hacia dónde se dirigen los envíos y las zonas de remate, consulta la sección **Balón Parado**; esta vista estudia cómo responde la defensa durante esas posesiones.")
    with st.expander("Cambios durante el partido · distribución por momento",expanded=False):
        table=selected.groupby("moment",observed=True).agg(Posesiones=("possession_id","size"),
                             Remates=("shot_conceded","sum"),Presiones=("pressures","sum"),
                             Partidos=("match_id","nunique")).reset_index()
        table["Con remate (%)"]=(100*table["Remates"]/table["Posesiones"]).round(1)
        st.dataframe(table.sort_values("moment"),hide_index=True,use_container_width=True)
        st.caption("Las diferencias pueden depender del rival, marcador y tamaño de muestra; no son efectos causales del entrenador.")
    with st.expander("Evidencia de las posesiones y jugadores · detalle auditable",expanded=False):
        cols=["match_id","opponent","minute","score_state","scenario","scenario_source","pressures",
              "defensive_events","reached_final_third","reached_box","shot_count","xg_conceded","xg_complete"]
        st.dataframe(selected[[c for c in cols if c in selected]],hide_index=True,use_container_width=True)
        if not participating.empty:
            st.dataframe(participating[["match_id","minute","player","action","x","y"]],hide_index=True,use_container_width=True)
    with st.expander("Identidad general y métodos de presión · análisis previo",expanded=False):
        st.write(story.get("summary", ""))
        if story.get("zones"):
            st.dataframe(pd.DataFrame(story["zones"]),hide_index=True,use_container_width=True)
        tf=result.get("coach_story",{}).get("tactical_framework",{})
        d=tf.get("defensive_profile",{})
        if d:
            st.write("Presión rival sobre pases (muestra global):",_pct_text(d.get("opponent_passes_under_pressure",{}).get("rate")))
        traps=result.get("trap_metrics",{})
        st.write("Trampas defensivas experimentales: ",int(traps.get("trap_attempts",0)))
        c=_xcache(result)
        _action_explorer("def",c,X.defence_actions(c["e"],team),"Greens","Eventos defensivos")
        st.caption("No se infieren marcaje zonal/individual ni distancias entre líneas sin observaciones 360/tracking específicas.")

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
    page=st.session_state['nav']
    if page=='Equipo y datos': _selection_panel()
    elif page=='★ Informe Ejecutivo': _report_page(result)
    elif page=='Modelo de Juego': _coach_page(result)
    elif page=='Con balón': _on_ball_page(result)
    elif page=='Sin balón': _off_ball_page(result)
    elif page=='Balón parado': _set_pieces_page(result)


_init_state()
if not st.session_state["authenticated"]:
    _login_page()
    _footer()
    st.stop()

try:
    active_cloud = _cloud_config() is not None
except SB.CloudError as exc:
    st.error(f'Configuración inválida: {exc}')
    st.stop()
if active_cloud:
    try:
        _cloud_token()
    except SB.CloudError as exc:
        st.warning(f"Tu sesión ha terminado: {exc}")
        if st.button('Volver a iniciar sesión'):
            _logout()
        st.stop()
_header()
_divider()
if st.session_state.get("analysis") is None:
    _selection_panel()
else:
    _render_active_page(st.session_state["analysis"])
_footer()
