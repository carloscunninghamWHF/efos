"""EFOS v0.4.21: one-page PDF sharing the *same* evidence-first executive brief.

The historical full tactical PDF is not replaced by this module.
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from coach_story.executive_brief import build_executive_brief
from interpretation.tactical_reasoning import build_tactical_reasoning

NAVY = colors.HexColor('#101D30')
GOLD = colors.HexColor('#B28636')
INK = colors.HexColor('#1B2A40')
MUTED = colors.HexColor('#64748B')
LINE = colors.HexColor('#E1E5EC')
SOFT = colors.HexColor('#F7F8FA')
WHITE = colors.white


def _styles():
    ss = getSampleStyleSheet()
    return {
        'k': ParagraphStyle('efos_k', parent=ss['Normal'], fontName='Helvetica-Bold', fontSize=7,
                            textColor=GOLD, leading=9, spaceAfter=3),
        'head': ParagraphStyle('efos_head', parent=ss['Normal'], fontName='Helvetica-Bold', fontSize=18,
                               leading=21, textColor=INK, spaceAfter=4),
        'subtitle': ParagraphStyle('efos_sub', parent=ss['Normal'], fontSize=8, leading=11, textColor=MUTED),
        'body': ParagraphStyle('efos_body', parent=ss['Normal'], fontSize=9, leading=13.4,
                               textColor=INK),
        'small': ParagraphStyle('efos_small', parent=ss['Normal'], fontSize=7.8, leading=10.8,
                                textColor=MUTED),
        'cardhead': ParagraphStyle('efos_cardhead', parent=ss['Normal'], fontName='Helvetica-Bold',
                                   fontSize=8.5, leading=11, textColor=INK),
        'value': ParagraphStyle('efos_value', parent=ss['Normal'], fontName='Helvetica-Bold',
                                fontSize=16, leading=18, textColor=INK),
        'white': ParagraphStyle('efos_white', parent=ss['Normal'], fontSize=9.3, leading=14,
                                textColor=WHITE),
    }


def _p(text, style):
    return Paragraph(escape(str(text)), style)


def build_executive_pdf(result: dict, context: dict | None = None,
                        output_path: Path | str | None = None) -> bytes:
    context = context or {}
    brief = build_executive_brief(result)
    reasoning = result.get("tactical_reasoning") or build_tactical_reasoning(result)
    team = result.get('focal_team') or (result.get('football_report') or {}).get('equipo') or 'Equipo'
    events = result.get('events')
    # Do not conflate metadata for one file with actual current sample.
    if hasattr(events, 'columns') and {'team', 'match_id'}.issubset(events.columns):
        matches = int(events.loc[events['team'].eq(team), 'match_id'].nunique())
    else:
        matches = int(((result.get('football_report') or {}).get('ficha') or {}).get('partidos') or 0)
    meta = '  |  '.join(str(v) for v in (context.get('league'), context.get('season'),
                                          context.get('period'), f'{matches} partidos') if v)
    coach = context.get('coach') or 'DT no informado'
    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=11*mm,
                            title=f'EFOS | Informe Ejecutivo | {team}', author='EFOS')
    W = 182*mm
    elements = [
        _p('EFOS  /  INTELIGENCIA TÁCTICA', s['k']),
        _p('La historia táctica de ' + str(team), s['head']),
        _p(meta, s['subtitle']), Spacer(1, 3*mm),
    ]
    banner = Table([[_p('LA LECTURA DEL EQUIPO EN 30 SEGUNDOS', s['k'])],
                    [_p(reasoning['identity'] if reasoning['coverage'] else brief['story'], s['white'])]], colWidths=[W])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.extend([banner, Spacer(1, 4*mm)])
    elements += [_p('TRES SEÑALES PARA EL CUERPO TÉCNICO', s['k']), Spacer(1, 2*mm)]
    widths = [W/3] * 3
    cards = []
    for signal in brief['signals']:
        inner = Table([
            [_p(signal['section'], s['k'])],
            [_p(signal['headline'], s['cardhead'])],
            [_p(signal['value'], s['value'])],
            [_p(signal['caption'], s['small'])],
        ], colWidths=[widths[0] - 4*mm])
        inner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), SOFT),
            ('BOX', (0, 0), (-1, -1), 0.6, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ]))
        cards.append(inner)
    grid = Table([cards], colWidths=widths)
    grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0),
                              ('RIGHTPADDING', (0, 0), (-1, -1), 2)]))
    elements.extend([grid, Spacer(1, 5*mm)])
    # Evidence-oriented diagnosis drawn from the same canonical engine outputs.
    selected = [f for f in reasoning['findings'] if f['id'] in ('origen_y_productividad', 'situaciones_de_amenaza')]
    if selected:
        elements.extend([_p('LECTURA TÁCTICA CONECTADA', s['k']), Spacer(1, 1*mm)])
        for f in selected:
            elements.extend([_p(f['question'], s['cardhead']),
                             _p(f['interpretation'], s['small']),
                             _p('Revisar: ' + f['action'], s['small']), Spacer(1, 2*mm)])

    elements.extend([
        _p('LA PREGUNTA TÁCTICA', s['k']),
        _p(brief['conflict'], s['body']), Spacer(1, 3*mm),
        _p('QUÉ REVISAR DESPUÉS', s['k']),
        _p(brief['next_step'], s['body']), Spacer(1, 4*mm),
        _p('EVIDENCIA, COBERTURA Y LÍMITES', s['k']),
    ])
    for signal in brief['signals']:
        evidence_text = f"{signal['section']}: {signal['evidence']}. Límite: {signal['limitation']}"
        elements.extend([_p(evidence_text, s['small']), Spacer(1, 2*mm)])
    elements.extend([Spacer(1, 2*mm), _p(brief['disclaimer'], s['small']),
                     Spacer(1, 2*mm), _p('Director técnico (metadato): ' + str(coach), s['small'])])
    doc.build(elements)
    pdf = buf.getvalue()
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pdf)
    return pdf
