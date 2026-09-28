"""Parsers puros contra fixtures reais do Sofascore."""
from __future__ import annotations

from src.processing import parsers
from tests.conftest import SANTA, load


def test_parse_event_scoreline_from_santacruz_view():
    event = load("event_15617748.json")["event"]
    p = parsers.parse_event(event, SANTA)
    assert p["home_team_name"] == "Anápolis FC"
    assert p["away_team_name"] == "Santa Cruz"
    assert p["is_santacruz_home"] == 0
    assert p["santacruz_gf"] == 1 and p["santacruz_ga"] == 1
    assert p["santacruz_result"] == "E"
    assert p["status_type"] == "finished"
    assert p["unique_tournament_id"] == 1281
    assert p["season_id"] == 90642


def test_parse_lineups_has_ratings_and_positions():
    event = load("event_15617748.json")["event"]
    lineups = load("event_15617748_lineups.json")
    players, stats, any_rating = parsers.parse_lineups(lineups, event, SANTA)
    assert any_rating is True
    assert len(players) > 20
    sc_rows = [r for r in stats if r["is_santacruz"] == 1]
    assert sc_rows, "deve haver jogadores do Santa Cruz"
    rated = [r for r in sc_rows if r["rating"] is not None]
    assert rated
    # todo titular do Santa Cruz tem posição
    assert all(r["position"] for r in sc_rows if r["started"] == 1)


def test_parse_incidents_goals_cards_subs():
    event = load("event_15617748.json")["event"]
    inc = load("event_15617748_incidents.json")["incidents"]
    rows = parsers.parse_incidents(inc, event, SANTA)
    kinds = {r["type"] for r in rows}
    assert {"goal", "card", "substitution"} <= kinds
    goals = [r for r in rows if r["type"] == "goal"]
    assert len(goals) == 2  # placar 1-1

    cards = parsers.card_counts_from_incidents(inc)
    assert all(set(v) == {"yellow_cards", "red_cards"} for v in cards.values())


def test_parse_match_statistics_long_format():
    event = load("event_15617748.json")["event"]
    stats = load("event_15617748_statistics.json")
    rows = parsers.parse_match_statistics(stats, event, SANTA)
    assert rows
    poss = [r for r in rows if r["key"] == "ballPossession" and r["period"] == "ALL"]
    assert len(poss) == 2  # casa + fora
    assert any(r["is_santacruz"] == 1 for r in poss)


def test_parse_standings_marks_santa_cruz():
    data = load("standings_1281_90642.json")
    rows = parsers.parse_standings(data, "2026-08-31")
    sc = next(r for r in rows if r["team_id"] == SANTA)
    assert sc["played"] and sc["points"] is not None
    assert sc["position"] >= 1


def test_parse_standings_ignores_smaller_subgroup_tables():
    """standings/total pode trazer a tabela geral + mini-grupos de uma fase
    final (ex.: 'Main Round, Group B', 4 times, poucos jogos). Só a maior
    tabela (a geral) deve virar linhas — nunca mistura as duas.

    Bug real encontrado em 2026-09-24: o parser antigo iterava por TODAS as
    tabelas e duplicava/misturava posições (Santa Cruz aparecia na posição 8
    E na posição 1, de tabelas diferentes, no mesmo snapshot)."""
    payload = {
        "standings": [
            {
                "name": "Brasileiro Serie C 2026",
                "rows": [
                    {"position": i, "points": 40 - i, "matches": 19, "wins": 0, "draws": 0,
                     "losses": 0, "scoresFor": 0, "scoresAgainst": 0,
                     "team": {"id": 1000 + i, "name": f"Time {i}"}}
                    for i in range(1, 21)
                ],
            },
            {
                "name": "Brasileiro Serie C 2026, Main Round, Group B",
                "rows": [
                    {"position": 1, "points": 9, "matches": 3, "wins": 3, "draws": 0, "losses": 0,
                     "scoresFor": 5, "scoresAgainst": 1, "team": {"id": SANTA, "name": "Santa Cruz"}},
                ],
            },
        ]
    }
    rows = parsers.parse_standings(payload, "2026-09-24")
    assert len(rows) == 20
    assert all(r["played"] == 19 for r in rows)
    assert SANTA not in {r["team_id"] for r in rows}  # veio só da tabela pequena


def test_parsers_tolerate_empty_input():
    assert parsers.parse_lineups({}, {"id": 1}, SANTA) == ([], [], False)
    assert parsers.parse_incidents([], {"id": 1}, SANTA) == []
    assert parsers.parse_match_statistics({}, {"id": 1}, SANTA) == []
    assert parsers.parse_standings({}, "2026-01-01") == []
