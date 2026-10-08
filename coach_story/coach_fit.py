"""EFOS — ¿Qué entrenador encaja con este equipo?

Funciona con cualquier equipo con datos StatsBomb normalizados (run_sprint4.py):
América, Manchester City, etc. Todo se mide contra los rivales que enfrentó el
propio equipo en los mismos partidos, así que no depende de la liga.

Pasos:
  1. style_by_match   -> métricas por partido para el equipo y cada rival.
  2. style_profile    -> índice 0-100 por eje (50 = rival promedio).
  3. coach_fit        -> encaje con cada perfil de entrenador (config/coach_archetypes.yaml).
  4. build_story      -> textos en lenguaje llano para el jurado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_MATCHES = 5      # por debajo, el perfil se marca como no fiable
LONG_PASS = 32.0      # unidades StatsBomb (~30 m)
RIVAL_HALF_X = 60.0

AXES = {
    # clave: (etiqueta llana, unidad, mayor_es_mas, tipo)
    "posesion": ("Tiene el balón", "% de los pases del partido", True, "estilo"),
    "presion_alta": ("Presiona en campo rival", "% de sus presiones en campo rival", True, "estilo"),
    "contrapresion": ("Presiona justo tras perder", "contrapresiones por cada 100 presiones", True, "estilo"),
    "juego_directo": ("Usa el pase largo", "% de pases de 30 m o más", True, "estilo"),
    "peligro": ("Genera ocasiones", "xG a favor por partido", True, "rendimiento"),
    "solidez": ("Evita ocasiones del rival", "xG en contra por partido", False, "rendimiento"),
}
STYLE_AXES = [k for k, v in AXES.items() if v[3] == "estilo"]
NOUN = {"posesion": "la posesión", "presion_alta": "la presión en campo rival",
        "contrapresion": "la contrapresión tras pérdida", "juego_directo": "el uso del pase largo"}


def style_by_match(events: pd.DataFrame, team: str) -> pd.DataFrame:
    e = events.copy()
    for c in ("location_x", "pass_length", "statsbomb_xg"):
        e[c] = pd.to_numeric(e.get(c), errors="coerce")
    e["counterpress"] = e.get("counterpress", False)
    e["counterpress"] = e["counterpress"].fillna(False).astype(str).str.lower().isin(["true", "1"])
    matches = e.loc[e["team"].eq(team), "match_id"].unique()
    rows = []
    for mid in matches:
        g = e[e["match_id"].eq(mid)]
        total_passes = int(g["event_type"].eq("Pass").sum())
        for tm in g["team"].dropna().unique():
            me, op = g[g["team"].eq(tm)], g[~g["team"].eq(tm)]
            passes = me[me["event_type"].eq("Pass")]
            press = me[me["event_type"].eq("Pressure")]
            rows.append({
                "match_id": mid, "team": tm, "es_focal": tm == team,
                "posesion": 100 * len(passes) / total_passes if total_passes else np.nan,
                "presion_alta": 100 * (press["location_x"] >= RIVAL_HALF_X).mean() if press["location_x"].notna().any() else np.nan,
                "contrapresion": (100 * me["counterpress"].sum() / len(press)
                                  if len(press) and "counterpress" in events.columns else np.nan),
                "juego_directo": 100 * (passes["pass_length"] >= LONG_PASS).mean() if passes["pass_length"].notna().any() else np.nan,
                "peligro": me.loc[me["event_type"].eq("Shot"), "statsbomb_xg"].sum(),
                "solidez": op.loc[op["event_type"].eq("Shot"), "statsbomb_xg"].sum(),
            })
    return pd.DataFrame(rows)


def style_profile(by_match: pd.DataFrame) -> pd.DataFrame:
    """Índice 0-100 por eje: 50 = rival promedio, ±20 puntos por desviación típica."""
    f, r = by_match[by_match["es_focal"]], by_match[~by_match["es_focal"]]
    rows = []
    for k, (label, unit, higher_better, kind) in AXES.items():
        tv, rv, sd = f[k].mean(), r[k].mean(), r[k].std()
        if pd.isna(tv) or pd.isna(rv):
            rows.append({"eje": k, "etiqueta": label, "unidad": unit, "tipo": kind,
                         "equipo": tv, "rivales": rv, "indice": np.nan})
            continue
        z = (tv - rv) / sd if sd and not np.isnan(sd) else 0.0
        if not higher_better:
            z = -z
        rows.append({"eje": k, "etiqueta": label, "unidad": unit, "tipo": kind,
                     "equipo": tv, "rivales": rv, "indice": float(np.clip(50 + 20 * z, 0, 100))})
    return pd.DataFrame(rows)


def coach_fit(profile: pd.DataFrame, archetypes: dict) -> pd.DataFrame:
    """Encaje 0-100 = 100 - distancia media entre el estilo del equipo y el del perfil."""
    idx = profile.set_index("eje")["indice"]
    rows = []
    for key, a in archetypes["arquetipos"].items():
        gaps = {ax: idx[ax] - float(a["perfil"][ax]) for ax in STYLE_AXES}
        rows.append({"clave": key, "nombre": a["nombre"], "resumen": a["resumen"],
                     "ejemplos": ", ".join(a.get("ejemplos", [])),
                     "encaje": 100 - float(np.nanmean([abs(v) for v in gaps.values()]))
                     if any(not pd.isna(v) for v in gaps.values()) else np.nan,
                     **{f"brecha_{ax}": v for ax, v in gaps.items()}})
    return pd.DataFrame(rows).sort_values("encaje", ascending=False).reset_index(drop=True)


def _level(i: float) -> str:
    if i >= 65: return "claramente más que sus rivales"
    if i >= 55: return "algo más que sus rivales"
    if i > 45: return "como un rival promedio"
    if i > 35: return "algo menos que sus rivales"
    return "claramente menos que sus rivales"


def build_story(team: str, profile: pd.DataFrame, fit: pd.DataFrame, n_matches: int,
                margin: float = 5, esi_weakest: str | None = None) -> dict:
    p = profile.set_index("eje")
    style = p.loc[STYLE_AXES].dropna(subset=["indice"]).sort_values("indice", ascending=False)
    if style.empty:
        style = p.loc[STYLE_AXES].fillna({"indice": 50.0})
    top, bottom = style.iloc[0], style.iloc[-1]
    identity = (f"En {n_matches} partido{'s' if n_matches != 1 else ''}, lo que más define a {team} es que {top['etiqueta'].lower()} "
                f"{_level(top['indice'])} ({top['equipo']:.0f} frente a {top['rivales']:.0f}, en {top['unidad']}). "
                f"Donde menos destaca es en «{bottom['etiqueta'].lower()}»: {_level(bottom['indice'])}.")

    best, second = fit.iloc[0], fit.iloc[1]
    tie = best["encaje"] - second["encaje"] < margin
    if tie:
        coach = (f"Dos perfiles encajan casi igual: «{best['nombre']}» ({best['encaje']:.0f}/100) y "
                 f"«{second['nombre']}» ({second['encaje']:.0f}/100). Los datos no permiten elegir uno solo; "
                 f"la decisión depende de si el club quiere acentuar o moderar su estilo actual.")
    else:
        coach = (f"El perfil que mejor encaja es «{best['nombre']}» ({best['encaje']:.0f}/100), "
                 f"{best['encaje'] - second['encaje']:.0f} puntos por delante de «{second['nombre']}». "
                 f"{best['resumen']} Ejemplos conocidos de este estilo: {best['ejemplos']}.")
    gaps = {ax: best[f"brecha_{ax}"] for ax in STYLE_AXES}
    gaps = {k: v for k, v in gaps.items() if not pd.isna(v)} or {STYLE_AXES[0]: 0.0}
    ax = max(gaps, key=lambda k: abs(gaps[k]))
    verb = "reducir" if gaps[ax] > 0 else "aumentar"
    change = (f"Para parecerse del todo a ese perfil, el mayor ajuste sería {verb} {NOUN[ax]} "
              f"(hoy {p.loc[ax, 'indice']:.0f}/100; el perfil pide {p.loc[ax, 'indice'] - gaps[ax]:.0f}).")

    perf = p[p["tipo"].eq("rendimiento")].dropna(subset=["indice"]).sort_values("indice")
    if perf.empty:
        perf = p[p["tipo"].eq("rendimiento")].fillna({"indice": 50.0})
    weak = perf.iloc[0]
    if weak["indice"] >= 55:
        need = (f"En resultados, {team} supera a sus rivales tanto en generar ocasiones "
                f"({p.loc['peligro', 'equipo']:.2f} xG por partido frente a {p.loc['peligro', 'rivales']:.2f}) "
                f"como en evitarlas ({p.loc['solidez', 'equipo']:.2f} frente a {p.loc['solidez', 'rivales']:.2f}). "
                f"El nuevo entrenador hereda una base sólida: la prioridad es darle continuidad.")
    else:
        need = (f"El punto débil en resultados es «{weak['etiqueta'].lower()}»: {weak['equipo']:.2f} "
                f"{weak['unidad']} frente a {weak['rivales']:.2f} de sus rivales. El nuevo entrenador "
                f"debería traer soluciones concretas para esto.")
    if esi_weakest:
        need += f" En el índice de estabilidad EFOS, la dimensión más baja es «{esi_weakest.lower()}»."
    aviso = ""
    if n_matches < MIN_MATCHES:
        aviso = (f"Atención: con {n_matches} partido{'s' if n_matches != 1 else ''} la comparación con los rivales "
                 f"no es fiable (se recomiendan al menos {MIN_MATCHES}). Tome este perfil como ilustrativo.")
    return {"identidad": identity, "entrenador": coach, "cambio": change, "necesidad": need, "empate": tie,
            "mejor": best["nombre"], "aviso": aviso}
