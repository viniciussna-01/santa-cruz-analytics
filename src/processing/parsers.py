"""Funções puras que convertem payloads do Sofascore em dicts prontos p/ o banco.

Nenhuma faz I/O — recebem JSON (dict) e devolvem dict/list. Isso as torna
triviais de testar com as fixtures em tests/fixtures/.

Princípio: campo ausente -> None (nunca 0 inventado), exceto contadores que a
própria fonte omite quando são zero (passes, chutes...) — nesses casos 0 é o
valor real e usamos `or 0` explicitamente só onde faz sentido.
"""
from __future__ import annotations

from typing import Any, Optional

from src.utils.helpers import result_letter, safe_get, to_float, to_int, ts_to_date

# --- mapeamento chave Sofascore -> coluna do banco (stats por jogador) --------
# valor: (coluna, conversor)
_PLAYER_STAT_MAP: dict[str, tuple[str, Any]] = {
    "minutesPlayed": ("minutes", to_int),
    "rating": ("rating", to_float),
    "goals": ("goals", to_int),
    "goalAssist": ("assists", to_int),
    "ownGoals": ("own_goals", to_int),
    "totalShots": ("shots", to_int),
    "onTargetScoringAttempt": ("shots_on_target", to_int),
    "shotOffTarget": ("shots_off_target", to_int),
    "bigChanceCreated": ("big_chances_created", to_int),
    "bigChanceMissed": ("big_chances_missed", to_int),
    "expectedGoals": ("xg", to_float),
    "expectedAssists": ("xa", to_float),
    "totalPass": ("passes", to_int),
    "accuratePass": ("accurate_passes", to_int),
    "keyPass": ("key_passes", to_int),
    "totalCross": ("crosses", to_int),
    "accurateCross": ("accurate_crosses", to_int),
    "totalLongBalls": ("long_balls", to_int),
    "accurateLongBalls": ("accurate_long_balls", to_int),
    "totalTackle": ("tackles", to_int),
    "wonTackle": ("tackles_won", to_int),
    "interceptionWon": ("interceptions", to_int),
    "totalClearance": ("clearances", to_int),
    "outfielderBlock": ("blocks", to_int),
    "duelWon": ("duels_won", to_int),
    "duelLost": ("duels_lost", to_int),
    "aerialWon": ("aerials_won", to_int),
    "aerialLost": ("aerials_lost", to_int),
    "ballRecovery": ("ball_recoveries", to_int),
    "touches": ("touches", to_int),
    "possessionLostCtrl": ("possession_lost", to_int),
    "dispossessed": ("dispossessed", to_int),
    "fouls": ("fouls", to_int),
    "wasFouled": ("was_fouled", to_int),
    "penaltyWon": ("penalty_won", to_int),
    "saves": ("saves", to_int),
    "savedShotsFromInsideTheBox": ("saved_shots_in_box", to_int),
    "errorLeadToAShot": ("error_led_to_shot", to_int),
}

_PLAYER_STAT_COLS = [c for c, _ in _PLAYER_STAT_MAP.values()]


# ---------------------------------------------------------------------------
# EVENTO / PARTIDA
# ---------------------------------------------------------------------------
def parse_event(event: dict, santacruz_team_id: int) -> dict:
    home = event.get("homeTeam", {}) or {}
    away = event.get("awayTeam", {}) or {}
    hs = safe_get(event, "homeScore", "current")
    as_ = safe_get(event, "awayScore", "current")
    is_home = home.get("id") == santacruz_team_id
    gf = ga = None
    if hs is not None and as_ is not None:
        gf, ga = (hs, as_) if is_home else (as_, hs)

    opponent = away if is_home else home
    tournament = event.get("tournament", {}) or {}
    ut = tournament.get("uniqueTournament", {}) or {}
    season = event.get("season", {}) or {}
    status_type = safe_get(event, "status", "type")

    return {
        "id": event.get("id"),
        "date": ts_to_date(event.get("startTimestamp")),
        "start_timestamp": event.get("startTimestamp"),
        "competition_name": tournament.get("name") or ut.get("name"),
        "unique_tournament_id": ut.get("id"),
        "season_id": season.get("id"),
        "season_year": season.get("year"),
        "round": safe_get(event, "roundInfo", "round"),
        "home_team_id": home.get("id"),
        "away_team_id": away.get("id"),
        "home_team_name": home.get("name"),
        "away_team_name": away.get("name"),
        "home_score": to_int(hs),
        "away_score": to_int(as_),
        "status": safe_get(event, "status", "description"),
        "status_type": status_type,
        "winner_code": event.get("winnerCode"),
        "venue": safe_get(event, "venue", "stadium", "name"),
        "is_santacruz_home": 1 if is_home else 0,
        "santacruz_gf": gf,
        "santacruz_ga": ga,
        "santacruz_result": result_letter(gf, ga) if status_type == "finished" else None,
        "opponent_id": opponent.get("id"),
        "opponent_name": opponent.get("name"),
        "has_event_player_statistics": bool(event.get("hasEventPlayerStatistics")),
        "has_event_player_heatmap": bool(event.get("hasEventPlayerHeatMap")),
    }


