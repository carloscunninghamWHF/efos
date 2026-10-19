"""EFOS — Informe para cuerpo técnico.

Traduce todo EFOS al formato que usa un entrenador o un analista de vídeo:

  Ficha · El entrenador · Ataque organizado · Transición defensiva · Defensa organizada ·
  Transición ofensiva · Balón parado · Cómo reacciona · Jugadores · Conclusiones
  (fortalezas, debilidades, cómo jugarle, perfil que encaja) · Vídeo (clips sugeridos)

Reglas de redacción:
  * Unidades de fútbol (metros, por partido, de cada 10), sin siglas ni decimales innecesarios.
  * Cada dato va comparado con los rivales en esos mismos partidos.
  * Lo que no está validado se dice; lo que no se puede medir con eventos, no se afirma.

Funciona con cualquier equipo con datos de eventos estilo StatsBomb.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from coach_story.coach_profile import SCORE_LABELS, _abs_minute, _join, _plural

# Glosario: sigla técnica EFOS -> cómo lo diría un entrenador.
GLOSSARY = {
    "ESI": ("Regularidad del juego", "Índice 0–100 que resume cinco aspectos de la estabilidad del equipo."),
    "OC": ("Compacidad del bloque", "Cuánto se mantienen juntas las líneas del equipo."),
    "HPS": ("Juego bajo presión", "Cuánto conserva y progresa el balón cuando el rival aprieta."),
    "RPS": ("Seguridad en la salida", "Cuántos balones evita perder en su propio tercio."),
    "DS": ("Toma de decisiones", "Si elige pases acordes a su dificultad."),
    "DER": ("Reacción tras pérdida", "Qué tan rápido responde al perder el balón."),
    "DTC": ("Momentos del partido", "Tramos de 15 minutos clasificados como dominando, ajustando o sufriendo."),
    "PCI": ("Intensidad de la presión rival", "Cuánta presión sufre (o mete) en cada acción, de 0 a 1."),
    "LAP": ("Participación en último tercio", "Parte de las acciones de un jugador en el último tercio que son de ataque."),
    "CTS": ("Huella táctica", "Resumen del estilo del entrenador en ataque, defensa y transición."),
    "PPDA": ("Pases que permite antes de robar", "Pases del rival en su salida por cada acción defensiva propia. Menos = presiona más."),
    "xG": ("Goles esperados", "Calidad de las ocasiones: 1 xG equivale, de media, a un gol."),
}
DTC_FOOTBALL = {"stability": "Dominando", "adaptation": "Ajustando", "tension": "Bajo presión",
                "fragility": "Sufriendo", "collapse": "Desbordado"}

SET_PIECES = {"From Corner": "córner", "From Free Kick": "falta", "From Throw In": "saque de banda"}
DEF_ACTIONS_PPDA = {"Duel", "Interception", "Foul Committed"}
RECOVERIES = {"Ball Recovery", "Interception"}
LOSS_PASS = {"Incomplete", "Out", "Pass Offside", "Unknown"}
ON_BALL = {"Pass", "Carries", "Carry", "Ball Receipt*", "Dribble", "Shot"}
YARD_TO_M = 0.9144


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _prep(ev: pd.DataFrame, team: str) -> pd.DataFrame:
    e = ev[ev["match_id"].isin(ev.loc[ev["team"].eq(team), "match_id"].unique())].copy()
    for c in ("location_x", "location_y", "end_location_x", "end_location_y", "statsbomb_xg", "timestamp_seconds"):
        e[c] = _num(e[c]) if c in e else np.nan
    # columnas opcionales: si faltan, se crean vacías y las métricas que dependen de ellas quedan en 0 / sin dato
    defaults = {"period": 1, "second": 0, "minute": np.nan, "possession": np.nan, "play_pattern_name": np.nan,
                "shot_outcome": np.nan, "pass_outcome": np.nan, "pass_length": np.nan, "player": np.nan,
                "player_position_name": np.nan}
    for c, v in defaults.items():
        if c not in e:
            e[c] = v
    e["_min"] = _abs_minute(e)
    return e


# --------------------------------------------------------------- métricas por partido
def per_match_table(ev: pd.DataFrame, team: str) -> pd.DataFrame:
    """Una fila por (partido, equipo) con métricas futbolísticas; incluye al equipo y a cada rival."""
    e = _prep(ev, team)
    rows = []
    for mid, g in e.groupby("match_id", sort=False):
        teams = g["team"].dropna().unique()
        for tm in teams:
            me, op = g[g["team"].eq(tm)], g[~g["team"].eq(tm)]
            shots, oshots = me[me["event_type"].eq("Shot")], op[op["event_type"].eq("Shot")]
            passes = me[me["event_type"].eq("Pass")]
            pass_out = passes["pass_outcome"] if "pass_outcome" in passes else pd.Series(np.nan, index=passes.index)
            losses = pd.concat([me[me["event_type"].isin(["Dispossessed", "Miscontrol"])], passes[pass_out.isin(LOSS_PASS)]])
            rec = me[me["event_type"].isin(RECOVERIES)]
            # entradas en último tercio y en el área (pases completados y conducciones)
            prog = me[me["event_type"].isin(["Pass", "Carries", "Carry"])]
            ok = ~prog.get("pass_outcome", pd.Series(np.nan, index=prog.index)).isin(LOSS_PASS)
            ft_entries = prog[ok & (prog["location_x"] < 80) & (prog["end_location_x"] >= 80)]
            box = prog[ok & (prog["end_location_x"] >= 102) & prog["end_location_y"].between(18, 62)
                       & ~((prog["location_x"] >= 102) & prog["location_y"].between(18, 62))]
            # PPDA: pases del rival en su 60 % propio / acciones defensivas propias en el 60 % ofensivo
            opp_passes = op[op["event_type"].eq("Pass") & (op["location_x"] < 72)]
            def_act = me[me["event_type"].isin(DEF_ACTIONS_PPDA) & (me["location_x"] >= 48)]
            # ataques elaborados: posesiones con 10+ pases propios
            poss = passes.groupby("possession").size() if "possession" in passes else pd.Series(dtype=int)
            # recuperación -> tiro en <= 15 s, misma posesión
            counter = _recovery_to_shot(me, rec, shots)
            sp = shots[shots["play_pattern_name"].isin(SET_PIECES)] if "play_pattern_name" in shots else shots.iloc[0:0]
            osp = oshots[oshots["play_pattern_name"].isin(SET_PIECES)] if "play_pattern_name" in oshots else oshots.iloc[0:0]
            corners = int(passes["type_name"].eq("Corner").sum()) if "type_name" in passes else 0
            rows.append({
                "match_id": mid, "team": tm, "es_focal": tm == team,
                "rival": next((t for t in teams if t != tm), ""),
                "goles": int((shots.get("shot_outcome") == "Goal").sum() + me["event_type"].eq("Own Goal For").sum()),
                "goles_contra": int((oshots.get("shot_outcome") == "Goal").sum() + op["event_type"].eq("Own Goal For").sum()),
                "tiros": len(shots), "tiros_contra": len(oshots),
                "xg": shots["statsbomb_xg"].sum(), "xg_contra": oshots["statsbomb_xg"].sum(),
                "tiros_en_area_pct": 100 * (shots["location_x"].ge(102) & shots["location_y"].between(18, 62)).mean() if len(shots) else np.nan,
                "entradas_ultimo_tercio": len(ft_entries), "entradas_area": len(box),
                "ataques_elaborados": int((poss >= 10).sum()),
                "pases_largos_pct": 100 * (_num(passes.get("pass_length")) >= 32).mean() if len(passes) else np.nan,
                "ppda": len(opp_passes) / len(def_act) if len(def_act) else np.nan,
                "recuperaciones_ultimo_tercio": int((rec["location_x"] >= 80).sum()),
                "perdidas_propio_tercio": int((losses["location_x"] < 40).sum()),
                "tiros_tras_recuperar": counter["n"], "xg_tras_recuperar": counter["xg"],
                "tiros_abp": len(sp), "xg_abp": sp["statsbomb_xg"].sum(), "goles_abp": int((sp.get("shot_outcome") == "Goal").sum()),
                "xg_abp_contra": osp["statsbomb_xg"].sum(), "goles_abp_contra": int((osp.get("shot_outcome") == "Goal").sum()),
                "corners": int(corners),
            })
    d = pd.DataFrame(rows)
    # tiros del rival tras recuperar = transiciones defensivas que sufre el equipo
    m = d[["match_id", "team", "tiros_tras_recuperar", "xg_tras_recuperar"]].rename(
        columns={"team": "rival", "tiros_tras_recuperar": "tiros_tras_perder", "xg_tras_recuperar": "xg_tras_perder"})
    return d.merge(m, on=["match_id", "rival"], how="left")


def _recovery_to_shot(me: pd.DataFrame, rec: pd.DataFrame, shots: pd.DataFrame, window: float = 15.0) -> dict:
    if rec.empty or shots.empty or "possession" not in me:
        return {"n": 0, "xg": 0.0, "idx": []}
    n, xg, idx = 0, 0.0, []
    sh = shots.dropna(subset=["timestamp_seconds"])
    for _, r in rec.dropna(subset=["timestamp_seconds"]).iterrows():
        s = sh[sh["possession"].eq(r["possession"]) & sh["timestamp_seconds"].between(r["timestamp_seconds"], r["timestamp_seconds"] + window)
               & sh["period"].eq(r["period"])]
        if len(s):
            n += 1; xg += float(s["statsbomb_xg"].sum()); idx.append((r.name, s.index[0]))
    return {"n": n, "xg": xg, "idx": idx}


# --------------------------------------------------------------- comparación con rivales
# clave: (texto de fortaleza, texto de debilidad, mayor_es_mejor, formato)
COMPARE = {
    "xg": ("Genera ocasiones de calidad", "Le cuesta generar ocasiones", True, "{:.2f} xG por partido"),
    "xg_contra": ("Concede pocas ocasiones", "Concede demasiadas ocasiones", False, "{:.2f} xG en contra por partido"),
    "entradas_area": ("Pisa mucho el área rival", "Llega poco al área rival", True, "{:.0f} entradas al área por partido"),
    "ataques_elaborados": ("Sabe atacar con paciencia", "Pocos ataques elaborados", True, "{:.1f} ataques de 10+ pases por partido"),
    "ppda": ("Presiona arriba con intensidad", "Presiona poco la salida rival", False, "{:.1f} pases rivales por acción defensiva"),
    "recuperaciones_ultimo_tercio": ("Roba balones cerca del área rival", "Recupera poco en campo rival", True, "{:.1f} recuperaciones en último tercio por partido"),
    "perdidas_propio_tercio": ("Sale limpio desde atrás", "Pierde balones en su salida", False, "{:.1f} pérdidas en su tercio por partido"),
    "xg_tras_recuperar": ("Castiga a la contra", "Aprovecha poco las recuperaciones", True, "{:.2f} xG tras recuperar por partido"),
    "xg_tras_perder": ("Defiende bien las transiciones", "Sufre a la contra", False, "{:.2f} xG concedido tras perder por partido"),
    "xg_abp": ("Peligroso a balón parado", "Saca poco del balón parado", True, "{:.2f} xG a balón parado por partido"),
    "xg_abp_contra": ("Sólido defendiendo el balón parado", "Sufre en el balón parado defensivo", False, "{:.2f} xG concedido a balón parado por partido"),
}

HOW_TO_PLAY = {
    "perdidas_propio_tercio": "Presionarle la salida de balón: es donde más pérdidas comete.",
    "xg_tras_perder": "Atacar rápido tras recuperar: cuando pierde el balón, concede ocasiones a la contra.",
    "xg_abp_contra": "Insistir en el balón parado: defensivamente es su punto más vulnerable.",
    "ppda": "Construir con calma desde atrás: presiona poco la salida y permite muchos pases.",
    "xg_contra": "Acumular llegadas: concede ocasiones de calidad.",
    "recuperaciones_ultimo_tercio": "Salir jugando sin miedo: rara vez roba balones en campo rival.",
    "entradas_area": "Defender en bloque medio-bajo: le cuesta pisar el área.",
    "ataques_elaborados": "Obligarle a atacar en estático: tiene pocos recursos de ataque elaborado.",
    "xg": "Defender con orden y paciencia: genera pocas ocasiones claras.",
    "xg_tras_recuperar": "Asumir riesgos en la circulación: aprovecha poco los balones que recupera.",
    "xg_abp": "Conceder faltas lejos del área no es un gran riesgo: genera poco a balón parado.",
}


def compare_with_rivals(pm: pd.DataFrame) -> pd.DataFrame:
    f, r = pm[pm["es_focal"]], pm[~pm["es_focal"]]
    rows = []
    for k, (good, bad, higher, fmt) in COMPARE.items():
        tv, rv, sd = f[k].mean(), r[k].mean(), r[k].std()
        if pd.isna(tv) or pd.isna(rv):
            continue
        z = (tv - rv) / sd if sd and not np.isnan(sd) else 0.0
        z = z if higher else -z
        rows.append({"clave": k, "equipo": tv, "rivales": rv, "z": z, "fortaleza": good, "debilidad": bad,
                     "texto_equipo": fmt.format(tv), "texto_rivales": fmt.format(rv)})
    return pd.DataFrame(rows).sort_values("z", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------- jugadores
def average_positions(ev: pd.DataFrame, team: str, starters: dict | None = None, n: int = 11) -> pd.DataFrame:
    t = _prep(ev, team)
    t = t[t["team"].eq(team) & t["event_type"].isin(ON_BALL) & t["player"].notna()]
    if t.empty:
        return pd.DataFrame()
    if starters:
        counts = pd.Series([p for xi in starters.values() for p in xi]).value_counts()
        players = counts.head(n).index
        starts = counts
    else:
        players = t["player"].value_counts().head(n).index
        starts = pd.Series(dtype=int)
    g = t[t["player"].isin(players)].groupby("player")
    d = pd.DataFrame({"x": g["location_x"].median() * YARD_TO_M, "y": g["location_y"].median() * YARD_TO_M,
                      "acciones": g.size(),
                      "posicion": g["player_position_name"].agg(lambda s: s.value_counts().index[0] if s.notna().any() else "")
                      if "player_position_name" in t else ""}).reset_index()
    d["titularidades"] = d["player"].map(starts).fillna(0).astype(int)
    d["nombre_corto"] = d["player"].map(_short_name)
    return d.sort_values("x").reset_index(drop=True)


def _short_name(full: str) -> str:
    parts = str(full).split()
    if len(parts) <= 2:
        return str(full)
    # nombres hispanos: nombre + primer apellido suele ser el nombre deportivo aproximado
    return f"{parts[0]} {parts[-2] if len(parts) >= 4 else parts[1]}"


# --------------------------------------------------------------- vídeo
def suggested_clips(ev: pd.DataFrame, team: str, per_type: int = 3) -> pd.DataFrame:
    """Jugadas concretas (partido, parte, minuto) que ilustran cada rasgo, para revisarlas en vídeo."""
    e = _prep(ev, team)
    rival_of = e.groupby("match_id")["team"].agg(lambda s: next((t for t in s.dropna().unique() if t != team), ""))
    me, op = e[e["team"].eq(team)], e[~e["team"].eq(team)]
    clips, used = [], set()

    def add(df, tipo, que_ver, rasgo, player_col=None):
        df = df[[i not in used for i in df.index]]
        for i, r in df.head(per_type).iterrows():
            used.add(i)
            mm = int(r["_min"]) if not pd.isna(r["_min"]) else int(r.get("minute", 0))
            clips.append({"tipo": tipo, "rasgo": rasgo, "match_id": r["match_id"], "rival": rival_of.get(r["match_id"], ""),
                          "parte": int(r["period"]) if not pd.isna(r.get("period")) else None,
                          "minuto": f"{mm}:{int(r.get('second', 0) or 0):02d}",
                          "jugador": r.get(player_col, "") if player_col else r.get("player", ""),
                          "xg": round(float(r["statsbomb_xg"]), 2) if not pd.isna(r.get("statsbomb_xg")) else None,
                          "que_ver": que_ver})

    shots = me[me["event_type"].eq("Shot")]
    oshots = op[op["event_type"].eq("Shot")]
    # 1. Recuperación alta que acaba en tiro
    rec = me[me["event_type"].isin(RECOVERIES) & (me["location_x"] >= 60)]
    pairs = _recovery_to_shot(me, rec, shots)["idx"]
    if pairs:
        s = e.loc[[b for _, b in pairs]].sort_values("statsbomb_xg", ascending=False)
        add(s, "A favor", "Cómo roba en campo rival y en cuántos segundos llega al tiro.", "Presión y transición ofensiva")
    # 2. Ataque elaborado (10+ pases) que termina en tiro
    if "possession" in me:
        npass = me[me["event_type"].eq("Pass")].groupby(["match_id", "possession"]).size()
        long_poss = set(npass[npass >= 10].index)
        open_play = ~shots["play_pattern_name"].isin(SET_PIECES) if "play_pattern_name" in shots else True
        in_long = pd.Series([(m, p) in long_poss for m, p in zip(shots["match_id"], shots["possession"])], index=shots.index)
        s = shots[in_long & open_play].sort_values("statsbomb_xg", ascending=False)
        add(s, "A favor", "La circulación previa: por dónde progresa y cómo encuentra el hueco.", "Ataque organizado")
    # 3. Balón parado a favor
    if "play_pattern_name" in shots:
        s = shots[shots["play_pattern_name"].isin(SET_PIECES)].sort_values("statsbomb_xg", ascending=False)
        add(s, "A favor", "El bloqueo o movimiento que libera al rematador.", "Balón parado ofensivo")
    # 4. Pérdida en salida que acaba en tiro rival
    passes = me[me["event_type"].eq("Pass")]
    pout = passes["pass_outcome"] if "pass_outcome" in passes else pd.Series(np.nan, index=passes.index)
    losses = pd.concat([me[me["event_type"].isin(["Dispossessed", "Miscontrol"])], passes[pout.isin(LOSS_PASS)]])
    losses = losses[losses["location_x"] < 40].dropna(subset=["timestamp_seconds"])
    rows = []
    for _, l in losses.iterrows():
        s = oshots[oshots["match_id"].eq(l["match_id"]) & oshots["period"].eq(l["period"])
                   & oshots["timestamp_seconds"].between(l["timestamp_seconds"], l["timestamp_seconds"] + 15)]
        if len(s):
            row = s.iloc[0].copy(); row["perdio"] = l.get("player", "")
            rows.append(row)
    if rows:
        add(pd.DataFrame(rows).sort_values("statsbomb_xg", ascending=False), "En contra",
            "Dónde y cómo pierde el balón en su salida, y la ocasión que concede.", "Salida de balón", "perdio")
    # 5. Ocasión concedida a la contra
    if "play_pattern_name" in oshots:
        s = oshots[oshots["play_pattern_name"].eq("From Counter")].sort_values("statsbomb_xg", ascending=False)
        add(s, "En contra", "La espalda de su defensa adelantada tras la pérdida.", "Transición defensiva")
    # 6. Balón parado en contra
    if "play_pattern_name" in oshots:
        s = oshots[oshots["play_pattern_name"].isin(SET_PIECES)].sort_values("statsbomb_xg", ascending=False)
        add(s, "En contra", "Marcajes y zona de remate rival.", "Balón parado defensivo")
    return pd.DataFrame(clips)


# --------------------------------------------------------------- informe
def build_football_report(ev: pd.DataFrame, team: str, coach_identity: dict, fit: pd.DataFrame,
                          dims: dict, esi: float, lap: pd.DataFrame | None, states: pd.DataFrame | None,
                          transition_rate: float | None, starters: dict | None = None) -> dict:
    pm = per_match_table(ev, team)
    f, r = pm[pm["es_focal"]], pm[~pm["es_focal"]]
    n = int(f["match_id"].nunique())
    res = f.assign(res=np.sign(f["goles"] - f["goles_contra"]))
    w, d_, l = int((res["res"] > 0).sum()), int((res["res"] == 0).sum()), int((res["res"] < 0).sum())
    cmp = compare_with_rivals(pm)
    t = coach_identity.get("textos", {})
    fm = f.mean(numeric_only=True); rm = r.mean(numeric_only=True)

    def vs(k, fmt="{:.1f}"):
        return f"{fmt.format(fm[k])} (sus rivales, {fmt.format(rm[k])})"

    ficha = {"partidos": n, "ganados": w, "empatados": d_, "perdidos": l, "puntos": 3 * w + d_,
             "puntos_por_partido": (3 * w + d_) / n if n else 0, "goles": int(f["goles"].sum()),
             "goles_contra": int(f["goles_contra"].sum()), "xg": float(f["xg"].sum()), "xg_contra": float(f["xg_contra"].sum())}
    ficha_txt = (f"{_plural(n, 'partido')}: {w} victorias, {d_} empates y {l} derrotas "
                 f"({ficha['puntos_por_partido']:.2f} puntos por partido). {ficha['goles']} goles a favor y "
                 f"{ficha['goles_contra']} en contra; por la calidad de sus ocasiones \"debería\" haber marcado "
                 f"{ficha['xg']:.0f} y recibido {ficha['xg_contra']:.0f} (goles esperados).")
    diff = ficha["goles"] - ficha["xg"]
    if abs(diff) >= 4:
        ficha_txt += (f" Marca {abs(diff):.0f} goles {'más' if diff > 0 else 'menos'} de lo esperado: "
                      f"{'eficacia o acierto por encima de la media' if diff > 0 else 'falta de acierto de cara a portería'}.")

    attack = (f"Con balón tiene el {_style(coach_identity, 'posesion')} de los pases del partido. "
              f"Por partido llega {fm['entradas_ultimo_tercio']:.0f} veces al último tercio y {vs('entradas_area', '{:.0f}')} al área, "
              f"construye {vs('ataques_elaborados')} ataques de 10 o más pases y dispara {fm['tiros']:.0f} veces "
              f"({fm['tiros_en_area_pct']:.0f} % desde dentro del área). Juega en largo el {fm['pases_largos_pct']:.0f} % de sus pases.")
    def_trans = (f"Tras perder el balón, {t.get('transicion', '').replace('Tras perder el balón, ', '')} "
                 f"Cuando el rival le roba y ataca rápido, le genera {vs('xg_tras_perder', '{:.2f}')} xG por partido.")
    defence = (f"{t.get('sin_balon', '')} Permite {vs('ppda')} pases al rival en su salida por cada acción defensiva "
               f"(cuanto más bajo, más presiona) y recupera {vs('recuperaciones_ultimo_tercio')} balones por partido "
               f"en el último tercio. Concede {vs('tiros_contra', '{:.0f}')} tiros y {vs('xg_contra', '{:.2f}')} xG por partido.")
    off_trans = (f"Tras recuperar, termina en tiro en menos de 15 segundos {fm['tiros_tras_recuperar']:.1f} veces por partido, "
                 f"por {fm['xg_tras_recuperar']:.2f} xG (sus rivales, {rm['xg_tras_recuperar']:.2f}).")
    sp_share = 100 * f["xg_abp"].sum() / f["xg"].sum() if f["xg"].sum() else 0
    sp_share_c = 100 * f["xg_abp_contra"].sum() / f["xg_contra"].sum() if f["xg_contra"].sum() else 0
    set_pieces = (f"A balón parado (córners, faltas y saques de banda) genera {vs('xg_abp', '{:.2f}')} xG por partido, el "
                  f"{sp_share:.0f} % de todo su peligro, y ha marcado {int(f['goles_abp'].sum())} goles así. En defensa concede "
                  f"{vs('xg_abp_contra', '{:.2f}')} xG por partido a balón parado ({sp_share_c:.0f} % de lo que concede) y "
                  f"{int(f['goles_abp_contra'].sum())} goles. Saca {fm['corners']:.1f} córners por partido.")

    strengths = cmp[cmp["z"] >= 0.25].head(3)
    if strengths.empty:
        strengths = cmp.head(2)
    weaknesses = cmp[cmp["z"] <= -0.1].sort_values("z").head(3)
    weak_label = "Debilidades"
    if weaknesses.empty:
        weaknesses = cmp.sort_values("z").head(2)
        weak_label = "Lo menos destacado (no son debilidades: está en la media o por encima)"
    real_weak = weaknesses[weaknesses["z"] < 0]
    how = [HOW_TO_PLAY[k] for k in real_weak["clave"] if k in HOW_TO_PLAY]
    if not how:
        how.append("No muestra un punto débil claro frente a sus rivales: las vías más prometedoras son aquellas "
                   "en las que su ventaja es menor (" + _join([x.lower() for x in weaknesses["fortaleza"]]) + ").")
    block = coach_identity.get("altura_bloque", {})
    if block and block.get("equipo", 0) > block.get("rivales", 0) + 2:
        how.append(f"Por estilo: defiende muy adelantado ({block['equipo']:.0f} m de su portería), así que los balones "
                   "a la espalda y los desmarques de ruptura son una vía natural.")

    moments = ""
    if states is not None and len(states):
        c = states["state"].value_counts(normalize=True)
        moments = ("Por tramos de 15 minutos, el equipo está " + _join(
            [f"{DTC_FOOTBALL.get(k, k).lower()} el {100 * v:.0f} % del tiempo" for k, v in c.items() if v >= 0.01]) + ".")

    players_txt = ""
    if lap is not None and len(lap):
        top = lap[lap["final_third_actions"] >= 100].nlargest(3, "LAP")
        if len(top):
            players_txt = ("Entre los jugadores con al menos 100 acciones en el último tercio, los que más participan en "
                           "jugadas de ataque son " + _join([f"{p.player} ({p.LAP:.0f} %)" for p in top.itertuples()]) + ".")

    best = fit.iloc[0] if len(fit) else None
    fit_txt = (f"Por estilo, el perfil que mejor lo continuaría es «{best['nombre']}» ({best['encaje']:.0f}/100), "
               f"como {best['ejemplos']}." if best is not None else "")

    stability = (f"Regularidad del juego (índice EFOS): {esi:.0f}/100. Lo más sólido es la "
                 f"{GLOSSARY[max(dims, key=dims.get)][0].lower()} ({dims[max(dims, key=dims.get)]:.0f}) y lo más mejorable, la "
                 f"{GLOSSARY[min(dims, key=dims.get)][0].lower()} ({dims[min(dims, key=dims.get)]:.0f}).")

    return {
        "equipo": team, "ficha": ficha, "per_match": pm, "comparacion": cmp,
        "textos": {
            "ficha": ficha_txt, "entrenador": t.get("retrato", ""), "estructura": t.get("estructura", ""),
            "gestion": t.get("gestion", ""), "rotacion": t.get("rotacion", ""),
            "ataque_organizado": attack, "transicion_defensiva": def_trans, "defensa_organizada": defence,
            "transicion_ofensiva": off_trans, "balon_parado": set_pieces,
            "reaccion": t.get("reaccion_marcador", ""), "descanso": t.get("descanso", ""), "momentos": moments,
            "jugadores": players_txt, "regularidad": stability, "encaje": fit_txt,
        },
        "fortalezas": [{"titulo": x.fortaleza, "dato": x.texto_equipo, "rivales": x.texto_rivales} for x in strengths.itertuples()],
        "debilidades": [{"titulo": x.debilidad if x.z < 0 else f"{x.fortaleza}, aunque menos que en otras facetas",
                         "dato": x.texto_equipo, "rivales": x.texto_rivales, "real": bool(x.z < 0)} for x in weaknesses.itertuples()],
        "debilidades_titulo": weak_label, "como_jugarle": how,
        "clips": suggested_clips(ev, team),
        "posiciones": average_positions(ev, team, starters),
        "aviso": coach_identity.get("aviso", ""),
        "estructura": coach_identity.get("estructura", {}),
        "perfil_tipo": coach_identity.get("perfil_tipo", ""), "ejemplos": coach_identity.get("ejemplos", ""),
    }


def _style(cp: dict, key: str) -> str:
    # posesión media global: se toma del texto de estilo del perfil del entrenador
    txt = cp.get("textos", {}).get("con_balon", "")
    import re
    m = re.search(r"el (\d+) % de los pases del partido \(sus rivales, (\d+) %\)", txt)
    return f"{m.group(1)} % (sus rivales, {m.group(2)} %)" if m else "—"


def render_football_report_md(rep: dict) -> str:
    t, team = rep["textos"], rep["equipo"]
    L = [f"# Informe para cuerpo técnico — {team}", "",
         "*EFOS · Todos los datos se comparan con lo que hicieron sus rivales en esos mismos partidos.*", ""]
    if rep.get("aviso"):
        L += [f"> **{rep['aviso']}**", ""]
    L += ["## Ficha", "", t["ficha"], "", "## 1. El entrenador", "", t["entrenador"], ""]
    for k in ("gestion", "rotacion"):
        if t.get(k):
            L += [t[k], ""]
    L += ["## 2. Ataque organizado", "", t["ataque_organizado"], "",
          "## 3. Transición defensiva (tras perder el balón)", "", t["transicion_defensiva"], "",
          "## 4. Defensa organizada", "", t["defensa_organizada"], "",
          "## 5. Transición ofensiva (tras recuperar)", "", t["transicion_ofensiva"], "",
          "## 6. Balón parado", "", t["balon_parado"], "",
          "## 7. Cómo reacciona durante el partido", "", t["reaccion"], ""]
    for k in ("descanso", "momentos"):
        if t.get(k):
            L += [t[k], ""]
    L += ["## 8. Jugadores", ""]
    pos = rep["posiciones"]
    if len(pos):
        L += ["Once más utilizado y su posición media con balón (metros desde su portería · desde la banda izquierda):", "",
              "| Jugador | Posición habitual | Titularidades | Altura (m) | Carril (m) |", "|---|---|---:|---:|---:|"]
        for p in pos.sort_values("x", ascending=False).itertuples():
            L.append(f"| {p.player} | {POSITION_ES.get(p.posicion, p.posicion)} | {p.titularidades} | {p.x:.0f} | {p.y:.0f} |")
        L.append("")
    if t["jugadores"]:
        L += [t["jugadores"], ""]
    L += ["## 9. Conclusiones", "", "### Fortalezas", ""]
    L += [f"- **{x['titulo']}**: {x['dato']} (rivales: {x['rivales']})." for x in rep["fortalezas"]]
    L += ["", f"### {rep['debilidades_titulo']}", ""]
    L += [f"- **{x['titulo']}**: {x['dato']} (rivales: {x['rivales']})." for x in rep["debilidades"]]
    if rep["como_jugarle"]:
        L += ["", "### Cómo jugarle", ""] + [f"- {x}" for x in rep["como_jugarle"]]
    L += ["", "### Perfil de entrenador que lo continuaría", "", t["encaje"], "", t["regularidad"], ""]
    clips = rep["clips"]
    if len(clips):
        L += ["## 10. Vídeo: jugadas para revisar", "",
              "Cada conclusión debería verse en vídeo. Estas jugadas son los mejores ejemplos que encuentra EFOS "
              "(protagonista: quien remata o, en «salida de balón», el jugador propio que pierde el balón):", "",
              "| Tipo | Rasgo | Rival | Parte | Minuto | Protagonista | xG | Qué observar |", "|---|---|---|---:|---:|---|---:|---|"]
        for c in clips.itertuples():
            xg = "" if c.xg is None or pd.isna(c.xg) else f"{c.xg:.2f}"
            L.append(f"| {c.tipo} | {c.rasgo} | {c.rival} | {c.parte} | {c.minuto} | {c.jugador} | {xg} | {c.que_ver} |")
        L.append("")
    L += ["## Qué no dice este informe", "",
          "- Describe lo que hizo el equipo; no sabe qué instrucciones dio el entrenador en el vestuario.",
          "- No separa las decisiones del entrenador de la calidad de sus jugadores.",
          "- Si hubo cambio de entrenador dentro de la muestra, mezcla a ambos.",
          "- Los datos no indican local o visitante, ni el torneo (Apertura, Clausura, Liguilla): esos cortes quedan pendientes.",
          "- Las «trampas de presión» y otros patrones avanzados de EFOS siguen en fase experimental hasta validarlos con vídeo.",
          "", "## Glosario", "", "| En EFOS | En el vestuario | Qué significa |", "|---|---|---|"]
    L += [f"| {k} | {v[0]} | {v[1]} |" for k, v in GLOSSARY.items()]
    return "\n".join(L) + "\n"


POSITION_ES = {
    "Goalkeeper": "Portero", "Right Back": "Lateral derecho", "Left Back": "Lateral izquierdo",
    "Right Center Back": "Central derecho", "Left Center Back": "Central izquierdo", "Center Back": "Central",
    "Right Wing Back": "Carrilero derecho", "Left Wing Back": "Carrilero izquierdo",
    "Right Defensive Midfield": "Pivote derecho", "Left Defensive Midfield": "Pivote izquierdo",
    "Center Defensive Midfield": "Mediocentro defensivo", "Right Center Midfield": "Interior derecho",
    "Left Center Midfield": "Interior izquierdo", "Center Center Midfield": "Mediocentro",
    "Right Midfield": "Volante derecho", "Left Midfield": "Volante izquierdo",
    "Right Attacking Midfield": "Mediapunta derecho", "Left Attacking Midfield": "Mediapunta izquierdo",
    "Center Attacking Midfield": "Mediapunta", "Right Wing": "Extremo derecho", "Left Wing": "Extremo izquierdo",
    "Center Forward": "Delantero centro", "Right Center Forward": "Delantero derecho",
    "Left Center Forward": "Delantero izquierdo", "Secondary Striker": "Segundo delantero",
}
