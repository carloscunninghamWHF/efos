"""Visual PDF report for EFOS Coach Story.

The PDF is the formal, coach-facing deliverable. It translates EFOS metrics into
an executive narrative while preserving methodological traceability.
"""
from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Any
import math
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, PageBreak, Flowable, HRFlowable,
)

# Corporate visual language shared with the Streamlit portal.
NAVY = colors.HexColor("#0F172A")
NAVY_2 = colors.HexColor("#172554")
BLUE = colors.HexColor("#1D4ED8")
BLUE_SOFT = colors.HexColor("#EFF6FF")
TEAL = colors.HexColor("#0F766E")
GREEN = colors.HexColor("#166534")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")
INK = colors.HexColor("#0F172A")
TEXT = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
SURFACE = colors.HexColor("#F8FAFC")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN_X = 16 * mm
MARGIN_TOP = 18 * mm
MARGIN_BOTTOM = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

DIM_LABELS = {
    "OC": "Organización colectiva",
    "HPS": "Estabilidad bajo presión",
    "RPS": "Respuesta ante riesgo",
    "DS": "Estabilidad de decisión",
    "DER": "Respuesta tras pérdida",
}
DTC_LABELS = {
    "stability": "Control",
    "adaptation": "Recuperación / adaptación",
    "tension": "Presión creciente",
    "fragility": "Inestabilidad",
    "collapse": "Ruptura estructural",
}


