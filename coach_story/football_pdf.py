"""EFOS — PDF «Informe para cuerpo técnico».

Mismo lenguaje visual que el Coach Story PDF (coach_story/pdf_report.py), pero
organizado por momentos del juego y escrito en lenguaje de vestuario. Incluye
un campo con la posición media del once más utilizado.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from coach_story.football_report import GLOSSARY, POSITION_ES
from coach_story.pdf_report import (
    BLUE, CONTENT_W, GREEN, LINE, MARGIN_BOTTOM, MARGIN_TOP, MARGIN_X, MUTED, NAVY, PAGE_H, RED, SURFACE,
    INK, LINE as _LINE, PAGE_W, WHITE, _claim_box, _metric_card, _p, _section_header, _styles,
)

GREEN_SOFT = colors.HexColor("#F0FDF4")
RED_SOFT = colors.HexColor("#FEF2F2")
PITCH = colors.HexColor("#F1F5F9")


def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE); canvas.setLineWidth(.5)
    canvas.line(MARGIN_X, PAGE_H - 11 * mm, PAGE_W - MARGIN_X, PAGE_H - 11 * mm)
    canvas.setFont("Helvetica-Bold", 7); canvas.setFillColor(INK)
    canvas.drawString(MARGIN_X, PAGE_H - 8 * mm, "EFOS | INFORME PARA CUERPO TÉCNICO")
    canvas.setFont("Helvetica", 7); canvas.setFillColor(MUTED)
    canvas.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 8 * mm, f"Página {doc.page}")
    canvas.line(MARGIN_X, 10 * mm, PAGE_W - MARGIN_X, 10 * mm)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawString(MARGIN_X, 6.5 * mm, "EFOS resume lo que muestran los datos de eventos. No sustituye al vídeo ni al criterio del cuerpo técnico.")
    canvas.restoreState()


def _box(title: str, items: list[str], styles, bg, border, bold_titles: list[str] | None = None) -> Table:
    """Recuadro con viñetas; el texto se escapa aquí y solo se añade el formato propio."""
    lines = []
    for i, it in enumerate(items):
        head = f"<b>{escape(bold_titles[i])}</b>: " if bold_titles else ""
        lines.append(Paragraph("· " + head + escape(it), styles["body"]))
    data = [[_p(title.upper(), styles["eyebrow"])]] + [[x] for x in lines]
    t = Table(data, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("BOX", (0, 0), (-1, -1), .8, border),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


PARTICLES = {"de", "del", "dos", "da", "das", "la", "las", "los", "van", "von", "di"}


def _shirt_name(full: str) -> str:
    """Apellido «de camiseta» aproximado: agrupa partículas (Del Castillo, dos Santos)."""
    toks, groups = str(full).split(), []
    i = 0
    while i < len(toks):
        if toks[i].lower() in PARTICLES and i + 1 < len(toks):
            groups.append(toks[i] + " " + toks[i + 1]); i += 2
        else:
            groups.append(toks[i]); i += 1
    if len(groups) <= 2:
        return groups[-1]
    return groups[1] if len(groups) == 3 else groups[2]


def _pitch_positions(pos: pd.DataFrame, width: float) -> Drawing:
    """Campo 105×68 con el once más utilizado en su posición media con balón (ataca hacia la derecha)."""
    L, W = 105.0, 68.0
    s = width / L
    h = W * s
    d = Drawing(width, h + 8)
    oy = 8
    line = colors.HexColor("#94A3B8")
    d.add(Rect(0, oy, L * s, W * s, fillColor=PITCH, strokeColor=line, strokeWidth=0.8))
    d.add(Line(L / 2 * s, oy, L / 2 * s, oy + W * s, strokeColor=line, strokeWidth=0.6))
    d.add(Circle(L / 2 * s, oy + W / 2 * s, 9.15 * s, fillColor=None, strokeColor=line, strokeWidth=0.6))
    for x0 in (0, L - 16.5):
        d.add(Rect(x0 * s, oy + (W / 2 - 20.15) * s, 16.5 * s, 40.3 * s, fillColor=None, strokeColor=line, strokeWidth=0.6))
    d.add(String(L * s - 2, 1, "Dirección de ataque  →", fontName="Helvetica", fontSize=6.5, fillColor=MUTED, textAnchor="end"))
    for p in pos.dropna(subset=["x", "y"]).itertuples():
        x = min(max(p.x * 105 / 109.7, 2), L - 2) * s
        y = oy + (W - min(max(p.y * 68 / 73.15, 2), W - 2)) * s   # y StatsBomb crece hacia abajo
        d.add(Circle(x, y, 7, fillColor=NAVY, strokeColor=WHITE, strokeWidth=1))
        label = _shirt_name(p.player)
        d.add(String(x, y - 13, label, fontName="Helvetica-Bold", fontSize=6.3, fillColor=NAVY, textAnchor="middle"))
    return d


def _table(rows, widths, styles, head=True):
    data = [[_p(c, styles["table_head"] if (head and i == 0) else styles["table_cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), .35, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    t.setStyle(TableStyle(st))
    return t


def build_football_pdf(rep: dict, output_path: Path | str | None = None) -> bytes:
    styles = _styles()
    t, team, f = rep["textos"], rep["equipo"], rep["ficha"]
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=(CONTENT_W + 2 * MARGIN_X, PAGE_H), leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                          topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM, title=f"EFOS — Informe para cuerpo técnico — {team}",
                          author="EFOS")
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM, id="n",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame], onPage=_on_page))
    E = []

    cover = Table([[_p("EFOS | INFORME PARA CUERPO TÉCNICO", styles["cover_kicker"])], [_p(team, styles["cover_title"])],
                   [_p(f"{f['partidos']} partidos · todos los datos comparados con sus rivales en esos mismos partidos", styles["cover_sub"])]],
                  colWidths=[CONTENT_W])
    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("LEFTPADDING", (0, 0), (-1, -1), 18),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 18), ("TOPPADDING", (0, 0), (-1, 0), 14),
                               ("BOTTOMPADDING", (0, -1), (-1, -1), 16)]))
    E += [Spacer(1, 4 * mm), cover, Spacer(1, 6 * mm)]
    if rep.get("aviso"):
        E += [_claim_box("Atención", rep["aviso"], styles, bg=RED_SOFT, border=RED), Spacer(1, 4 * mm)]

    cw = (CONTENT_W - 9 * mm) / 4
    cards = [_metric_card("Balance", f"{f['ganados']}G {f['empatados']}E {f['perdidos']}P", f"{f['puntos_por_partido']:.2f} puntos por partido", styles, cw),
             _metric_card("Goles", f"{f['goles']} - {f['goles_contra']}", f"esperados: {f['xg']:.0f} - {f['xg_contra']:.0f}", styles, cw)]
    est = rep.get("estructura") or {}
    if est.get("dibujo_principal"):
        cards.append(_metric_card("Dibujo habitual", est["dibujo_principal"], f"{est.get('dibujo_principal_pct', 0):.0f} % de los partidos", styles, cw))
    cards.append(_metric_card("Perfil", rep.get("perfil_tipo", "—"), rep.get("ejemplos", ""), styles, cw))
    ct = Table([cards], colWidths=[cw] * len(cards), hAlign="LEFT")
    ct.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
    E += [ct, Spacer(1, 6 * mm), _claim_box("El entrenador en pocas líneas", t["entrenador"], styles, bg=NAVY, border=NAVY),
          Spacer(1, 4 * mm), _p(t["ficha"], styles["body"])]

    # Conclusiones primero: es lo que lee un director deportivo
    E += _section_header("Conclusiones", "Fortalezas, puntos débiles y cómo jugarle.", styles)
    fx, dx = rep["fortalezas"], rep["debilidades"]
    E += [_box("Fortalezas", [f"{x['dato']} (rivales: {x['rivales']})" for x in fx], styles, GREEN_SOFT, GREEN, [x["titulo"] for x in fx]),
          Spacer(1, 3 * mm),
          _box(rep["debilidades_titulo"], [f"{x['dato']} (rivales: {x['rivales']})" for x in dx], styles,
               RED_SOFT if any(x.get("real", True) for x in dx) else colors.HexColor("#FFFBEB"),
               RED if any(x.get("real", True) for x in dx) else colors.HexColor("#F59E0B"), [x["titulo"] for x in dx]),
          Spacer(1, 3 * mm),
          _box("Cómo jugarle", rep["como_jugarle"], styles, colors.HexColor("#EFF6FF"), colors.HexColor("#BFDBFE")), Spacer(1, 3 * mm),
          _p(t["encaje"] + " " + t["regularidad"], styles["body"])]

    sections = [
        ("1. El entrenador", "Sistema, gestión del partido y del plantel.", [t["estructura"], t["gestion"], t["rotacion"]]),
        ("2. Ataque organizado", "Cómo construye y llega al área.", [t["ataque_organizado"]]),
        ("3. Transición defensiva", "Qué hace al perder el balón.", [t["transicion_defensiva"]]),
        ("4. Defensa organizada", "Altura, presión y ocasiones concedidas.", [t["defensa_organizada"]]),
        ("5. Transición ofensiva", "Qué hace al recuperar el balón.", [t["transicion_ofensiva"]]),
        ("6. Balón parado", "Córners, faltas y saques de banda.", [t["balon_parado"]]),
        ("7. Cómo reacciona", "Según el marcador y del primer al segundo tiempo.", [t["reaccion"], t["descanso"], t["momentos"]]),
    ]
    for title, sub, paras in sections:
        block = _section_header(title, sub, styles) + [_p(x, styles["body"]) for x in paras if x]
        E.append(KeepTogether(block))

    pos = rep["posiciones"]
    E += _section_header("8. Jugadores", "Once más utilizado en su posición media con balón.", styles)
    if len(pos) and pos[["x", "y"]].notna().all(axis=1).sum() >= 5:
        pitch = Table([[_pitch_positions(pos, CONTENT_W * 0.78)]], colWidths=[CONTENT_W])
        pitch.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        E += [pitch, Spacer(1, 3 * mm)]
        rows = [["Jugador", "Posición habitual", "Titular", "Altura (m)"]]
        for p in pos.sort_values("x", ascending=False).itertuples():
            rows.append([p.player, POSITION_ES.get(p.posicion, p.posicion), str(p.titularidades), f"{p.x:.0f}"])
        E.append(_table(rows, [70 * mm, 50 * mm, 22 * mm, 28 * mm], styles))
    if t["jugadores"]:
        E += [Spacer(1, 3 * mm), _p(t["jugadores"], styles["body"])]

    clips = rep["clips"]
    if len(clips):
        E += _section_header("9. Vídeo: jugadas para revisar", "Los mejores ejemplos de cada rasgo, para comprobarlo en vídeo.", styles)
        rows = [["", "Rasgo", "Rival", "Momento", "Protagonista", "Qué observar"]]
        for c in clips.itertuples():
            rows.append([c.tipo, c.rasgo, c.rival, f"{c.parte}ª parte, {c.minuto}", c.jugador, c.que_ver])
        E.append(_table(rows, [15 * mm, 30 * mm, 24 * mm, 19 * mm, 35 * mm, CONTENT_W - 123 * mm], styles))

    E += _section_header("Qué no dice este informe", "Límites que conviene tener presentes.", styles)
    for x in ["Describe lo que hizo el equipo; no sabe qué instrucciones dio el entrenador en el vestuario.",
              "No separa las decisiones del entrenador de la calidad de sus jugadores; si hubo cambio de entrenador, mezcla a ambos.",
              "Los datos no indican local o visitante, ni el torneo (Apertura, Clausura, Liguilla).",
              "Las «trampas de presión» y otros patrones avanzados siguen en fase experimental hasta validarlos con vídeo."]:
        E.append(_p("- " + x, styles["limitation"]))
    E += [Spacer(1, 4 * mm), _p("Glosario", styles["h2"]),
          _table([["En EFOS", "En el vestuario", "Qué significa"]] + [[k, v[0], v[1]] for k, v in GLOSSARY.items()],
                 [20 * mm, 45 * mm, CONTENT_W - 65 * mm], styles)]

    doc.build(E)
    pdf = buf.getvalue()
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(pdf)
    return pdf
