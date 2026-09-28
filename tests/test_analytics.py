"""Análises de time e jogador sobre um banco sintético e determinístico."""
from __future__ import annotations

import pytest

import pandas as pd

from src.analytics import players, ratings, scorers, team
from src.database import Database
from src.utils.helpers import result_letter


# ---------------------------------------------------------------------------
# construção de um banco pequeno e controlado
# ---------------------------------------------------------------------------
def _mk_match(db: Database, mid: int, ts: int, gf: int, ga: int, home: bool, comp_id: int):
    res = result_letter(gf, ga)
    hs, as_ = (gf, ga) if home else (ga, gf)
    db.upsert("matches", {
        "id": mid, "date": f"2026-01-{mid:02d}", "start_timestamp": ts,
        "competition_id": comp_id, "competition_name": "Teste",
        "home_team_id": 1976 if home else 99, "away_team_id": 99 if home else 1976,
        "home_team_name": "Santa Cruz" if home else "Rival",
        "away_team_name": "Rival" if home else "Santa Cruz",
        "home_score": hs, "away_score": as_, "status": "Ended", "status_type": "finished",
        "winner_code": 1 if hs > as_ else (2 if as_ > hs else 3),
        "is_santacruz_home": 1 if home else 0, "santacruz_gf": gf, "santacruz_ga": ga,
        "santacruz_result": res, "opponent_id": 99, "opponent_name": "Rival",
        "has_lineups": 1, "has_player_stats": 1,
    }, pk=["id"])


def _mk_pms(db: Database, mid: int, pid: int, **stats):
    row = {"match_id": mid, "player_id": pid, "team_id": 1976, "is_santacruz": 1,
           "started": 1, "substitute": 0, "yellow_cards": 0, "red_cards": 0}
    row.update(stats)
    db.upsert("player_match_stats", row, pk=["match_id", "player_id"])


@pytest.fixture
def mini_db():
    db = Database(":memory:")
    cid = db.competition_id_for(9999, 5555, "Teste", "2026")
    db.upsert("teams", {"id": 1976, "name": "Santa Cruz"}, pk=["id"])
    db.upsert("teams", {"id": 99, "name": "Rival"}, pk=["id"])
    # 5 jogos: V(2-0 casa), D(0-1 fora), V(3-1 casa), E(1-1 fora), V(2-1 casa)
    plan = [
        (1, 100, 2, 0, True), (2, 200, 0, 1, False), (3, 300, 3, 1, True),
        (4, 400, 1, 1, False), (5, 500, 2, 1, True),
    ]
    for mid, ts, gf, ga, home in plan:
        _mk_match(db, mid, ts, gf, ga, home, cid)
    for p in (10, 11, 12):
        db.upsert("players", {"id": p, "name": f"Jogador {p}", "position": "F" if p == 10 else "M"}, pk=["id"])
    # Jogador 10: artilheiro (4 gols em 5 jogos, 450 min, notas variando)
    for i, (mid, g, a, rating, mins) in enumerate([
        (1, 2, 0, 7.5, 90), (2, 0, 1, 6.0, 90), (3, 2, 0, 8.4, 90),
        (4, 0, 0, 6.5, 90), (5, 0, 1, 7.0, 90),
    ]):
        _mk_pms(db, mid, 10, goals=g, assists=a, rating=rating, minutes=mins,
                shots=4, shots_on_target=2, passes=20, accurate_passes=15, key_passes=1,
                tackles_won=0, interceptions=0, xg=0.4, xa=0.1)
    # Jogador 11: meio com boa nota, 1 gol 3 assist
    for mid, g, a, rating in [(1, 0, 1, 7.2), (2, 1, 0, 7.8), (3, 0, 1, 7.1), (4, 0, 1, 6.9), (5, 0, 0, 7.0)]:
        _mk_pms(db, mid, 11, goals=g, assists=a, rating=rating, minutes=90,
                passes=55, accurate_passes=48, key_passes=3, tackles_won=2, interceptions=2)
    # Jogador 12: só 2 jogos -> abaixo do min_matches padrão
    _mk_pms(db, 1, 12, goals=0, assists=0, rating=6.0, minutes=45)
    _mk_pms(db, 2, 12, goals=1, assists=0, rating=7.0, minutes=30)
    db.commit()
    yield db
    db.close()


# ---------------------------------------------------------------------------
# TIME
# ---------------------------------------------------------------------------
def test_summary_counts_and_aproveitamento(mini_db):
    s = team.summary(mini_db, season_year=2026)
    assert s["jogos"] == 5
    assert (s["vitorias"], s["empates"], s["derrotas"]) == (3, 1, 1)
    assert s["gols_marcados"] == 8 and s["gols_sofridos"] == 4
    assert s["saldo"] == 4
    # 3*3 + 1 = 10 pontos em 15 possíveis -> 66.7%
    assert s["aproveitamento"] == pytest.approx(66.7, abs=0.1)
    assert s["media_gols"] == pytest.approx(1.6)


