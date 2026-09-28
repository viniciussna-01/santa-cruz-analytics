"""Ranking e agregados por jogador (somente Santa Cruz)."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.analytics import loaders
from src.database import Database

# colunas somadas / contadas nos agregados
_SUM_COLS = [
    "minutes", "goals", "assists", "own_goals", "shots", "shots_on_target",
    "shots_off_target", "big_chances_created", "key_passes", "passes",
    "accurate_passes", "crosses", "accurate_crosses", "tackles", "tackles_won",
    "interceptions", "clearances", "blocks", "duels_won", "duels_lost",
    "aerials_won", "aerials_lost", "ball_recoveries", "possession_lost",
    "dispossessed", "fouls", "was_fouled", "saves", "saved_shots_in_box",
    "yellow_cards", "red_cards",
]


def _base(
    db: Database,
    season_year: Optional[str | int],
    competition_id: Optional[int],
    last_n_matches: Optional[int],
) -> pd.DataFrame:
    df = loaders.santacruz_player_matches(db, season_year=season_year, competition_id=competition_id)
    if df.empty:
        return df
    if last_n_matches:
        recent_ids = (
            df.drop_duplicates("match_id")
            .sort_values("start_timestamp", ascending=False)
            .head(last_n_matches)["match_id"]
        )
        df = df[df["match_id"].isin(recent_ids)]
    return df


def player_table(
    db: Database,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
    last_n_matches: Optional[int] = None,
    position: Optional[str] = None,
    min_matches: int = 0,
) -> pd.DataFrame:
    """Tabela-resumo por jogador. Colunas em português para o dashboard.

    Retorna DataFrame vazio (com colunas) se não houver dados no recorte —
    o dashboard trata isso mostrando aviso, sem inventar linhas."""
    cols = [
        "player_id", "jogador", "posicao", "jogos", "titularidades", "minutos", "gols",
        "assistencias", "participacao_gols", "nota_media", "finalizacoes",
        "finalizacoes_alvo", "passes", "passes_chave", "desarmes",
        "interceptacoes", "cartoes_amarelos", "cartoes_vermelhos",
        "gols_por_90", "part_gols_por_90",
    ]
    df = _base(db, season_year, competition_id, last_n_matches)
    if df.empty:
        return pd.DataFrame(columns=cols)

    if position:
        df = df[df["position"].str.upper().str[0] == position.upper()[0]]
        if df.empty:
            return pd.DataFrame(columns=cols)

    g = df.groupby("player_id")
    agg = pd.DataFrame({
        "jogador": g["name"].last(),
        "posicao": g["position"].last(),
        "jogos": g["match_id"].nunique(),
        "titularidades": g["started"].sum(min_count=1),
        "minutos": g["minutes"].sum(min_count=1),
        "gols": g["goals"].sum(min_count=1),
        "assistencias": g["assists"].sum(min_count=1),
        "finalizacoes": g["shots"].sum(min_count=1),
        "finalizacoes_alvo": g["shots_on_target"].sum(min_count=1),
        "passes": g["passes"].sum(min_count=1),
        "passes_chave": g["key_passes"].sum(min_count=1),
        "desarmes": g["tackles_won"].sum(min_count=1),
        "interceptacoes": g["interceptions"].sum(min_count=1),
        "cartoes_amarelos": g["yellow_cards"].sum(min_count=1),
        "cartoes_vermelhos": g["red_cards"].sum(min_count=1),
        "nota_media": g["rating"].mean(),
    }).reset_index()

    for c in ("gols", "assistencias"):
        agg[c] = pd.to_numeric(agg[c], errors="coerce").fillna(0)
    agg["participacao_gols"] = agg["gols"] + agg["assistencias"]
    mins = agg["minutos"].replace(0, np.nan)
    agg["gols_por_90"] = (agg["gols"] / mins * 90).round(2)
    agg["part_gols_por_90"] = (agg["participacao_gols"] / mins * 90).round(2)
    agg["nota_media"] = agg["nota_media"].round(2)

    agg = agg[agg["jogos"] >= max(0, min_matches)]
    agg = agg.sort_values(["participacao_gols", "nota_media"], ascending=False, na_position="last")
    return agg[cols].reset_index(drop=True)


def positions_available(db: Database, **kw) -> list[str]:
    df = _base(db, kw.get("season_year"), kw.get("competition_id"), None)
    if df.empty:
        return []
    return sorted({str(p)[0] for p in df["position"].dropna().unique()})
