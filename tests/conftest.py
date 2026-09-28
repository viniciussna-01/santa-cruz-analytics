"""Fixtures de teste — nenhum teste toca a rede.

`fixtures/` contém respostas reais do Sofascore capturadas em 2026-08-31.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.database import Database

FIX = Path(__file__).parent / "fixtures"
SANTA = 1976
SAMPLE_EVENT = 15617748
HEATMAP_PLAYER = 1087858


def load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeSofascoreClient:
    """Implementa a mesma interface do SofascoreClient usando as fixtures.

    Endpoints sem fixture retornam None / lista vazia — exatamente o que o
    coletor precisa tolerar na vida real.
    """

    def __init__(self) -> None:
        self._search = load("search_santa_cruz.json")
        self._team = load("team_1976.json")
        self._last = load("events_last_0.json")
        self._next = load("events_next_0.json")
        self._event = load(f"event_{SAMPLE_EVENT}.json")
        self._lineups = load(f"event_{SAMPLE_EVENT}_lineups.json")
        self._incidents = load(f"event_{SAMPLE_EVENT}_incidents.json")
        self._statistics = load(f"event_{SAMPLE_EVENT}_statistics.json")
        self._heatmap = load(f"event_{SAMPLE_EVENT}_heatmap_{HEATMAP_PLAYER}.json")
        self._standings = load("standings_1281_90642.json")
        # indexa TODOS os eventos das listas (last + next) para servir get_event
        self._events_by_id = {}
        for blk in (self._last, self._next):
            for ev in blk.get("events", []):
                self._events_by_id[ev["id"]] = ev
        self._events_by_id[SAMPLE_EVENT] = self._event["event"]

    # -- interface -----------------------------------------------------
    def search_teams(self, query: str):
        return [r["entity"] for r in self._search.get("results", [])
                if r.get("type") == "team" and r.get("entity")]

    def get_team(self, team_id: int):
        t = self._team.get("team")
        return t if t and t.get("id") == team_id else None

    def team_events_last(self, team_id: int, page: int = 0):
        return self._last if page == 0 else {"events": [], "hasNextPage": False}

    def team_events_next(self, team_id: int, page: int = 0):
        return self._next if page == 0 else {"events": [], "hasNextPage": False}

    def get_event(self, event_id: int):
        return self._events_by_id.get(event_id)

    def event_lineups(self, event_id: int):
        return self._lineups if event_id == SAMPLE_EVENT else None

    def event_statistics(self, event_id: int):
        return self._statistics if event_id == SAMPLE_EVENT else None

    def event_incidents(self, event_id: int):
        return self._incidents.get("incidents", []) if event_id == SAMPLE_EVENT else []

    def event_managers(self, event_id: int):
        return None

    def event_best_players(self, event_id: int):
        return None

    def player_heatmap(self, event_id: int, player_id: int):
        if event_id == SAMPLE_EVENT and player_id == HEATMAP_PLAYER:
            return self._heatmap.get("heatmap")
        return None

    def average_positions(self, event_id: int):
        return None

    def standings(self, unique_tournament_id: int, season_id: int, kind: str = "total"):
        return self._standings


@pytest.fixture
def db() -> Database:
    database = Database(":memory:")
    yield database
    database.close()


@pytest.fixture
def fake_client() -> FakeSofascoreClient:
    return FakeSofascoreClient()


@pytest.fixture
def collected_db(db, fake_client) -> Database:
    """Banco já populado pela coleta usando o FakeSofascoreClient."""
    from src.collectors.collector import Collector

    Collector(db=db, client=fake_client, team_id=SANTA).run(max_pages=1)
    return db
