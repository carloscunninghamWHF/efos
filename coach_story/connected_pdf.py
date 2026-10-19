"""One-page PDF showing precisely the diagnostic observations visible in EFOS.

Unlike the older coach PDF, it never imports season-wide prescriptive claims.
"""
from __future__ import annotations
from io import BytesIO
from xml.sax.saxutils import escape


def build_connected_pdf(diagnosis: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    from reportlab.lib.enums import TA_LEFT
    buf=BytesIO()
    paper=colors.HexColor('#10171D');accent=colors.HexColor('#B58C4F');muted=colors.HexColor('#53606B')
    doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=44,leftMargin=44,topMargin=45,bottomMargin=45)
    styles={
        'brand':ParagraphStyle('brand',fontName='Helvetica-Bold',fontSize=12,textColor=accent,spaceAfter=20),
        'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=21,leading=25,textColor=paper,spaceAfter=12),
        'body':ParagraphStyle('body',fontName='Helvetica',fontSize=10.5,leading=16,textColor=paper,spaceAfter=12),
        'head':ParagraphStyle('head',fontName='Helvetica-Bold',fontSize=12,leading=16,textColor=paper,spaceBefore=16,spaceAfter=6),
        'muted':ParagraphStyle('muted',fontName='Helvetica',fontSize=9,leading=13,textColor=muted,spaceAfter=7),
    }
    games=diagnosis.get('matches')
    descriptor=(f"{games} {'partido' if games==1 else 'partidos'}" if games is not None else 'muestra no identificada')
    items=[Paragraph('EFOS  /  FOOTBALL INTELLIGENCE',styles['brand']),
        Paragraph(escape(str(diagnosis.get('team','Equipo')))+' · diagnóstico táctico',styles['title']),
        Paragraph(f'Muestra: {descriptor} · métricas observadas, no causalidad',styles['muted']),
        Paragraph(escape(str(diagnosis.get('lead',''))),styles['body'])]
    for f in (diagnosis.get('findings') or [])[:3]:
        items.append(KeepTogether([
            Paragraph(escape(str(f.get('title',''))),styles['head']),
            Paragraph(escape(str(f.get('text',''))),styles['body']),
            Paragraph('PARA VERIFICAR  '+escape(str(f.get('meaning',''))),styles['muted']),
            Paragraph('Base: '+escape(str(f.get('scope',''))),styles['muted'])]))
    items.append(Spacer(1,12))
    items.append(Paragraph(escape(str(diagnosis.get('limit',''))),styles['muted']))
    doc.build(items)
    return buf.getvalue()