def _safe_text(value: Any) -> str:
    """Normalize symbols unsupported by Helvetica while retaining Spanish text."""
    if value is None:
        return "N/A"
    s = str(value)
    replacements = {
        "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "≈": "~",
        "–": "-", "—": "-", "…": "...", "·": " | ", "×": "x",
        "′": "'", "“": '"', "”": '"', "’": "'", "‑": "-",
        "🛡": "", "⚠": "", "↗": "", "ⓘ": "",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    # remove control chars; keep Latin-1 characters supported by Helvetica.
    s = "".join(ch for ch in s if ch in "\n\t" or ord(ch) >= 32)
    return s


def _p(text: Any, style: ParagraphStyle) -> Paragraph:
    # Escape XML-ish characters used by ReportLab Paragraph markup.
    s = _safe_text(text)
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(s, style)


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        return f"{float(value):.{digits}f}{suffix}"
    except Exception:
        return _safe_text(value)


def _pct(value: Any, digits: int = 1) -> str:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        return f"{100 * float(value):.{digits}f}%"
    except Exception:
        return "N/A"


def _per_match(value: Any) -> str:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "N/A"
        return f"{float(value):.1f}/partido"
    except Exception:
        return "N/A"


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


class ScoreBar(Flowable):
    """Compact horizontal 0-100 score bar with label and score."""
    def __init__(self, label: str, score: float, width: float = CONTENT_W, height: float = 11*mm):
        super().__init__()
        self.label = _safe_text(label)
        self.score = max(0.0, min(100.0, float(score or 0)))
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        label_w = 62 * mm
        score_w = 18 * mm
        bar_x = label_w
        bar_w = max(20 * mm, self.width - label_w - score_w)
        y = self.height / 2 - 2
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(INK)
        c.drawString(0, y-1.5, self.label[:42])
        c.setFillColor(colors.HexColor("#E8EDF5"))
        c.roundRect(bar_x, y-1, bar_w, 5, 2.5, fill=1, stroke=0)
        c.setFillColor(BLUE)
        c.roundRect(bar_x, y-1, bar_w * self.score/100.0, 5, 2.5, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(INK)
        c.drawRightString(self.width, y-2, f"{self.score:.1f}")


class MiniBar(Flowable):
    """Share bar for percentages 0-1."""
    def __init__(self, label: str, rate: float, width: float = CONTENT_W, height: float = 9*mm, color=TEAL):
        super().__init__()
        self.label = _safe_text(label)
        self.rate = max(0.0, min(1.0, float(rate or 0)))
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        c = self.canv
        label_w = 65 * mm
        score_w = 18 * mm
        bar_w = self.width - label_w - score_w
        y = self.height/2 - 1
        c.setFont("Helvetica", 8.2)
        c.setFillColor(TEXT)
        c.drawString(0, y-1.5, self.label[:46])
        c.setFillColor(colors.HexColor("#E8EDF5"))
        c.roundRect(label_w, y-1, bar_w, 4.5, 2.2, fill=1, stroke=0)
        c.setFillColor(self.color)
        c.roundRect(label_w, y-1, bar_w*self.rate, 4.5, 2.2, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(INK)
        c.drawRightString(self.width, y-2, f"{100*self.rate:.1f}%")


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle("cover_kicker", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.HexColor("#BFDBFE"), spaceAfter=3),
        "cover_title": ParagraphStyle("cover_title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=28, leading=31, textColor=WHITE, spaceAfter=7),
        "cover_sub": ParagraphStyle("cover_sub", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15, textColor=colors.HexColor("#DBEAFE")),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=INK, spaceBefore=4, spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=INK, spaceBefore=12, spaceAfter=6),
        "eyebrow": ParagraphStyle("eyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=BLUE, spaceAfter=3),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.4, textColor=TEXT, spaceAfter=5),
        "body_small": ParagraphStyle("body_small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.8, leading=11, textColor=MUTED, spaceAfter=3),
        "body_white": ParagraphStyle("body_white", parent=base["BodyText"], fontName="Helvetica", fontSize=9.5, leading=14, textColor=WHITE),
        "metric_value": ParagraphStyle("metric_value", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=16, leading=18, textColor=INK, alignment=TA_LEFT),
        "metric_label": ParagraphStyle("metric_label", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=MUTED),
        "metric_note": ParagraphStyle("metric_note", parent=base["Normal"], fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
        "table_head": ParagraphStyle("table_head", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=WHITE),
        "table_cell": ParagraphStyle("table_cell", parent=base["Normal"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=TEXT),
        "table_cell_bold": ParagraphStyle("table_cell_bold", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=INK),
        "question": ParagraphStyle("question", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=colors.HexColor("#1E3A8A")),
        "limitation": ParagraphStyle("limitation", parent=base["BodyText"], fontName="Helvetica", fontSize=7.6, leading=10.5, textColor=MUTED, leftIndent=8),
        "center": ParagraphStyle("center", parent=base["Normal"], fontName="Helvetica", fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER),
    }


def _metric_card(label: str, value: str, note: str, styles: dict, width: float) -> Table:
    data = [[_p(label.upper(), styles["metric_label"])], [_p(value, styles["metric_value"])], [_p(note, styles["metric_note"])]]
    t = Table(data, colWidths=[width], rowHeights=[7*mm, 9*mm, 8*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), WHITE),
        ("BOX", (0,0), (-1,-1), .7, LINE),
        ("LEFTPADDING", (0,0), (-1,-1), 9), ("RIGHTPADDING", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def _section_header(title: str, subtitle: str, styles: dict) -> list:
    return [Spacer(1, 3*mm), _p(title, styles["h1"]), _p(subtitle, styles["body_small"]), HRFlowable(width="100%", thickness=.7, color=LINE, spaceBefore=2, spaceAfter=8)]


def _claim_box(title: str, text: str, styles: dict, bg=BLUE_SOFT, border=colors.HexColor("#BFDBFE")) -> Table:
    dark = bg in (NAVY, NAVY_2)
    title_style = styles["cover_kicker"] if dark else styles["eyebrow"]
    body_style = styles["body_white"] if dark else styles["body"]
    content = [[_p(title.upper(), title_style)], [_p(text, body_style)]]
    t = Table(content, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("BOX", (0,0), (-1,-1), .8, border),
        ("LEFTPADDING", (0,0), (-1,-1), 12), ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    return t


def _on_page(canvas, doc):
    canvas.saveState()
    # thin top rule
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(.5)
    canvas.line(MARGIN_X, PAGE_H-11*mm, PAGE_W-MARGIN_X, PAGE_H-11*mm)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.setFillColor(INK)
    canvas.drawString(MARGIN_X, PAGE_H-8*mm, "EFOS | DECISION INTELLIGENCE")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W-MARGIN_X, PAGE_H-8*mm, f"Coach Story | Página {doc.page}")
    canvas.line(MARGIN_X, 10*mm, PAGE_W-MARGIN_X, 10*mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN_X, 6.5*mm, "EFOS convierte eventos en interpretación táctica auditable. No sustituye video, scouting ni juicio del staff.")
    canvas.restoreState()


def _nested(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def build_coach_story_pdf(result: dict, output_path: Path | str | None = None) -> bytes:
    """Return PDF bytes and optionally persist them to ``output_path``."""
    story = result.get("coach_story", {}) or {}
    evidence = result.get("evidence", {}) or {}
    styles = _styles()
    buf = BytesIO()

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=_safe_text(story.get("title", "EFOS Coach Story")),
        author="EFOS",
        subject="Coach Story - Decision Intelligence",
    )
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H-MARGIN_TOP-MARGIN_BOTTOM, id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=_on_page))

    team = story.get("team") or result.get("focal_team") or "Equipo"
    meta = story.get("analysis_metadata", {}) or {}
    dims = _nested(story, "system_identity", "dimensions", default={}) or result.get("esi_dimensions", {}) or {}
    esi = float(result.get("ESI", _nested(story, "system_identity", "ESI", default=_nested(story, "system_identity", "esi", default=0))) or 0)
    pressure = story.get("pressure_resistance", {}) or {}
    pci = float(_nested(pressure, "mean_pci_hps_actions", default=_nested(pressure, "mean_pci_all_context_actions", default=result.get("pressure_summary", {}).get("mean_pci", 0))) or 0)
    n_matches = int(meta.get("matches_analyzed", 0) or 0)
    n_events = int(meta.get("team_events", 0) or 0)

    elements = []

    # COVER / EXECUTIVE SUMMARY
    cover = Table([
        [_p("EFOS | COACH STORY", styles["cover_kicker"])],
        [_p(team, styles["cover_title"])],
        [_p(f"Decision Intelligence Report | {n_matches} partidos | {n_events:,} acciones", styles["cover_sub"])],
    ], colWidths=[CONTENT_W])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("LEFTPADDING", (0,0), (-1,-1), 18), ("RIGHTPADDING", (0,0), (-1,-1), 18),
        ("TOPPADDING", (0,0), (-1,0), 14), ("BOTTOMPADDING", (0,-1), (-1,-1), 16),
    ]))
    elements += [Spacer(1, 4*mm), cover, Spacer(1, 8*mm)]

    card_w = (CONTENT_W - 9*mm)/4
    cards = [
        _metric_card("Identidad del sistema", f"{esi:.0f} / 100", "EFOS System Identity Index", styles, card_w),
        _metric_card("Estabilidad bajo presión", _level_100(float(dims.get("HPS",0))), f"{float(dims.get('HPS',0)):.1f}/100", styles, card_w),
        _metric_card("Presión contextual", _pressure_level(pci), f"PCI medio {pci:.3f}", styles, card_w),
        _metric_card("Respuesta ante riesgo", _level_100(float(dims.get("RPS",0))), f"{float(dims.get('RPS',0)):.1f}/100", styles, card_w),
    ]
    ct = Table([cards], colWidths=[card_w]*4, hAlign="LEFT")
    ct.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elements += [ct, Spacer(1, 7*mm)]

    executive = story.get("executive_summary", {}) or {}
    narrative = executive.get("narrative") or story.get("conclusion") or "Sin narrativa disponible."
    elements += [_claim_box("Lectura ejecutiva", narrative, styles, bg=NAVY, border=NAVY)]
    key_q = executive.get("key_question")
    if key_q:
        elements += [Spacer(1, 4*mm), _claim_box("Pregunta que deja la muestra", key_q, styles)]

    # Three ideas
    elements += _section_header("La historia en tres ideas", "Qué debería recordar el staff antes de entrar al detalle técnico.", styles)
    system = story.get("system_identity", {}) or {}
    strong = system.get("strongest_relative", "RPS"); weak = system.get("weakest_relative", "OC")
    dynamic = story.get("dynamic_states", {}) or {}
    change_claim = _nested(dynamic, "claims", default=[])
    change_text = change_claim[0].get("claim") if isinstance(change_claim, list) and change_claim else "EFOS segmenta los partidos para detectar cambios de comportamiento."
    insight_w = (CONTENT_W - 6*mm)/3
    insights = [
        ["FORTALEZA RELATIVA", DIM_LABELS.get(strong,strong), f"{float(dims.get(strong,0)):.1f}/100. Dimensión relativamente más alta de esta muestra."],
        ["SEÑAL A OBSERVAR", DIM_LABELS.get(weak,weak), f"{float(dims.get(weak,0)):.1f}/100. Mayor variación relativa dentro del perfil."],
        ["CAMBIO", "Momentos del partido", change_text],
    ]
    cells=[]
    for kicker,title,copy in insights:
        t=Table([[_p(kicker,styles["eyebrow"])],[_p(title,styles["metric_value"])],[_p(copy,styles["body_small"])]],colWidths=[insight_w])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WHITE),("BOX",(0,0),(-1,-1),.7,LINE),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
        cells.append(t)
    it=Table([cells],colWidths=[insight_w]*3)
    it.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),3),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elements += [it, PageBreak()]

    # IDENTITY
    elements += _section_header("1. Identidad del sistema", "Cinco dimensiones EFOS traducidas a comportamiento observable.", styles)
    for code in ["OC","HPS","RPS","DS","DER"]:
        elements.append(ScoreBar(DIM_LABELS[code], float(dims.get(code,0)), width=CONTENT_W))
    elements += [Spacer(1, 5*mm)]
    elements.append(_claim_box("Cómo leerlo", "Los valores son relativos al modelo y a la muestra analizada; todavía no constituyen un benchmark universal de liga. La comparación principal es entre dimensiones del propio equipo y entre periodos del mismo dataset.", styles, bg=SURFACE, border=LINE))

    # Context table
    ctx = story.get("contextual_behavior", {}) or {}
    ctx_rows = ctx.get("rows") or ctx.get("contexts") or []
    if isinstance(ctx_rows, list) and ctx_rows:
        elements += [_p("Identidad según contexto de marcador", styles["h2"])]
        headers=[_p(x,styles["table_head"]) for x in ["Contexto","n","ESI","OC","HPS","RPS","DS","DER"]]
        rows=[headers]
        for r in ctx_rows[:6]:
            rows.append([
                _p({"winning":"Ganando","drawing":"Empate","losing":"Perdiendo"}.get(str(r.get("context",r.get("game_state",r.get("score_state","-")))), r.get("context",r.get("game_state",r.get("score_state","-")))),styles["table_cell_bold"]),
                _p(r.get("n",r.get("windows",r.get("n_events","-"))),styles["table_cell"]),
                _p(_fmt(r.get("ESI")),styles["table_cell"]), _p(_fmt(r.get("OC")),styles["table_cell"]),
                _p(_fmt(r.get("HPS")),styles["table_cell"]), _p(_fmt(r.get("RPS")),styles["table_cell"]),
                _p(_fmt(r.get("DS")),styles["table_cell"]), _p(_fmt(r.get("DER")),styles["table_cell"]),
            ])
        t=Table(rows,colWidths=[34*mm,14*mm]+[18.5*mm]*6,repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("GRID",(0,0),(-1,-1),.4,LINE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        elements.append(t)

    # WITHOUT BALL
    elements += _section_header("2. Sin balón", "Presión, altura de intervención y mecanismos compatibles con control defensivo.", styles)
    tf = story.get("tactical_framework", {}) or {}
    defensive = tf.get("defensive_profile", {}) or {}
    h = defensive.get("defensive_action_height", {}) or {}
    cp = defensive.get("counterpress", {}) or {}
    hp = defensive.get("high_press_share", {}) or {}
    opp = defensive.get("opponent_passes_under_pressure", {}) or {}
    offside = defensive.get("opponent_offside_outcomes", {}) or {}
    dw=(CONTENT_W-8*mm)/5
    d_cards=[
        _metric_card("Altura intervención", f"x={_fmt(h.get('value'),1)}", h.get("band") or "acciones defensivas", styles,dw),
        _metric_card("Counterpress", _per_match(cp.get("per_match")), "acciones defensivas", styles,dw),
        _metric_card("Presión alta", _pct(hp.get("rate")), "Pressure events x>=80", styles,dw),
        _metric_card("Pases rivales presionados", _pct(opp.get("rate")), "share under_pressure", styles,dw),
        _metric_card("Offside rival", _per_match(offside.get("per_match")), "proxy de profundidad", styles,dw),
    ]
    dt=Table([d_cards],colWidths=[dw]*5)
    dt.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP")]))
    elements += [dt, Spacer(1,5*mm)]
    if hp.get("rate") is not None: elements.append(MiniBar("Pressure events en bloque alto (x>=80)",hp.get("rate"),width=CONTENT_W,color=BLUE))
    if opp.get("rate") is not None: elements.append(MiniBar("Pases rivales etiquetados bajo presión",opp.get("rate"),width=CONTENT_W,color=TEAL))
    claims = tf.get("claims", []) if isinstance(tf,dict) else []
    for cid in ["tactical_defensive_height","tactical_pressing_profile","tactical_offside_proxy"]:
        c = next((x for x in claims if x.get("id")==cid),None)
        if c:
            elements += [Spacer(1,2*mm), _claim_box("Lectura EFOS", c.get("claim",""), styles, bg=SURFACE, border=LINE)]

    # WITH BALL
    elements += _section_header("3. Con balón", "Cómo atrae presión, progresa y ocupa zonas interiores.", styles)
    build = tf.get("construction_progression", {}) or {}
    offensive = tf.get("offensive_microconcepts", {}) or {}
    value = tf.get("value_purpose", {}) or {}
    metrics = [
        ("Pases completos bajo presión", _per_match(_nested(build,"pressure_attraction_passes","per_match")), "Fishing proxy EVENT"),
        ("Liberación posterior", _pct(_nested(build,"pressure_release_success","rate")), "progresión tras presión"),
        ("Half-space", _per_match(_nested(build,"halfspace_entries","per_match")), "entradas por partido"),
        ("Combinaciones A→B→C", _per_match(_nested(build,"third_man_progression_proxy","per_match")), "proxy A->B->C"),
        ("Intervalo", _per_match(_nested(offensive,"interval_entries","per_match")), "central-lateral"),
        ("Centros zona peligrosa", _per_match(_nested(offensive,"cross_to_danger_zone_proxy","per_match")), "destino profundo configurado"),
    ]
    cw=(CONTENT_W-5*mm)/3
    for row in [metrics[:3],metrics[3:]]:
        cards=[_metric_card(a,b,c,styles,cw) for a,b,c in row]
        t=Table([cards],colWidths=[cw]*3)
        t.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),2),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP")]))
        elements.append(t)
    elements += [Spacer(1,4*mm)]
    xgpm = _nested(value,"xg","per_match",default=_nested(value,"xg_total","per_match"))
    obvpm = _nested(value,"obv","per_match",default=_nested(value,"obv_net","per_match",default=_nested(value,"obv_total_net","per_match")))
    if xgpm is not None or obvpm is not None:
        elements.append(_p("Propósito y valor", styles["h2"]))
        vrows=[[_p("xG generado / partido",styles["table_cell_bold"]),_p(_fmt(xgpm,3),styles["table_cell"])],[_p("OBV neto / partido",styles["table_cell_bold"]),_p(_fmt(obvpm,3),styles["table_cell"])]]
        vt=Table(vrows,colWidths=[60*mm,35*mm])
        vt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),SURFACE),("BOX",(0,0),(-1,-1),.5,LINE),("INNERGRID",(0,0),(-1,-1),.3,LINE),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        elements.append(vt)
    for cid in ["tactical_pressure_attraction","tactical_halfspace_thirdman","tactical_final_third_microconcepts"]:
        c = next((x for x in claims if x.get("id")==cid),None)
        if c:
            elements += [Spacer(1,2*mm), _claim_box("Interpretación", c.get("claim",""), styles, bg=SURFACE, border=LINE)]

    elements.append(PageBreak())

    # MOMENTS / DTC / EVOLUTION
    elements += _section_header("4. Cuándo cambia el equipo", "Momentos de control, presión creciente, inestabilidad y recuperación.", styles)
    dyn = story.get("dynamic_states", {}) or {}
    state_rows = dyn.get("distribution") or dyn.get("states") or dyn.get("state_distribution") or []
    if isinstance(state_rows, dict):
        parsed=[]
        for k,v in state_rows.items():
            if isinstance(v,dict):
                parsed.append({"state":k,"count":v.get("windows",v.get("count",0)),"share":(float(v.get("share_pct",0))/100.0 if v.get("share_pct") is not None else v.get("share"))})
            else:
                parsed.append({"state":k,"count":v})
        state_rows=parsed
    if isinstance(state_rows,list) and state_rows:
        total=sum(float(r.get("count",r.get("n",0)) or 0) for r in state_rows) or 1
        for r in state_rows:
            n=float(r.get("count",r.get("n",0)) or 0)
            rate=float(r.get("share", n/total) or 0)
            elements.append(MiniBar(DTC_LABELS.get(str(r.get("state")),str(r.get("state"))),rate,width=CONTENT_W,color=BLUE if rate>.15 else TEAL))
    elif dyn.get("claims"):
        elements.append(_claim_box("Lectura temporal", dyn["claims"][0].get("claim",""), styles, bg=SURFACE, border=LINE))

    temporal = story.get("temporal_evolution", {}) or {}
    phases = temporal.get("phases") or []
    if phases:
        elements += [_p("Evolución por bloques de la muestra", styles["h2"])]
        hdr=[_p(x,styles["table_head"]) for x in ["Fase","Partidos","ESI","OC","HPS","RPS","DS","DER"]]
        rows=[hdr]
        for r in phases:
            rows.append([_p(r.get("phase"),styles["table_cell_bold"]),_p(r.get("matches"),styles["table_cell"])] + [_p(_fmt(r.get(k)),styles["table_cell"]) for k in ["ESI","OC","HPS","RPS","DS","DER"]])
        tt=Table(rows,colWidths=[31*mm,18*mm]+[18*mm]*6,repeatRows=1)
        tt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("GRID",(0,0),(-1,-1),.4,LINE),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        elements.append(tt)
        if temporal.get("claims"):
            elements += [Spacer(1,3*mm), _claim_box("Evolución", temporal["claims"][0].get("claim",""), styles, bg=SURFACE, border=LINE)]

    # SIGNATURE / PRINCIPLES
    elements += _section_header("5. Firma táctica del entrenador", "Síntesis de patrones recurrentes; describe comportamiento observado, no intención demostrada.", styles)
    sig = story.get("coach_tactical_signature", {}) or {}
    sig_interp = story.get("coach_tactical_signature_interpretation", {}) or {}
    if sig:
        for k,v in sig.items():
            if isinstance(v,(int,float)) and not (isinstance(v,float) and math.isnan(v)):
                score = float(v)*100 if 0 <= float(v) <= 1 else float(v)
                if 0 <= score <= 100:
                    elements.append(ScoreBar(k.replace("_"," ").title(),score,width=CONTENT_W))
    if sig_interp.get("claims"):
        elements += [Spacer(1,3*mm), _claim_box("Lectura CTS", sig_interp["claims"][0].get("claim",""), styles, bg=BLUE_SOFT, border=colors.HexColor("#BFDBFE"))]

    principles = story.get("coach_principles", []) or []
    if principles:
        elements += [_p("Principios candidatos con mayor evidencia", styles["h2"])]
        hdr=[_p(x,styles["table_head"]) for x in ["Principio","Valor","n","Fuente"]]
        rows=[hdr]
        for r in principles[:8]:
            rows.append([_p(r.get("display_name",r.get("principle")),styles["table_cell_bold"]),_p(_fmt(r.get("value_pct"),1,"%"),styles["table_cell"]),_p(r.get("evidence_n"),styles["table_cell"]),_p(r.get("source"),styles["table_cell"])])
        pt=Table(rows,colWidths=[92*mm,22*mm,18*mm,38*mm],repeatRows=1)
        pt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("GRID",(0,0),(-1,-1),.4,LINE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        elements.append(pt)

    elements.append(PageBreak())

    # EVIDENCE / METHOD
    elements += _section_header("6. Evidencia y confianza", "Cada conclusión EFOS debe poder recorrerse hacia atrás hasta el dato original.", styles)
    ev_claims = evidence.get("claims", []) if isinstance(evidence,dict) else []
    if ev_claims:
        conf=Counter(str(c.get("confidence","N/A")).upper() for c in ev_claims)
        src=Counter(str(c.get("source","N/A")) for c in ev_claims)
        ew=(CONTENT_W-6*mm)/3
        ecards=[
            _metric_card("Claims auditables", str(len(ev_claims)), "evidence.json", styles, ew),
            _metric_card("Confianza alta", str(conf.get("HIGH",0)), "claims con evidencia directa", styles, ew),
            _metric_card("Fuentes distintas", str(len(src)), "EVENT / PROXY / engines", styles, ew),
        ]
        et=Table([ecards],colWidths=[ew]*3)
        et.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),2),("VALIGN",(0,0),(-1,-1),"TOP")]))
        elements.append(et)
        elements += [_p("Muestra de claims auditables", styles["h2"])]
        hdr=[_p(x,styles["table_head"]) for x in ["Conclusión","Fuente","n","Confianza"]]
        rows=[hdr]
        for c in ev_claims[:10]:
            rows.append([_p(c.get("claim",c.get("id")),styles["table_cell"]),_p(c.get("source"),styles["table_cell"]),_p(c.get("n"),styles["table_cell"]),_p(c.get("confidence"),styles["table_cell_bold"])])
        etab=Table(rows,colWidths=[99*mm,33*mm,16*mm,25*mm],repeatRows=1)
        etab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("GRID",(0,0),(-1,-1),.35,LINE),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        elements.append(etab)

    elements += _section_header("7. Conclusión", "Qué sistema parece estar construyendo la muestra.", styles)
    elements.append(_claim_box("Síntesis EFOS", story.get("conclusion", "Sin conclusión disponible."), styles, bg=NAVY, border=NAVY))

    limitations = story.get("limitations", []) or []
    elements += [_p("Límites metodológicos", styles["h2"])]
    for lim in limitations:
        elements.append(_p("- " + _safe_text(lim), styles["limitation"]))

    # Method metadata
    elements += [_p("Ficha de análisis", styles["h2"])]
    source_files = meta.get("source_files") or result.get("input_metadata",{}).get("source_files") or []
    rows = [
        ("Equipo focal", team),
        ("Partidos analizados", n_matches),
        ("Eventos del equipo", f"{n_events:,}"),
        ("Archivos consolidados", meta.get("files_loaded", len(source_files) or 1)),
        ("Frames 360", meta.get("frames360_loaded", result.get("frames360_loaded",0))),
        ("Perfil de fórmulas", meta.get("formula_profile", "EFOS_v0.4.5_PDF_CoachStory")),
    ]
    ft=Table([[_p(k,styles["table_cell_bold"]),_p(v,styles["table_cell"])] for k,v in rows],colWidths=[55*mm,115*mm])
    ft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),SURFACE),("BOX",(0,0),(-1,-1),.5,LINE),("INNERGRID",(0,0),(-1,-1),.3,LINE),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    elements.append(ft)

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(pdf_bytes)
    return pdf_bytes
