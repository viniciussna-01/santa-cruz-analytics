"""Artilharia e participação em gols."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.analytics import loaders
from src.database import Database


def scorers_table(
    db: Database,
    last_n_matches: Optional[int] = None,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
) -> pd.DataFrame:
    """Colunas: Jogador | Gols | Assistências | Jogos | Minutos | Participações | Part/90.

    Só entram jogadores com pelo menos 1 gol OU 1 assistência."""
    df = loaders.santacruz_player_matches(db, season_year=season_year, competition_id=competition_id)
    cols = ["jogador", "gols", "assistencias", "jogos", "minutos", "participacoes", "part_por_90"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    if last_n_matches:
        recent = (
            df.drop_duplicates("match_id")
            .sort_values("start_timestamp", ascending=False)
            .head(last_n_matches)["match_id"]
        )
        df = df[df["match_id"].isin(recent)]

    g = df.groupby("player_id")
    t = pd.DataFrame({
        "jogador": g["name"].last(),
        "gols": g["goals"].sum(min_count=1).fillna(0),
        "assistencias": g["assists"].sum(min_count=1).fillna(0),
        "jogos": g["match_id"].nunique(),
        "minutos": g["minutes"].sum(min_count=1).fillna(0),
    }).reset_index(drop=True)
    t["participacoes"] = t["gols"] + t["assistencias"]
    mins = t["minutos"].replace(0, np.nan)
    t["part_por_90"] = (t["participacoes"] / mins * 90).round(2)
    t = t[t["participacoes"] > 0]
    t = t.sort_values(["gols", "assistencias", "part_por_90"], ascending=False)
    return t[cols].reset_index(drop=True)


def goal_involvement_summary(db: Database, **kw) -> dict:
    t = scorers_table(db, **kw)
    if t.empty:
        return {"artilheiro": None, "garcom": None, "total_gols": 0, "total_assist": 0}
    top_g = t.sort_values("gols", ascending=False).iloc[0]
    top_a = t.sort_values("assistencias", ascending=False).iloc[0]
    return {
        "artilheiro": {"jogador": top_g["jogador"], "gols": int(top_g["gols"])},
        "garcom": {"jogador": top_a["jogador"], "assistencias": int(top_a["assistencias"])},
        "total_gols": int(t["gols"].sum()),
        "total_assist": int(t["assistencias"].sum()),
    }
