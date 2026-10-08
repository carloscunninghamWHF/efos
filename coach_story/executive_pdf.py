"""Informe ejecutivo EFOS de una página para cuerpo técnico / jurado."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

NAVY=colors.HexColor('#0F172A'); GOLD=colors.HexColor('#C89B3C'); BLUE=colors.HexColor('#2563EB')
MUTED=colors.HexColor('#64748B'); LINE=colors.HexColor('#E2E8F0'); SOFT=colors.HexColor('#F8FAFC')
GREEN=colors.HexColor('#166534'); RED=colors.HexColor('#B91C1C'); WHITE=colors.white


def _styles():
    s=getSampleStyleSheet()
    return {
      'k':ParagraphStyle('k',parent=s['Normal'],fontName='Helvetica-Bold',fontSize=7.5,textColor=GOLD,leading=9,spaceAfter=3),
      'h1':ParagraphStyle('h1',parent=s['Heading1'],fontName='Helvetica-Bold',fontSize=20,textColor=NAVY,leading=22,spaceAfter=3),
      'sub':ParagraphStyle('sub',parent=s['Normal'],fontSize=8.5,textColor=MUTED,leading=11),
      'h2':ParagraphStyle('h2',parent=s['Heading2'],fontName='Helvetica-Bold',fontSize=10.5,textColor=NAVY,leading=12,spaceAfter=3),
      'body':ParagraphStyle('body',parent=s['Normal'],fontSize=8.3,textColor=colors.HexColor('#334155'),leading=11),
      'small':ParagraphStyle('small',parent=s['Normal'],fontSize=7,textColor=MUTED,leading=9),
      'white':ParagraphStyle('white',parent=s['Normal'],fontName='Helvetica-Bold',fontSize=9,textColor=WHITE,leading=11),
      'whitebody':ParagraphStyle('whitebody',parent=s['Normal'],fontSize=8.2,textColor=WHITE,leading=10.5),
    }


def _box(title, body, styles, border=LINE, bg=WHITE):
    t=Table([[Paragraph(escape(title),styles['h2'])],[Paragraph(escape(body),styles['body'])]],colWidths=[86*mm])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),bg),('BOX',(0,0),(-1,-1),.7,border),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t


def build_executive_pdf(result: dict, context: dict | None=None, output_path: Path|str|None=None) -> bytes:
    context=context or {}
    fr=result.get('football_report') or {}; cp=result.get('coach_identity') or {}
    team=result.get('focal_team') or fr.get('equipo','Equipo')
    coach=context.get('coach') or 'DT no informado en catálogo'
    esi=float(result.get('ESI',0)); formation=(cp.get('estructura') or {}).get('dibujo_principal','—')
    matches=int((fr.get('ficha') or {}).get('partidos',0))
    strengths=fr.get('fortalezas') or [] ; weaknesses=fr.get('debilidades') or [] ; plan=fr.get('como_jugarle') or []
    story=(fr.get('textos') or {}).get('entrenador') or (result.get('coach_story') or {}).get('conclusion','')
    buf=BytesIO(); styles=_styles()
    doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=12*mm,rightMargin=12*mm,topMargin=10*mm,bottomMargin=10*mm,title=f'EFOS Informe Ejecutivo — {team}',author='EFOS')
    E=[]
    # Header
    head=Table([[Paragraph('EFOS · DECISION INTELLIGENCE',styles['k'])],[Paragraph(escape(team),styles['h1'])],[Paragraph(escape(f'{context.get("league","Liga")} · {context.get("season","Temporada")} · {context.get("period","Muestra")} · {matches} partidos'),styles['sub'])]],colWidths=[186*mm])
    head.setStyle(TableStyle([('BOTTOMPADDING',(0,0),(-1,-1),1)])); E += [head,Spacer(1,3*mm)]
    # Coach / formation / ESI
    cards=[]
    for title,val,note in [('Director técnico',coach,'Metadato documentado'),('Esquema base',formation,'Dibujo inicial más frecuente'),('Estabilidad global',f'{esi:.1f} / 100','Engine Stability Index (ESI)')]:
        tt=Table([[Paragraph(escape(title.upper()),styles['k'])],[Paragraph(escape(val),styles['h2'])],[Paragraph(escape(note),styles['small'])]],colWidths=[60*mm])
        tt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SOFT),('BOX',(0,0),(-1,-1),.6,LINE),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); cards.append(tt)
    ct=Table([cards],colWidths=[62*mm]*3); ct.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),2)])); E += [ct,Spacer(1,4*mm)]
    # Hero story
    hero=Table([[Paragraph('COACH STORY · EN 30 SEGUNDOS',styles['k'])],[Paragraph(escape(story[:900]),styles['whitebody'])]],colWidths=[186*mm])
    hero.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAVY),('BOX',(0,0),(-1,-1),.8,NAVY),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])); E += [hero,Spacer(1,4*mm)]
    def text_items(items, fallback):
        if not items:return fallback
        return ' · '.join([f"{x.get('titulo','')}: {x.get('dato','')}" for x in items[:2]])
    left=_box('Fortalezas principales',text_items(strengths,'Sin fortaleza diferencial suficiente en la muestra.'),styles,border=colors.HexColor('#BBF7D0'),bg=colors.HexColor('#F0FDF4'))
    right=_box('Vulnerabilidades clave',text_items(weaknesses,'No aparece una vulnerabilidad diferencial clara frente a sus rivales.'),styles,border=colors.HexColor('#FECACA'),bg=colors.HexColor('#FEF2F2'))
    row=Table([[left,right]],colWidths=[92*mm,92*mm]); row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),2)])); E += [row,Spacer(1,3*mm)]
    E += [_box('Plan de partido · cómo jugarle',' · '.join(plan[:3]) if plan else 'La muestra no ofrece una vía de ataque claramente diferencial.',styles,border=colors.HexColor('#BFDBFE'),bg=colors.HexColor('#EFF6FF')),Spacer(1,3*mm)]
    # Evidence footer
    claims=(result.get('evidence') or {}).get('claims',[])
    note=(f"Trazabilidad: {len(claims)} afirmaciones auditables. Cada lectura puede recorrerse desde el Coach Story hasta la métrica y el evento original. "
          "Los proxies se etiquetan como tales y no sustituyen la revisión en vídeo.")
    E += [Paragraph(note,styles['small'])]
    doc.build(E)
    pdf=buf.getvalue()
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True,exist_ok=True); Path(output_path).write_bytes(pdf)
    return pdf
