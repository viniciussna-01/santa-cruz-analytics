"""Utilitários e tratamento de dados ausentes."""
from __future__ import annotations

import math

from src.analytics import insights, players, ratings, scorers, team
from src.utils.helpers import pct, result_letter, safe_get, to_float, to_int, ts_to_date


def test_result_letter():
    assert result_letter(2, 0) == "V"
    assert result_letter(1, 1) == "E"
    assert result_letter(0, 3) == "D"
    assert result_letter(None, 1) is None


def test_pct_safe_division():
    assert pct(10, 15) == 66.7
    assert pct(1, 0) is None


def test_to_float_int_none_on_garbage():
    assert to_float("abc") is None
    assert to_float(None) is None
    assert to_int("3.9") == 3
    assert to_int("") is None


def test_safe_get_nested():
    d = {"a": {"b": {"c": 5}}}
    assert safe_get(d, "a", "b", "c") == 5
    assert safe_get(d, "a", "x", default=0) == 0
    assert safe_get(None, "a", default="z") == "z"


def test_ts_to_date():
    assert ts_to_date(1704067200) == "2024-01-01"
    assert ts_to_date(None) is None
    assert ts_to_date(0) is None


def test_analytics_on_empty_db_do_not_crash():
    from src.database import Database

    db = Database(":memory:")
    assert team.summary(db)["jogos"] == 0
    assert team.form_string(db) == ""
    assert players.player_table(db).empty
    assert scorers.scorers_table(db).empty
    assert ratings.rating_and_index(db).empty
    msgs = insights.momentum(db)
    assert msgs and "Ainda não há partidas" in msgs[0]
    db.close()


def test_player_table_handles_missing_stat_columns():
    """Jogador com escalação mas sem estatísticas (rating/minutos None)."""
    from src.database import Database

    db = Database(":memory:")
    cid = db.competition_id_for(1, 2, "X", "2026")
    db.upsert("teams", {"id": 1976, "name": "Santa Cruz"}, pk=["id"])
    db.upsert("matches", {
        "id": 1, "date": "2026-02-01", "start_timestamp": 10, "competition_id": cid,
        "status_type": "finished", "is_santacruz_home": 1, "santacruz_gf": 0,
        "santacruz_ga": 0, "santacruz_result": "E", "home_team_name": "Santa Cruz",
        "away_team_name": "R",
    }, pk=["id"])
    db.upsert("players", {"id": 5, "name": "Sem Stats", "position": "D"}, pk=["id"])
    db.upsert("player_match_stats", {
        "match_id": 1, "player_id": 5, "team_id": 1976, "is_santacruz": 1,
        "started": 1, "substitute": 0, "minutes": None, "rating": None,
        "goals": None, "assists": None, "yellow_cards": 0, "red_cards": 0,
    }, pk=["match_id", "player_id"])
    db.commit()

    pt = players.player_table(db, season_year=2026, min_matches=1)
    row = pt[pt["jogador"] == "Sem Stats"].iloc[0]
    assert row["jogos"] == 1
    assert row["gols"] == 0                    # None -> 0 para exibição
    assert math.isnan(row["nota_media"]) or row["nota_media"] is None
    db.close()
