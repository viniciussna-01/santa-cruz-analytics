"""Indicadores táticos — médias por partida das estatísticas de equipe.

Tudo aqui é **dado disponível**: média direta de números que o Sofascore
já entrega por partida (`match_team_stats`). Nenhum valor é inferido além
da média/soma explícita — e isso é deixado claro na UI.

O que o Sofascore NÃO entrega (zonas de atuação por tipo de ação, ex.:
"finalizações no último terço") fica de fora e é rotulado como
FONTE NECESSÁRIA nas páginas que consomem este módulo.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from src.analytics import loaders
from src.database import Database

# (grupo de exibição, [(key, rótulo, tipo)]) — tipo: 'sum' soma bruta, 'avg' média/jogo, 'pct' percentual textual
_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Ataque", [
        ("totalShotsOnGoal", "Finalizações"), ("shotsOnGoal", "Finalizações no alvo"),
        ("shotsOffGoal", "Finalizações para fora"), ("totalShotsInsideBox", "Finalizações dentro da área"),
        ("expectedGoals", "Gols esperados (xG)"), ("touchesInOppBox", "Toques na área adversária"),
        ("cornerKicks", "Escanteios"),
    ]),
    ("Posse e passe", [
        ("ballPossession", "Posse de bola (%)"), ("passes", "Passes"),
        ("accuratePasses", "Passes certos"), ("accurateCross", "Cruzamentos certos"),
        ("accurateLongBalls", "Bolas longas certas"),
    ]),
    ("Defesa", [
        ("totalTackle", "Desarmes"), ("interceptionWon", "Interceptações"),
        ("totalClearance", "Cortes"), ("duelWonPercent", "Duelos vencidos (%)"),
    ]),
    ("Disciplina", [
        ("fouls", "Faltas cometidas"), ("yellowCards", "Cartões amarelos"),
        ("redCards", "Cartões vermelhos"), ("dispossessed", "Perdas de posse"),
    ]),
]
ALL_KEYS = {k for _, items in _GROUPS for k, _ in items}
PERCENT_KEYS = {"ballPossession", "duelWonPercent"}


def team_stats_summary(
    db: Database,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
    last_n: Optional[int] = None,
) -> dict:
    """Retorna {"groups": [...], "n_matches": int} com médias Santa Cruz x Adversário.

    Cada grupo: {"grupo": str, "linhas": DataFrame[key,label,santacruz,adversario,n]}
    """
    matches = loaders.santacruz_matches(db, season_year=season_year, competition_id=competition_id)
    if last_n:
        matches = matches.head(last_n)
    if matches.empty:
        return {"groups": [], "n_matches": 0}

    ids = matches["id"].tolist()
    q = ",".join("?" for _ in ids)
    df = db.query_df(
        f"SELECT match_id, is_santacruz, key, value FROM match_team_stats "
        f"WHERE period='ALL' AND match_id IN ({q})",
        ids,
    )
    if df.empty:
        return {"groups": [], "n_matches": len(ids)}

    out_groups = []
    for grupo, items in _GROUPS:
        rows = []
        for key, label in items:
            sub = df[df["key"] == key]
            if sub.empty:
                continue
            sc = sub[sub["is_santacruz"] == 1]["value"]
            adv = sub[sub["is_santacruz"] == 0]["value"]
            if sc.empty and adv.empty:
                continue
            rows.append({
                "key": key, "label": label,
                "santacruz": round(sc.mean(), 1) if not sc.empty else None,
                "adversario": round(adv.mean(), 1) if not adv.empty else None,
                "n": int(sub["match_id"].nunique()),
                "percentual": key in PERCENT_KEYS,
            })
        if rows:
            out_groups.append({"grupo": grupo, "linhas": pd.DataFrame(rows)})

    return {"groups": out_groups, "n_matches": len(ids)}