def test_form_string_is_chronological(mini_db):
    assert team.form_string(mini_db, n=5, season_year=2026) == "V D V E V"


def test_home_away_split(mini_db):
    ha = team.home_away_split(mini_db, season_year=2026)
    assert ha["mandante"]["jogos"] == 3 and ha["mandante"]["vitorias"] == 3
    assert ha["visitante"]["jogos"] == 2 and ha["visitante"]["vitorias"] == 0


def test_evolution_windows(mini_db):
    ev = team.evolution(mini_db, windows=(3, 5), season_year=2026)
    assert list(ev["janela"]) == ["Últimos 3", "Últimos 5"]
    assert ev.iloc[0]["jogos"] == 3
    assert ev.iloc[1]["jogos"] == 5


def test_summary_empty_slice_returns_zeros_not_invented(mini_db):
    s = team.summary(mini_db, season_year=1999)
    assert s["jogos"] == 0
    assert s["media_gols"] is None
    assert s["aproveitamento"] is None
    assert s["forma"] == []


# ---------------------------------------------------------------------------
# JOGADORES / ARTILHARIA
# ---------------------------------------------------------------------------
def test_player_table_aggregates(mini_db):
    pt = players.player_table(mini_db, season_year=2026, min_matches=1)
    j10 = pt[pt["jogador"] == "Jogador 10"].iloc[0]
    assert j10["jogos"] == 5
    assert j10["gols"] == 4
    assert j10["assistencias"] == 2
    assert j10["participacao_gols"] == 6
    assert j10["nota_media"] == pytest.approx(round((7.5 + 6 + 8.4 + 6.5 + 7) / 5, 2))


def test_player_table_position_filter(mini_db):
    only_f = players.player_table(mini_db, season_year=2026, min_matches=1, position="F")
    assert set(only_f["jogador"]) == {"Jogador 10"}


def test_scorers_ranked_by_goals(mini_db):
    sc = scorers.scorers_table(mini_db, season_year=2026)
    assert sc.iloc[0]["jogador"] == "Jogador 10"
    assert sc.iloc[0]["gols"] == 4
    # jogador sem G nem A não aparece
    assert "Jogador 12" not in set(sc["jogador"]) or sc[sc["jogador"] == "Jogador 12"]["participacoes"].iloc[0] > 0


def test_scorers_last_n_window(mini_db):
    sc = scorers.scorers_table(mini_db, season_year=2026, last_n_matches=2)
    # últimos 2 jogos (ids 4 e 5): Jogador 10 fez 0 gols, 1 assist
    row = sc[sc["jogador"] == "Jogador 10"]
    if not row.empty:
        assert row.iloc[0]["gols"] == 0


# ---------------------------------------------------------------------------
# NOTAS + ÍNDICE DE PERFORMANCE
# ---------------------------------------------------------------------------
def test_rating_and_index_basic_fields(mini_db):
    ri = ratings.rating_and_index(mini_db, season_year=2026, min_matches=3)
    j10 = ri[ri["jogador"] == "Jogador 10"].iloc[0]
    assert j10["melhor_nota"] == 8.4
    assert j10["pior_nota"] == 6.0
    assert j10["nota_ult5"] == pytest.approx(j10["nota_media"])
    assert 0 <= j10["ips"] <= 12
    assert j10["confianca"] == pytest.approx(min(1.0, 450 / (90 * 6)), abs=0.01)


def test_performance_index_respects_min_matches(mini_db):
    ri = ratings.rating_and_index(mini_db, season_year=2026, min_matches=3)
    assert "Jogador 12" not in set(ri["jogador"])  # só 2 jogos


def test_index_blends_sofascore_and_raw(mini_db):
    ri = ratings.rating_and_index(mini_db, season_year=2026, min_matches=3, w_sofascore=1.0)
    j10 = ri[ri["jogador"] == "Jogador 10"].iloc[0]
    # com peso 1.0 na nota Sofascore, IPS == nota média
    assert j10["ips"] == pytest.approx(j10["nota_media"], abs=0.01)


def test_index_none_when_no_data(mini_db):
    """Jogador sem minutos e sem nota -> IPS None + limitação explicada."""
    mini_db.upsert("players", {"id": 20, "name": "Fantasma", "position": "M"}, pk=["id"])
    for mid in (1, 2, 3):
        mini_db.upsert("player_match_stats", {
            "match_id": mid, "player_id": 20, "team_id": 1976, "is_santacruz": 1,
            "started": 0, "substitute": 1, "minutes": None, "rating": None,
            "yellow_cards": 0, "red_cards": 0,
        }, pk=["match_id", "player_id"])
    mini_db.commit()
    ri = ratings.rating_and_index(mini_db, season_year=2026, min_matches=3)
    ghost = ri[ri["jogador"] == "Fantasma"].iloc[0]
    # numa coluna numérica, "sem valor" vira NaN — o importante é NÃO ser um número inventado
    assert ghost["ips"] is None or pd.isna(ghost["ips"])
    assert ghost["limitacao"] and "não calculado" in ghost["limitacao"].lower()