def team_rows_from_event(event: dict) -> list[dict]:
    rows = []
    for side in ("homeTeam", "awayTeam"):
        t = event.get(side) or {}
        if t.get("id"):
            rows.append(
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "short_name": t.get("nameCode"),
                    "slug": t.get("slug"),
                    "country": safe_get(t, "country", "name"),
                }
            )
    return rows


# ---------------------------------------------------------------------------
# ESCALAÇÃO + STATS POR JOGADOR
# ---------------------------------------------------------------------------
def parse_lineups(
    lineups: dict, event: dict, santacruz_team_id: int
) -> tuple[list[dict], list[dict], bool]:
    """Retorna (players, player_match_stats, tem_ratings)."""
    players: list[dict] = []
    stats_rows: list[dict] = []
    any_rating = False
    if not lineups:
        return players, stats_rows, any_rating

    home_id = safe_get(event, "homeTeam", "id")
    away_id = safe_get(event, "awayTeam", "id")
    match_id = event.get("id")

    for side, team_id in (("home", home_id), ("away", away_id)):
        block = lineups.get(side) or {}
        for entry in block.get("players", []) or []:
            p = entry.get("player") or {}
            pid = p.get("id")
            if not pid:
                continue
            position = entry.get("position") or p.get("position")
            players.append(
                {
                    "id": pid,
                    "name": p.get("name"),
                    "short_name": p.get("shortName"),
                    "position": position,
                    "team_id": team_id,
                    "country": safe_get(p, "country", "name"),
                    "dob_timestamp": p.get("dateOfBirthTimestamp"),
                }
            )

            raw = entry.get("statistics") or {}
            row: dict[str, Any] = {
                "match_id": match_id,
                "player_id": pid,
                "team_id": team_id,
                "is_santacruz": 1 if team_id == santacruz_team_id else 0,
                "position": position,
                "jersey": to_int(entry.get("jerseyNumber") or entry.get("shirtNumber")),
                "substitute": 1 if entry.get("substitute") else 0,
                "started": 0 if entry.get("substitute") else 1,
                "yellow_cards": 0,
                "red_cards": 0,
            }
            for col in _PLAYER_STAT_COLS:
                row.setdefault(col, None)
            for skey, (col, conv) in _PLAYER_STAT_MAP.items():
                if skey in raw:
                    row[col] = conv(raw[skey])
            # titular que não tem stats mas jogou: minutos podem faltar -> None
            if row.get("rating") is not None:
                any_rating = True
            stats_rows.append(row)

    return players, stats_rows, any_rating


# ---------------------------------------------------------------------------
# INCIDENTES (gols, cartões, substituições)
# ---------------------------------------------------------------------------
def parse_incidents(incidents: list[dict], event: dict, santacruz_team_id: int) -> list[dict]:
    match_id = event.get("id")
    home_id = safe_get(event, "homeTeam", "id")
    rows = []
    for inc in incidents or []:
        itype = inc.get("incidentType")
        if itype not in ("goal", "card", "substitution"):
            continue
        is_home = inc.get("isHome")
        team_id = home_id if is_home else safe_get(event, "awayTeam", "id")
        rows.append(
            {
                "match_id": match_id,
                "minute": inc.get("time"),
                "added_time": inc.get("addedTime"),
                "type": itype,
                "sub_type": inc.get("incidentClass"),
                "is_home": 1 if is_home else 0,
                "is_santacruz": 1 if team_id == santacruz_team_id else 0,
                "player_id": safe_get(inc, "player", "id"),
                "player_name": safe_get(inc, "player", "name"),
                "assist_player_id": safe_get(inc, "assist1", "id"),
                "assist_player_name": safe_get(inc, "assist1", "name"),
                "player_in_id": safe_get(inc, "playerIn", "id"),
                "player_in_name": safe_get(inc, "playerIn", "name"),
                "player_out_id": safe_get(inc, "playerOut", "id"),
                "player_out_name": safe_get(inc, "playerOut", "name"),
            }
        )
    return rows


