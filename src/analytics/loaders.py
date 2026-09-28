"""Carregadores de DataFrames a partir do SQLite.

Centraliza os JOINs para as demais análises não repetirem SQL.
Todas as funções aceitam um objeto Database.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from src import config
from src.database import Database


def santacruz_matches(
    db: Database,
    only_finished: bool = True,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
) -> pd.DataFrame:
    """Todas as partidas do Santa Cruz, ordenadas da mais recente para a mais antiga."""
    sql = """
        SELECT m.*, c.name AS competition, c.season_year, c.unique_tournament_id, c.season_id
        FROM matches m
        LEFT JOIN competitions c ON c.id = m.competition_id
        WHERE 1 = 1
    """
    params: list = []
    if only_finished:
        sql += " AND m.status_type = 'finished'"
    if season_year is not None:
        sql += " AND c.season_year = ?"
        params.append(str(season_year))
    if competition_id is not None:
        sql += " AND m.competition_id = ?"
        params.append(competition_id)
    sql += " ORDER BY m.start_timestamp DESC"
    return db.query_df(sql, params)


def next_match(db: Database) -> Optional[pd.Series]:
    df = db.query_df(
        """
        SELECT m.*, c.name AS competition
        FROM matches m LEFT JOIN competitions c ON c.id = m.competition_id
        WHERE m.status_type = 'notstarted'
        ORDER BY m.start_timestamp ASC LIMIT 1
        """
    )
    return None if df.empty else df.iloc[0]


def santacruz_player_matches(
    db: Database,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
) -> pd.DataFrame:
    """Uma linha por (jogador, partida) para jogadores do Santa Cruz, já com
    data/competição da partida. Base de quase todas as análises de jogador."""
    sql = """
        SELECT
            pms.*,
            p.name        AS player_name,
            p.short_name  AS player_short,
            p.position    AS player_position,
            m.start_timestamp,
            m.date        AS match_date,
            m.opponent_name,
            m.santacruz_result,
            m.is_santacruz_home,
            c.name        AS competition,
            c.season_year,
            c.id          AS competition_id
        FROM player_match_stats pms
        JOIN players p  ON p.id = pms.player_id
        JOIN matches m  ON m.id = pms.match_id
        LEFT JOIN competitions c ON c.id = m.competition_id
        WHERE pms.is_santacruz = 1 AND m.status_type = 'finished'
    """
    params: list = []
    if season_year is not None:
        sql += " AND c.season_year = ?"
        params.append(str(season_year))
    if competition_id is not None:
        sql += " AND m.competition_id = ?"
        params.append(competition_id)
    sql += " ORDER BY m.start_timestamp DESC"
    df = db.query_df(sql, params)
    # posição efetiva: a do jogo, senão a cadastral
    if not df.empty:
        df["position"] = df["position"].fillna(df["player_position"])
        df["name"] = df["player_name"]
    return df


def heatmap_points(db: Database, match_id: int, player_id: int) -> list[dict]:
    row = db.execute(
        "SELECT points_json FROM player_heatmap WHERE match_id = ? AND player_id = ?",
        (match_id, player_id),
    ).fetchone()
    if not row:
        return []
    import json

    try:
        return json.loads(row[0])
    except (ValueError, TypeError):
        return []


def heatmap_points_multi(db: Database, player_id: int, match_ids: list[int]) -> list[dict]:
    """Concatena os pontos de várias partidas (mapa agregado)."""
    if not match_ids:
        return []
    import json

    q = ",".join("?" for _ in match_ids)
    rows = db.execute(
        f"SELECT points_json FROM player_heatmap WHERE player_id = ? AND match_id IN ({q})",
        [player_id, *match_ids],
    ).fetchall()
    pts: list[dict] = []
    for (blob,) in rows:
        try:
            pts.extend(json.loads(blob))
        except (ValueError, TypeError):
            continue
    return pts


def standings(db: Database) -> pd.DataFrame:
    return db.query_df(
        """
        SELECT * FROM standings_snapshot
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM standings_snapshot)
        ORDER BY position
        """
    )


def data_health(db: Database) -> dict:
    """Resumo do que temos — usado no dashboard para ser transparente."""
    total = db.scalar("SELECT COUNT(*) FROM matches WHERE status_type = 'finished'") or 0
    with_lineups = db.scalar(
        "SELECT COUNT(*) FROM matches WHERE status_type='finished' AND has_lineups=1"
    ) or 0
    with_stats = db.scalar(
        "SELECT COUNT(*) FROM matches WHERE status_type='finished' AND has_player_stats=1"
    ) or 0
    with_heat = db.scalar(
        "SELECT COUNT(*) FROM matches WHERE status_type='finished' AND has_heatmap=1"
    ) or 0
    return {
        "matches_finished": total,
        "matches_with_lineups": with_lineups,
        "matches_with_player_stats": with_stats,
        "matches_with_heatmap": with_heat,
        "last_collection": db.get_meta("last_collection"),
        "players": db.scalar("SELECT COUNT(*) FROM players") or 0,
    }
