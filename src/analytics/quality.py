"""Camada de qualidade de dados — auditoria do que está (ou não) no banco.

Não corrige nada silenciosamente: só relata. Cada checagem devolve uma
contagem real, consultada no SQLite — nada aqui é estimado.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional

from src.analytics import loaders
from src.database import Database


@dataclass
class Issue:
    severity: str          # "alta" | "média" | "baixa" | "info"
    titulo: str
    detalhe: str
    contagem: int


@dataclass
class QualityReport:
    score: float
    issues: list[Issue] = field(default_factory=list)
    health: dict = field(default_factory=dict)
    checked_at: str = ""


def _duplicate_matches(db: Database) -> int:
    row = db.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT date, home_team_id, away_team_id, COUNT(*) c
            FROM matches
            WHERE date IS NOT NULL
            GROUP BY date, home_team_id, away_team_id
            HAVING c > 1
        )
        """
    ).fetchone()
    return int(row[0] or 0)


def _matches_missing_date(db: Database) -> int:
    return db.scalar("SELECT COUNT(*) FROM matches WHERE status_type='finished' AND date IS NULL") or 0


def _matches_missing_score(db: Database) -> int:
    return db.scalar(
        "SELECT COUNT(*) FROM matches WHERE status_type='finished' "
        "AND (santacruz_gf IS NULL OR santacruz_ga IS NULL)"
    ) or 0


def _players_without_name(db: Database) -> int:
    return db.scalar("SELECT COUNT(*) FROM players WHERE name IS NULL OR TRIM(name) = ''") or 0


def _stat_inconsistencies(db: Database) -> int:
    """Contadores onde 'certo/no alvo' excede o total — impossível fisicamente."""
    return db.scalar(
        """
        SELECT COUNT(*) FROM player_match_stats
        WHERE (accurate_passes IS NOT NULL AND passes IS NOT NULL AND accurate_passes > passes)
           OR (shots_on_target IS NOT NULL AND shots IS NOT NULL AND shots_on_target > shots)
           OR (tackles_won IS NOT NULL AND tackles IS NOT NULL AND tackles_won > tackles)
           OR (minutes IS NOT NULL AND minutes > 130)
           OR (rating IS NOT NULL AND (rating < 0 OR rating > 10))
        """
    ) or 0


def _stale_notstarted(db: Database) -> int:
    """Partidas marcadas 'a agendar' cuja data já passou — sinal de que a fonte
    mudou o status (cancelada, adiada, jogada) e a coleta ainda não revisitou."""
    today = _dt.date.today().isoformat()
    return db.scalar(
        "SELECT COUNT(*) FROM matches WHERE status_type = 'notstarted' AND date < ?", (today,)
    ) or 0


def _orphan_player_stats(db: Database) -> int:
    return db.scalar(
        "SELECT COUNT(*) FROM player_match_stats pms "
        "LEFT JOIN matches m ON m.id = pms.match_id WHERE m.id IS NULL"
    ) or 0


def _stale_hours(db: Database) -> Optional[float]:
    last = db.get_meta("last_collection")
    if not last:
        return None
    try:
        dt = _dt.datetime.strptime(last, "%Y-%m-%d %H:%M").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None
    return (_dt.datetime.now(_dt.timezone.utc) - dt).total_seconds() / 3600.0


def run(db: Database) -> QualityReport:
    health = loaders.data_health(db)
    issues: list[Issue] = []

    dup = _duplicate_matches(db)
    if dup:
        issues.append(Issue("alta", "Partidas possivelmente duplicadas",
                            "Mesma data e mesmo par de times aparecendo mais de uma vez.", dup))

    miss_date = _matches_missing_date(db)
    if miss_date:
        issues.append(Issue("média", "Partidas finalizadas sem data",
                            "startTimestamp ausente na fonte para partida já encerrada.", miss_date))

    miss_score = _matches_missing_score(db)
    if miss_score:
        issues.append(Issue("alta", "Partidas finalizadas sem placar",
                            "Placar não veio da fonte para uma partida marcada como encerrada.", miss_score))

    no_name = _players_without_name(db)
    if no_name:
        issues.append(Issue("média", "Jogadores sem nome", "Registro de jogador sem nome.", no_name))

    incons = _stat_inconsistencies(db)
    if incons:
        issues.append(Issue("baixa", "Estatísticas fisicamente inconsistentes",
                            "Ex.: passes certos > passes totais, minutos > 130, nota fora de 0–10.", incons))

    orphan = _orphan_player_stats(db)
    if orphan:
        issues.append(Issue("média", "Estatística de jogador sem partida associada", "", orphan))

    stale_ns = _stale_notstarted(db)
    if stale_ns:
        issues.append(Issue("média", "Partidas 'a agendar' com data no passado",
                            "O status da fonte provavelmente mudou (jogada/cancelada/adiada) "
                            "e a próxima coleta deve corrigir.", stale_ns))

    finished = health["matches_finished"] or 0
    lineup_cov = health["matches_with_lineups"] / finished if finished else None
    stats_cov = health["matches_with_player_stats"] / finished if finished else None
    heat_cov = health["matches_with_heatmap"] / finished if finished else None

    if finished and stats_cov is not None and stats_cov < 0.5:
        issues.append(Issue("info", "Cobertura baixa de estatística individual",
                            f"Só {stats_cov:.0%} das partidas finalizadas têm estatística por jogador na fonte "
                            "(competições menores costumam não ter).", finished - health["matches_with_player_stats"]))

    stale_h = _stale_hours(db)
    if stale_h is not None and stale_h > 48:
        issues.append(Issue("baixa", "Coleta desatualizada",
                            f"Última coleta há {stale_h:.0f}h.", int(stale_h)))
    elif stale_h is None:
        issues.append(Issue("média", "Nunca houve coleta registrada", "", 0))

    # score 0-100: cobertura (50%) + ausência de inconsistências graves (30%) + frescor (20%)
    cov_score = 100 * (sum(x for x in (lineup_cov, stats_cov, heat_cov) if x is not None) /
                       max(1, len([x for x in (lineup_cov, stats_cov, heat_cov) if x is not None]))) if finished else 0
    penalty = min(30, 6 * sum(1 for i in issues if i.severity in ("alta", "média")))
    fresh_score = 20 if (stale_h is not None and stale_h <= 48) else (10 if stale_h is not None else 0)
    score = round(max(0.0, min(100.0, 0.5 * cov_score + (30 - penalty) + fresh_score)), 1)

    return QualityReport(
        score=score, issues=issues, health=health,
        checked_at=_dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