def card_counts_from_incidents(incidents: list[dict]) -> dict[int, dict[str, int]]:
    """{player_id: {'yellow_cards': n, 'red_cards': n}} — para reconciliar com stats."""
    out: dict[int, dict[str, int]] = {}
    for inc in incidents or []:
        if inc.get("incidentType") != "card":
            continue
        pid = safe_get(inc, "player", "id")
        if not pid:
            continue
        cls = (inc.get("incidentClass") or "").lower()
        d = out.setdefault(pid, {"yellow_cards": 0, "red_cards": 0})
        if cls in ("red", "yellowred"):
            d["red_cards"] += 1
        if cls in ("yellow", "yellowred"):
            d["yellow_cards"] += 1
    return out


def goals_assists_from_incidents(incidents: list[dict]) -> dict[int, dict[str, int]]:
    """Fallback quando não há stats por jogador: conta gols/assist. via incidentes."""
    out: dict[int, dict[str, int]] = {}
    for inc in incidents or []:
        if inc.get("incidentType") != "goal":
            continue
        cls = (inc.get("incidentClass") or "").lower()
        scorer = safe_get(inc, "player", "id")
        if scorer and cls != "owngoal":
            out.setdefault(scorer, {}).setdefault("goals", 0)
            out[scorer]["goals"] += 1
        assist = safe_get(inc, "assist1", "id")
        if assist:
            out.setdefault(assist, {}).setdefault("assists", 0)
            out[assist]["assists"] += 1
    return out


# ---------------------------------------------------------------------------
# ESTATÍSTICAS DA PARTIDA (nível time)
# ---------------------------------------------------------------------------
def parse_match_statistics(stats: dict, event: dict, santacruz_team_id: int) -> list[dict]:
    if not stats:
        return []
    match_id = event.get("id")
    home_id = safe_get(event, "homeTeam", "id")
    away_id = safe_get(event, "awayTeam", "id")
    rows = []
    for period_block in stats.get("statistics", []) or []:
        period = period_block.get("period", "ALL")
        for group in period_block.get("groups", []) or []:
            gname = group.get("groupName")
            for item in group.get("statisticsItems", []) or []:
                for team_id, disp_key, val_key in (
                    (home_id, "home", "homeValue"),
                    (away_id, "away", "awayValue"),
                ):
                    rows.append(
                        {
                            "match_id": match_id,
                            "team_id": team_id,
                            "is_santacruz": 1 if team_id == santacruz_team_id else 0,
                            "period": period,
                            "group_name": gname,
                            "key": item.get("key"),
                            "name": item.get("name"),
                            "value": to_float(item.get(val_key)),
                            "display": str(item.get(disp_key)),
                        }
                    )
    return rows


# ---------------------------------------------------------------------------
# CLASSIFICAÇÃO
# ---------------------------------------------------------------------------
def parse_standings(standings: dict, snapshot_date: str) -> list[dict]:
    """`standings/total` pode trazer MAIS DE UMA tabela no mesmo payload —
    ex.: a classificação geral (20 times) e sub-grupos de uma fase final
    ("Main Round, Group B", com poucos jogos). Para não misturar tabelas
    diferentes num só snapshot, usamos só a tabela com mais linhas (a
    classificação geral)."""
    rows = []
    tables = (standings or {}).get("standings", []) or []
    if not tables:
        return rows
    main_table = max(tables, key=lambda t: len(t.get("rows", []) or []))
    for r in main_table.get("rows", []) or []:
            team = r.get("team", {}) or {}
            rows.append(
                {
                    "team_id": team.get("id"),
                    "team_name": team.get("name"),
                    "position": r.get("position"),
                    "points": r.get("points"),
                    "played": r.get("matches"),
                    "wins": r.get("wins"),
                    "draws": r.get("draws"),
                    "losses": r.get("losses"),
                    "goals_for": r.get("scoresFor"),
                    "goals_against": r.get("scoresAgainst"),
                    "snapshot_date": snapshot_date,
                }
            )
    return rows
