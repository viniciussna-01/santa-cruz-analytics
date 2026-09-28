"""Identificação do Santa Cruz + coleta de partidas (com fixtures)."""
from __future__ import annotations

from src.collectors.collector import Collector
from tests.conftest import SAMPLE_EVENT, SANTA


def test_search_finds_santa_cruz_pe(fake_client):
    teams = fake_client.search_teams("Santa Cruz")
    match = next(t for t in teams if t["id"] == SANTA)
    assert match["name"] == "Santa Cruz"
    assert match["country"]["name"] == "Brazil"


def test_identify_team_persists_row(db, fake_client):
    col = Collector(db=db, client=fake_client, team_id=SANTA)
    team = col.identify_team()
    assert team["id"] == SANTA
    row = db.execute("SELECT name FROM teams WHERE id = ?", (SANTA,)).fetchone()
    assert row is not None and "Santa Cruz" in row[0]


def test_collection_saves_matches_and_details(collected_db):
    n_matches = collected_db.scalar("SELECT COUNT(*) FROM matches")
    assert n_matches >= 12  # fixture events_last_0 traz 12 + próximos

    m = collected_db.execute(
        "SELECT home_team_name, away_team_name, santacruz_gf, santacruz_ga, santacruz_result, "
        "has_lineups, has_player_stats FROM matches WHERE id = ?",
        (SAMPLE_EVENT,),
    ).fetchone()
    assert m is not None
    # Anápolis 1 x 1 Santa Cruz  -> empate, do ponto de vista do Santa Cruz
    assert (m["santacruz_gf"], m["santacruz_ga"]) == (1, 1)
    assert m["santacruz_result"] == "E"
    assert m["has_lineups"] == 1
    assert m["has_player_stats"] == 1


def test_collection_is_incremental(db, fake_client):
    col = Collector(db=db, client=fake_client, team_id=SANTA)
    first = col.run(max_pages=1)
    second = Collector(db=db, client=fake_client, team_id=SANTA).run(max_pages=1)
    # na 2ª passada, a partida detalhada não é reprocessada
    assert second["processed"] < first["processed"]
    assert second["skipped"] >= 1


def test_partial_data_does_not_break_collection(collected_db):
    """Eventos sem fixture de detalhe entram como 'shell' sem escalação."""
    shells = collected_db.scalar(
        "SELECT COUNT(*) FROM matches WHERE has_lineups = 0 AND status_type = 'finished'"
    )
    assert shells >= 1  # resto dos 12 jogos ficou sem detalhe, sem erro
