"""Cenários — simulação de Monte Carlo dos jogos restantes do Santa Cruz.

Metodologia (100% baseada em dados reais coletados; ver docs/METODOLOGIA.md):

1. Detectamos a **fase atual** da competição automaticamente: ordenamos as
   partidas por data e cortamos sempre que o número da rodada VOLTA a cair
   (ex.: rodada 19 -> rodada 1) — sinal real de que uma fase terminou e outra
   começou (comprovado nos dados: Série C 2026 tem uma 1ª fase de 19 rodadas
   e depois uma fase final em mini-grupo, com a rodagem reiniciando do zero).
   Isso evita somar pontos de fases diferentes como se fossem uma coisa só.
2. Calculamos a taxa empírica de vitória/empate/derrota do Santa Cruz na
   temporada inteira (amostra maior, mais estável) para servir de base ao sorteio.
3. Para cada jogo restante da fase atual, sorteamos um resultado a partir
   dessa distribuição e somamos pontos. Repetimos N vezes (Monte Carlo).

O que este módulo **não** faz, de propósito: não estima probabilidade de
acesso/rebaixamento. Isso exigiria conhecer com certeza o regulamento da fase
atual (quantos avançam, critérios de desempate) e simular os demais times —
dado que não temos confirmado. Ver o aviso correspondente na página.
"""
from __future__ import annotations

import random
from typing import Optional

import numpy as np
import pandas as pd

from src.analytics import loaders
from src.database import Database


def _primary_competition(db: Database, season_year: Optional[str | int]) -> Optional[dict]:
    sql = (
        "SELECT c.id, c.name FROM matches m JOIN competitions c ON c.id = m.competition_id "
        "WHERE m.status_type = 'finished'"
    )
    params: list = []
    if season_year is not None:
        sql += " AND c.season_year = ?"
        params.append(str(season_year))
    sql += " GROUP BY c.id ORDER BY COUNT(*) DESC LIMIT 1"
    row = db.execute(sql, params).fetchone()
    return dict(row) if row else None


def _current_phase(db: Database, competition_id: int) -> pd.DataFrame:
    """Todas as partidas (jogadas + agendadas) da MESMA fase que os jogos
    restantes — detectada por queda no número da rodada."""
    df = db.query_df(
        "SELECT id, date, start_timestamp, round, status_type, "
        "santacruz_gf, santacruz_ga, santacruz_result, home_team_name, away_team_name, "
        "is_santacruz_home "
        "FROM matches WHERE competition_id = ? ORDER BY start_timestamp",
        (competition_id,),
    )
    if df.empty or df["round"].isna().all():
        df["phase"] = 0
        return df
    phase = 0
    phases = []
    prev_round = None
    for r in df["round"]:
        if prev_round is not None and r is not None and r < prev_round:
            phase += 1
        phases.append(phase)
        if r is not None:
            prev_round = r
    df["phase"] = phases
    return df


def simulate(
    db: Database,
    season_year: Optional[str | int] = None,
    n_sims: int = 10000,
    seed: Optional[int] = 42,
) -> dict:
    comp = _primary_competition(db, season_year)
    if not comp:
        return {"ok": False, "reason": "Sem competição com jogos finalizados neste recorte."}
    comp_id = comp["id"]

    all_matches = _current_phase(db, comp_id)
    if all_matches.empty:
        return {"ok": False, "reason": "Sem partidas coletadas para esta competição."}

    current_phase_id = all_matches["phase"].max()
    phase_df = all_matches[all_matches["phase"] == current_phase_id]
    played = phase_df[phase_df["status_type"] == "finished"]
    remaining = phase_df[phase_df["status_type"] == "notstarted"]

    current_points = int((played["santacruz_result"] == "V").sum() * 3 +
                         (played["santacruz_result"] == "E").sum())

    # taxa empírica: todas as fases DESTA competição (amostra maior e mais estável
    # que só a fase atual, mas sem misturar com outras competições/níveis — ex.:
    # não usamos o Pernambucano para estimar a forma na Série C)
    season_matches = loaders.santacruz_matches(db, competition_id=comp_id)
    n_season = len(season_matches)
    if n_season:
        p_v = (season_matches["santacruz_result"] == "V").sum() / n_season
        p_e = (season_matches["santacruz_result"] == "E").sum() / n_season
        p_d = (season_matches["santacruz_result"] == "D").sum() / n_season
    else:
        p_v = p_e = p_d = 1 / 3

    fixtures = []
    for _, r in remaining.iterrows():
        adversario = r["away_team_name"] if r["is_santacruz_home"] else r["home_team_name"]
        fixtures.append({
            "match_id": int(r["id"]), "date": r["date"], "adversario": adversario,
            "mando": "Casa" if r["is_santacruz_home"] else "Fora",
        })

    rng = random.Random(seed)
    finals = np.empty(n_sims, dtype=int)
    for i in range(n_sims):
        pts = current_points
        for _ in fixtures:
            roll = rng.random()
            pts += 3 if roll < p_v else (1 if roll < p_v + p_e else 0)
        finals[i] = pts

    return {
        "ok": True,
        "competicao": comp["name"],
        "fase_numero": int(current_phase_id) + 1,
        "n_fases_detectadas": int(all_matches["phase"].max()) + 1,
        "jogos_disputados_na_fase": len(played),
        "current_points": current_points,
        "n_remaining": len(fixtures),
        "fixtures": pd.DataFrame(fixtures),
        "final_points_dist": finals,
        "n_sims": n_sims,
        "taxa_competicao": {"vitoria": round(p_v, 3), "empate": round(p_e, 3),
                           "derrota": round(p_d, 3), "jogos": n_season},
        "played_in_phase": played[["date", "home_team_name", "away_team_name", "santacruz_result"]],
    }


def phase_summary(sim: dict) -> dict:
    dist = sim["final_points_dist"]
    return {
        "media": round(float(np.mean(dist)), 1),
        "p10": int(np.percentile(dist, 10)),
        "p50": int(np.percentile(dist, 50)),
        "p90": int(np.percentile(dist, 90)),
        "min": int(dist.min()),
        "max": int(dist.max()),
    }
