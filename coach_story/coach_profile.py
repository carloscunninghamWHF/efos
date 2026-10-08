"""EFOS — Perfil del entrenador a partir de datos de eventos.

Responde, para cualquier equipo, a «¿cómo es el entrenador que produjo estos datos?»:

  1. Estructura   -> dibujo habitual reconstruido con las posiciones de los titulares.
  2. Estilo       -> con balón, sin balón y en transición, frente a sus rivales.
  3. Reacciones   -> qué cambia según el marcador y del primer al segundo tiempo.
  4. Gestión      -> cuándo y cómo usa los cambios, retoques tácticos y rotación del once.
  5. Retrato      -> síntesis en lenguaje llano.

Solo necesita columnas estándar de eventos (team, match_id, event_type, period, minute,
player, player_position_name, location_x, pass_length, score_state). Si falta alguna, la
sección correspondiente se omite en lugar de inventarse.

Todo describe comportamiento observado del equipo bajo ese cuerpo técnico; no prueba
intención ni separa al entrenador de sus jugadores.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

LONG_PASS = 32.0
RIVAL_HALF_X = 60.0
DEF_ACTIONS = {"Pressure", "Ball Recovery", "Interception", "Duel", "Block"}
MIN_TEAM_EVENTS = 300          # mínimo de eventos del equipo para comparar un tramo
YARD_TO_M = 0.9144

# Posiciones StatsBomb agrupadas por línea (para reconstruir el dibujo)
DEFENCE = {"Right Back", "Left Back", "Right Center Back", "Left Center Back", "Center Back"}
WING_BACKS = {"Right Wing Back", "Left Wing Back"}
MIDFIELD = {"Right Defensive Midfield", "Left Defensive Midfield", "Center Defensive Midfield",
            "Right Center Midfield", "Left Center Midfield", "Center Center Midfield",
            "Right Midfield", "Left Midfield"}
PIVOTS = {"Right Defensive Midfield", "Left Defensive Midfield", "Center Defensive Midfield"}
CENTRAL_AM = {"Right Attacking Midfield", "Left Attacking Midfield", "Center Attacking Midfield"}
WINGS = {"Right Wing", "Left Wing"}
FORWARDS = {"Center Forward", "Right Center Forward", "Left Center Forward", "Secondary Striker"}

METRICS = {
    # clave: (etiqueta, unidad corta)
    "posesion": ("Posesión", "% de los pases"),
    "presion_alta": ("Presión en campo rival", "% de sus presiones"),
    "pase_largo": ("Pase largo", "% de sus pases"),
    "altura_bloque": ("Altura de su defensa", "m desde su portería"),
}
SCORE_LABELS = {"losing": "Perdiendo", "drawing": "Empatando", "winning": "Ganando"}


# --------------------------------------------------------------- utilidades
def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _abs_minute(df: pd.DataFrame) -> pd.Series:
    """Minuto de juego. StatsBomb ya da el minuto acumulado; si no, se suma 45 al 2T."""
    m = _num(df["minute"]) if "minute" in df else pd.Series(np.nan, index=df.index)
    if "period" in df and m.notna().any():
        p = _num(df["period"])
        second_half = p.eq(2)
        if second_half.any() and m[second_half].median() < 45:
            m = m.where(~second_half, m + 45)
    return m


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


# --------------------------------------------------- 1. estructura y once
def _starters(ev: pd.DataFrame, team: str) -> dict:
    """Titulares y su posición por partido (antes del primer cambio o retoque táctico)."""
    need = {"player", "player_position_name", "match_id"}
    if not need <= set(ev.columns):
        return {}
    t = ev[ev["team"].eq(team)].copy()
    t["_min"] = _abs_minute(t)
    period = _num(t["period"]) if "period" in t else pd.Series(1, index=t.index)
    out = {}
    for mid, g in t.groupby("match_id", sort=False):
        p1 = g[period.loc[g.index].eq(1)] if period.notna().any() else g
        cut_events = p1[p1["event_type"].isin(["Substitution", "Tactical Shift"])]
        cutoff = cut_events["_min"].min() if len(cut_events) else np.inf
        early = p1[(p1["_min"] < cutoff) & p1["player"].notna() & p1["player_position_name"].notna()]
        if early.empty:
            continue
        pos = early.groupby("player")["player_position_name"].agg(lambda s: s.value_counts().index[0])
        out[mid] = pos.to_dict()
    return out


def _formation(positions: list[str]) -> tuple[str, dict]:
    ps = [p for p in positions if p != "Goalkeeper"]
    d = sum(p in DEFENCE for p in ps)
    m = sum(p in MIDFIELD or p in WING_BACKS for p in ps)
    am = sum(p in CENTRAL_AM for p in ps)
    w = sum(p in WINGS for p in ps)
    f = sum(p in FORWARDS for p in ps)
    if am == 0:                    # sin mediapunta, los extremos forman la línea de ataque (4-3-3)
        f, w = f + w, 0
    lines = [d, m, am + w, f]
    shape = "-".join(str(n) for n in lines if n > 0)
    detail = {"defensas": d + sum(p in WING_BACKS for p in ps), "carrileros": sum(p in WING_BACKS for p in ps),
              "centrales": sum(p in {"Right Center Back", "Left Center Back", "Center Back"} for p in ps),
              "pivotes": sum(p in PIVOTS for p in ps), "delanteros_centro": sum(p in FORWARDS for p in ps)}
    return shape, detail


def structure_and_rotation(ev: pd.DataFrame, team: str) -> dict:
    starters = _starters(ev, team)
    if not starters:
        return {}
    shapes, details = [], []
    for pos in starters.values():
        if len(pos) >= 10:                     # once completo identificado
            s, det = _formation(list(pos.values()))
            shapes.append(s); details.append(det)
    freq = Counter(shapes)
    n = len(shapes)
    main, main_n = freq.most_common(1)[0] if freq else ("N/D", 0)
    centrals = Counter(d["centrales"] for d in details).most_common(1)[0][0] if details else None
    back_line = Counter(d["defensas"] for d in details).most_common(1)[0][0] if details else None
    pivots = Counter(d["pivotes"] for d in details).most_common(1)[0][0] if details else None
    strikers = Counter(d["delanteros_centro"] for d in details).most_common(1)[0][0] if details else None

    xis = [set(p) for p in starters.values()]
    changes = [len(b - a) for a, b in zip(xis[:-1], xis[1:])]
    starts = Counter(pl for xi in xis for pl in xi)
    core = sum(c for _, c in starts.most_common(11))
    return {
        "partidos_con_once": n,
        "dibujo_principal": main,
        "dibujo_principal_pct": 100 * main_n / n if n else 0.0,
        "dibujos": {k: int(v) for k, v in freq.most_common()},
        "n_dibujos": len(freq),
        "linea_defensiva": back_line, "centrales": centrals, "pivotes": pivots, "delanteros_centro": strikers,
        "titulares_distintos": len(starts),
        "cambios_en_once_por_partido": float(np.mean(changes)) if changes else None,
        "pct_titularidades_top11": 100 * core / sum(starts.values()) if starts else None,
    }


# ------------------------------------------------------- 2. métricas de estilo
def _segment_metrics(g: pd.DataFrame, team: str, rivals: bool = False) -> dict:
    """Métricas del equipo focal (o, con rivals=True, de sus rivales) dentro del tramo g."""
    me = g[~g["team"].eq(team)] if rivals else g[g["team"].eq(team)]
    all_passes = int(g["event_type"].eq("Pass").sum())
    passes = me[me["event_type"].eq("Pass")]
    press = me[me["event_type"].eq("Pressure")]
    defn = me[me["event_type"].isin(DEF_ACTIONS)]
    x_press = _num(press["location_x"]) if "location_x" in press else pd.Series(dtype=float)
    x_def = _num(defn["location_x"]) if "location_x" in defn else pd.Series(dtype=float)
    plen = _num(passes["pass_length"]) if "pass_length" in passes else pd.Series(dtype=float)
    return {
        "posesion": 100 * len(passes) / all_passes if all_passes else np.nan,
        "presion_alta": 100 * (x_press >= RIVAL_HALF_X).mean() if x_press.notna().any() else np.nan,
        "pase_largo": 100 * (plen >= LONG_PASS).mean() if plen.notna().any() else np.nan,
        "altura_bloque": float(x_def.median()) * YARD_TO_M if x_def.notna().any() else np.nan,
        "eventos_equipo": int(len(me)),
    }


def block_height_vs_rivals(ev: pd.DataFrame, team: str) -> dict:
    rows = []
    for mid, g in ev[ev["match_id"].isin(ev.loc[ev["team"].eq(team), "match_id"].unique())].groupby("match_id"):
        for tm in g["team"].dropna().unique():
            x = _num(g.loc[g["team"].eq(tm) & g["event_type"].isin(DEF_ACTIONS), "location_x"])
            if x.notna().any():
                rows.append({"focal": tm == team, "altura": float(x.median()) * YARD_TO_M})
    d = pd.DataFrame(rows)
    if d.empty or not d["focal"].any():
        return {}
    f, r = d.loc[d["focal"], "altura"], d.loc[~d["focal"], "altura"]
    sd = r.std()
    z = (f.mean() - r.mean()) / sd if sd and not np.isnan(sd) else 0.0
    return {"equipo": float(f.mean()), "rivales": float(r.mean()), "indice": float(np.clip(50 + 20 * z, 0, 100))}


FLIP = {"losing": "winning", "winning": "losing", "drawing": "drawing"}


def by_segment(ev: pd.DataFrame, team: str, column: str, values: list) -> pd.DataFrame:
    """Métricas por tramo. Incluye a los rivales en la MISMA situación como referencia
    (p. ej. «rivales perdiendo» = tramos en que el equipo focal va ganando)."""
    if column not in ev:
        return pd.DataFrame()
    ev = ev[ev["match_id"].isin(ev.loc[ev["team"].eq(team), "match_id"].unique())]
    rows = []
    for v in values:
        m = _segment_metrics(ev[ev[column].eq(v)], team)
        rv = FLIP.get(v, v) if column == "score_state" else v
        r = _segment_metrics(ev[ev[column].eq(rv)], team, rivals=True)
        m.update({f"rival_{k}": val for k, val in r.items()})
        m["segmento"] = v
        rows.append(m)
    d = pd.DataFrame(rows)
    d["fiable"] = d["eventos_equipo"] >= MIN_TEAM_EVENTS
    return d


# ------------------------------------------------------------- 3. gestión
def game_management(ev: pd.DataFrame, team: str) -> dict:
    t = ev[ev["team"].eq(team)].copy()
    matches = t["match_id"].nunique()
    if matches == 0 or "event_type" not in t:
        return {}
    t["_min"] = _abs_minute(t)
    subs = t[t["event_type"].eq("Substitution")].copy()
    shifts = t[t["event_type"].eq("Tactical Shift")]
    out = {"partidos": int(matches), "cambios_por_partido": len(subs) / matches,
           "retoques_tacticos_por_partido": len(shifts) / matches,
           "pct_partidos_con_retoque": 100 * shifts["match_id"].nunique() / matches}
    if len(subs) and subs["_min"].notna().any():
        first = subs.groupby("match_id")["_min"].min()
        out.update({
            "minutos_cambios": subs["_min"].dropna().round().astype(int).tolist(),
            "primer_cambio_mediana": float(first.median()),
            "pct_cambios_descanso": 100 * float(subs["_min"].between(45, 46.99).mean()),
            "pct_cambios_antes_60": 100 * float((subs["_min"] < 60).mean()),
            "pct_cambios_ultimos_15": 100 * float((subs["_min"] >= 75).mean()),
        })
        if "score_state" in subs:
            by_state = {}
            for st in ("losing", "drawing", "winning"):
                s = subs[subs["score_state"].eq(st)]
                if len(s):
                    by_state[st] = {"cambios": int(len(s)), "minuto_mediano": float(s["_min"].median())}
            out["cambios_segun_marcador"] = by_state
            f = subs.sort_values("_min").groupby("match_id").head(1)
            out["primer_cambio_segun_marcador"] = {
                st: float(f.loc[f["score_state"].eq(st), "_min"].median())
                for st in ("losing", "drawing", "winning") if f["score_state"].eq(st).any()}
    return out


# ----------------------------------------------------------- 4. narrativa
def _reaction_phrases(a: pd.Series, b: pd.Series, ra: pd.Series | None = None, rb: pd.Series | None = None,
                      rival_label: str = "") -> list[str]:
    """Frases sobre lo que cambia de la situación a a la b (b − a) y, si se dan, cuánto
    cambian sus rivales en la misma situación (rb − ra)."""
    out = []
    d = b - a
    rd = (rb - ra) if ra is not None and rb is not None else None

    def ref(k, unit):
        if rd is None or pd.isna(rd.get(k, np.nan)):
            return ""
        return f"; {rival_label} {rd[k]:+.0f}{unit}"

    if abs(d.get("posesion", 0)) >= 3:
        out.append(f"{'tiene más' if d['posesion'] > 0 else 'cede más'} el balón ({d['posesion']:+.0f} puntos de posesión{ref('posesion', '')})")
    if abs(d.get("presion_alta", 0)) >= 3:
        out.append(f"presiona {'más arriba' if d['presion_alta'] > 0 else 'más atrás'} ({d['presion_alta']:+.0f} puntos{ref('presion_alta', '')})")
    if abs(d.get("altura_bloque", 0)) >= 2:
        out.append(f"{'adelanta' if d['altura_bloque'] > 0 else 'retrasa'} su defensa {abs(d['altura_bloque']):.0f} m "
                   f"({d['altura_bloque']:+.0f} m{ref('altura_bloque', ' m')})")
    if abs(d.get("pase_largo", 0)) >= 2:
        out.append(f"{'recurre más' if d['pase_largo'] > 0 else 'recurre menos'} al pase largo ({d['pase_largo']:+.0f} puntos{ref('pase_largo', '')})")
    return out


def _intensity(d: pd.Series, rd: pd.Series) -> str:
    """Compara la magnitud del cambio del equipo con la de sus rivales."""
    keys = [k for k in METRICS if not pd.isna(d.get(k)) and not pd.isna(rd.get(k))]
    if not keys:
        return ""
    ratio = np.mean([abs(d[k]) - abs(rd[k]) for k in keys])
    if ratio >= 2:
        return "Reacciona con más intensidad que sus rivales en la misma situación: es un rasgo propio del entrenador."
    if ratio <= -2:
        return "Reacciona menos que sus rivales en la misma situación: mantiene su plan más que un equipo típico."
    return "Es una reacción de magnitud parecida a la de sus rivales en la misma situación, es decir, habitual en el fútbol."


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def _shape_sentence(s: dict) -> str:
    if not s:
        return ""
    parts = []
    if s.get("centrales") == 3:
        parts.append("defensa de tres centrales" + (" con carrileros" if s.get("linea_defensiva", 0) >= 5 else ""))
    elif s.get("linea_defensiva"):
        parts.append(f"línea de {s['linea_defensiva']} atrás")
    if s.get("pivotes") == 2:
        parts.append("doble pivote")
    elif s.get("pivotes") == 1:
        parts.append("un solo mediocentro defensivo")
    if s.get("delanteros_centro") == 1:
        parts.append("un único delantero centro")
    elif s.get("delanteros_centro", 0) >= 2:
        parts.append(f"{s['delanteros_centro']} delanteros centro")
    base = (f"Su dibujo más habitual es un {s['dibujo_principal']} "
            f"({s['dibujo_principal_pct']:.0f} % de los partidos; {_plural(s['n_dibujos'], 'dibujo')} distintos en total)")
    text = base + (": " + _join(parts) + "." if parts else ".")
    alts = [(k, v) for k, v in list(s["dibujos"].items())[1:] if v / max(s["partidos_con_once"], 1) >= 0.15]
    if alts:
        text += " Como alternativa recurre al " + _join([f"{k} ({_plural(v, 'partido')})" for k, v in alts]) + "."
    return text


def build_coach_profile(ev: pd.DataFrame, team: str, style: pd.DataFrame, fit: pd.DataFrame,
                        transition_rate: float | None = None) -> dict:
    n_matches = int(ev.loc[ev["team"].eq(team), "match_id"].nunique())
    shape = structure_and_rotation(ev, team)
    block = block_height_vs_rivals(ev, team)
    score = by_segment(ev, team, "score_state", ["losing", "drawing", "winning"])
    halves = by_segment(ev, team, "period", [1, 2])
    mgmt = game_management(ev, team)
    p = style.set_index("eje")
    best = fit.iloc[0]

    # --- con balón / sin balón / transición (cada frase solo con los datos disponibles)
    def v(ax, col="equipo"):
        return p.loc[ax, col] if ax in p.index else np.nan

    parts = []
    if not pd.isna(v("posesion")):
        parts.append(f"tiene el {v('posesion'):.0f} % de los pases del partido (sus rivales, {v('posesion', 'rivales'):.0f} %)")
    if not pd.isna(v("juego_directo")):
        parts.append(f"juega en largo el {v('juego_directo'):.0f} % de las veces (rivales {v('juego_directo', 'rivales'):.0f} %)")
    with_ball = ("Con balón, su equipo " + _join(parts) + ".") if parts else "No hay datos suficientes sobre su juego con balón."
    without = ""
    if not pd.isna(v("presion_alta")):
        without = (f"Sin balón, el {v('presion_alta'):.0f} % de sus presiones son en campo rival "
                   f"(rivales {v('presion_alta', 'rivales'):.0f} %)")
    if block:
        rel = "más adelantado" if block["equipo"] > block["rivales"] + 1 else ("más retrasado" if block["equipo"] < block["rivales"] - 1 else "a la misma altura")
        without += (" y d" if without else "Sin balón, d") + (f"efiende de media a {block['equipo']:.0f} m de su portería, un bloque {rel} "
                    f"que el de sus rivales ({block['rivales']:.0f} m)")
    without = (without + ".") if without else "No hay datos suficientes sobre su juego sin balón."
    tparts = []
    if not pd.isna(v("contrapresion")):
        tparts.append(f"presiona de inmediato en {v('contrapresion'):.0f} de cada 100 presiones (rivales {v('contrapresion', 'rivales'):.0f})")
    if transition_rate is not None and not pd.isna(transition_rate) and transition_rate > 0:
        tparts.append(f"responde en menos de 5 segundos en el {100 * transition_rate:.0f} % de las pérdidas")
    transition = ("Tras perder el balón, " + _join(tparts) + ".") if tparts else "No hay datos suficientes sobre sus transiciones."

    # --- reacción al marcador
    reaction, reaction_short = "", ""
    rel_score = score[score["fiable"]].set_index("segmento") if len(score) else pd.DataFrame()
    if {"winning", "losing"} <= set(rel_score.index):
        cols = list(METRICS); rcols = [f"rival_{k}" for k in cols]
        w, l = rel_score.loc["winning", cols], rel_score.loc["losing", cols]
        rw = rel_score.loc["winning", rcols].rename(lambda c: c[6:]); rl = rel_score.loc["losing", rcols].rename(lambda c: c[6:])
        ph = _reaction_phrases(w, l, rw, rl, "sus rivales al ir perdiendo,")
        verdict = _intensity(l - w, rl - rw)
        reaction = ("Cuando va perdiendo, frente a cuando va ganando, su equipo " + _join(ph) + ". " + verdict
                    if ph else "Su equipo juega prácticamente igual vaya ganando o perdiendo: el plan no depende del marcador.")
        short = [x.split(" (")[0] for x in ph[:2]]
        tail = {"más": "con más intensidad que un equipo típico", "menos": "menos que un equipo típico"}
        how = next((v for k, v in tail.items() if verdict.startswith(f"Reacciona con {k}") or verdict.startswith(f"Reacciona {k}")),
                   "como haría un equipo típico")
        reaction_short = (f"Cuando va perdiendo, su equipo {_join(short)}, {how}." if short
                          else "Su plan apenas cambia con el marcador.")
    elif len(score):
        reaction = "No hay suficientes minutos ganando y perdiendo para comparar su reacción al marcador."

    halftime = ""
    rel_h = halves[halves["fiable"]].set_index("segmento") if len(halves) else pd.DataFrame()
    if {1, 2} <= set(rel_h.index):
        cols = list(METRICS); rcols = [f"rival_{k}" for k in cols]
        r1 = rel_h.loc[1, rcols].rename(lambda c: c[6:]); r2 = rel_h.loc[2, rcols].rename(lambda c: c[6:])
        ph = _reaction_phrases(rel_h.loc[1, cols], rel_h.loc[2, cols], r1, r2, "sus rivales,")
        halftime = ("En la segunda parte su equipo " + _join(ph) + "." if ph
                    else "Del primer al segundo tiempo el plan se mantiene: no hay cambios de estilo apreciables.")

    # --- gestión
    management = ""
    if mgmt.get("primer_cambio_mediana") is not None:
        management = (f"Hace {mgmt['cambios_por_partido']:.1f} cambios por partido; el primero, hacia el minuto "
                      f"{mgmt['primer_cambio_mediana']:.0f} (mediana). El {mgmt['pct_cambios_descanso']:.0f} % de sus cambios "
                      f"son en el descanso y el {mgmt['pct_cambios_ultimos_15']:.0f} % en los últimos 15 minutos.")
        fs = mgmt.get("primer_cambio_segun_marcador", {})
        if "losing" in fs and "winning" in fs:
            diff = fs["winning"] - fs["losing"]
            if abs(diff) >= 5:
                management += (f" Cuando va perdiendo mueve el banquillo antes (minuto {fs['losing']:.0f} frente a "
                               f"{fs['winning']:.0f} cuando gana)." if diff > 0 else
                               f" Curiosamente, cuando va perdiendo tarda más en mover el banquillo (minuto {fs['losing']:.0f} "
                               f"frente a {fs['winning']:.0f} cuando gana).")
        management += (f" Mueve posiciones o cambia el dibujo durante el partido en el {mgmt['pct_partidos_con_retoque']:.0f} % "
                       f"de los encuentros ({mgmt['retoques_tacticos_por_partido']:.1f} ajustes por partido).")
    rotation = ""
    if shape.get("cambios_en_once_por_partido") is not None:
        c = shape["cambios_en_once_por_partido"]
        kind = "rota poco" if c < 2 else ("rota con moderación" if c < 4 else "rota mucho")
        rotation = (f"{kind[0].upper() + kind[1:]}: cambia de media {c:.1f} titulares de un partido al siguiente, usó "
                    f"{shape['titulares_distintos']} titulares distintos y sus 11 jugadores más utilizados suman el "
                    f"{shape['pct_titularidades_top11']:.0f} % de las titularidades.")

    structure = _shape_sentence(shape)
    first_shape = structure.split(" Como alternativa")[0]
    aviso = (f"Atención: con {_plural(n_matches, 'partido')} el perfil no es fiable (se recomiendan al menos 5)."
             if n_matches < 5 else "")
    portrait = (f"El entrenador de {team} tiene un perfil de «{best['nombre']}»: {best['resumen'][0].lower() + best['resumen'][1:]} "
                f"{first_shape} {reaction_short}").strip()

    return {
        "equipo": team, "partidos": n_matches, "perfil_tipo": best["nombre"], "perfil_encaje": float(best["encaje"]),
        "ejemplos": best["ejemplos"],
        "estructura": shape, "altura_bloque": block, "gestion": mgmt,
        "por_marcador": score.to_dict(orient="records") if len(score) else [],
        "por_tiempo": halves.to_dict(orient="records") if len(halves) else [],
        "aviso": aviso,
        "textos": {"retrato": portrait, "estructura": structure, "con_balon": with_ball, "sin_balon": without,
                   "transicion": transition, "reaccion_marcador": reaction, "reaccion_corta": reaction_short, "descanso": halftime,
                   "gestion": management, "rotacion": rotation},
    }


def _f(x) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:.1f}"


def render_coach_profile_md(cp: dict) -> str:
    t = cp["textos"]
    L = [f"# Perfil del entrenador — {cp['equipo']}", "",
         f"*EFOS v0.4 · {_plural(cp['partidos'], 'partido')} · perfil reconstruido a partir de datos de eventos.*", "",
         *([f"> **{cp['aviso']}**", ""] if cp.get("aviso") else []),
         "## Retrato", "", t["retrato"], ""]
    L += ["## 1. Estructura", "", t["estructura"] or "No hay datos de posiciones para reconstruir el dibujo.", ""]
    if cp["estructura"].get("dibujos"):
        L += ["| Dibujo | Partidos |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in cp["estructura"]["dibujos"].items()] + [""]
    L += ["## 2. Estilo de juego", "", f"**Con balón.** {t['con_balon']}", "", f"**Sin balón.** {t['sin_balon']}", "",
          f"**Transición.** {t['transicion']}", ""]
    L += ["## 3. Cómo reacciona", "", t["reaccion_marcador"], ""]
    if cp["por_marcador"]:
        L += ["| Marcador | Posesión (%) | Presión en campo rival (%) | Pase largo (%) | Altura defensa (m) | Eventos |",
              "|---|---:|---:|---:|---:|---:|"]
        for r in cp["por_marcador"]:
            flag = "" if r["fiable"] else " (muestra corta)"
            L.append(f"| {SCORE_LABELS.get(r['segmento'], r['segmento'])}{flag} | {_f(r['posesion'])} | {_f(r['presion_alta'])} | "
                     f"{_f(r['pase_largo'])} | {_f(r['altura_bloque'])} | {r['eventos_equipo']} |")
        L += ["", "*Referencia: sus rivales en la misma situación del marcador.*", "",
              "| Rivales… | Posesión (%) | Presión en campo rival (%) | Pase largo (%) | Altura defensa (m) |", "|---|---:|---:|---:|---:|"]
        for r in cp["por_marcador"]:
            L.append(f"| {SCORE_LABELS.get(r['segmento'], r['segmento'])} | {_f(r['rival_posesion'])} | {_f(r['rival_presion_alta'])} | "
                     f"{_f(r['rival_pase_largo'])} | {_f(r['rival_altura_bloque'])} |")
        L.append("")
    if t["descanso"]:
        L += [t["descanso"], ""]
    L += ["## 4. Gestión del partido y del plantel", "", t["gestion"] or "No hay eventos de sustitución en los datos.", ""]
    if t["rotacion"]:
        L += [t["rotacion"], ""]
    L += ["## Qué no dice este perfil", "",
          "- Describe al equipo bajo este cuerpo técnico; no separa las decisiones del entrenador de la calidad de sus jugadores.",
          "- Si hubo cambio de entrenador dentro de la muestra, el perfil mezcla a ambos.",
          "- Las reacciones al marcador también dependen del rival y del minuto; son asociaciones, no causas.",
          "- El dibujo se reconstruye con las posiciones de los titulares y es aproximado.",
          "- Algunos cambios se deben a lesiones, no a decisiones tácticas.", ""]
    return "\n".join(L)
