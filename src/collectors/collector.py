"""Coletor incremental do Santa Cruz.

Fluxo:
  1. identifica o Santa Cruz (id fixo 1976, validado na Fase 1)
  2. lista jogos passados (events/last) + próximos (events/next)
  3. para cada jogo novo OU ainda sem detalhes: baixa evento, escalação,
     estatísticas, incidentes e mapa de calor (quando disponível)
  4. grava tudo no SQLite

Incremental: jogo já finalizado e com escalação salva NÃO é rebaixado.
Erros em um jogo nunca derrubam a coleta inteira.
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Optional

from src import config
from src.api import SofascoreClient, SofascoreError
from src.database import Database, get_db
from src.processing import parsers
from src.utils.helpers import safe_get
from src.utils.logging_utils import get_logger

log = get_logger("santacruz.collector")


class Collector:
    def __init__(
        self,
        db: Optional[Database] = None,
        client: Optional[SofascoreClient] = None,
        team_id: int = config.SANTACRUZ_TEAM_ID,
    ) -> None:
        self.db = db or get_db()
        self.api = client or SofascoreClient()
        self.team_id = team_id
        self.now_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------------
    def identify_team(self) -> dict:
        team = None
        try:
            team = self.api.get_team(self.team_id)
        except SofascoreError as exc:
            log.warning("Não consegui detalhar o time (%s). Sigo com o id configurado.", exc)
        if team and team.get("id") == self.team_id:
            log.info("Santa Cruz encontrado — id %s (%s, %s)", self.team_id, team.get("name"),
                     safe_get(team, "venue", "city", "name") or "?")
            self.db.upsert(
                "teams",
                {
                    "id": team.get("id"),
                    "name": team.get("name"),
                    "short_name": team.get("nameCode"),
                    "slug": team.get("slug"),
                    "country": safe_get(team, "country", "name"),
                },
                pk=["id"],
            )
        else:
            log.info("Santa Cruz assumido pelo id configurado: %s", self.team_id)
            self.db.upsert(
                "teams",
                {"id": self.team_id, "name": config.SANTACRUZ_TEAM_NAME},
                pk=["id"],
            )
        self.db.commit()
        return team or {"id": self.team_id, "name": config.SANTACRUZ_TEAM_NAME}

    # ------------------------------------------------------------------
    def list_matches(self, max_pages: int = config.COLLECT_MAX_PAGES) -> list[dict]:
        events: dict[int, dict] = {}
        for page in range(max_pages):
            try:
                block = self.api.team_events_last(self.team_id, page)
            except SofascoreError as exc:
                log.warning("Falha ao listar página %d de jogos: %s", page, exc)
                break
            for ev in block.get("events", []):
                events[ev["id"]] = ev
            if not block.get("hasNextPage"):
                break
        # próximos jogos (para "próximo jogo" no dashboard)
        try:
            nxt = self.api.team_events_next(self.team_id, 0)
            for ev in nxt.get("events", [])[:10]:
                events[ev["id"]] = ev
        except SofascoreError as exc:
            log.warning("Falha ao listar próximos jogos: %s", exc)

        ordered = sorted(events.values(), key=lambda e: e.get("startTimestamp") or 0)
        log.info("%d partidas encontradas (passadas + próximas)", len(ordered))
        return ordered

    # ------------------------------------------------------------------
    def _save_event_shell(self, event: dict) -> int:
        parsed = parsers.parse_event(event, self.team_id)
        comp_id = self.db.competition_id_for(
            parsed.pop("unique_tournament_id") or 0,
            parsed.pop("season_id"),
            parsed.get("competition_name") or "Desconhecida",
            str(parsed.pop("season_year")) if parsed.get("season_year") is not None else None,
        )
        parsed.pop("season_year", None)
        parsed.pop("has_event_player_statistics", None)
        parsed.pop("has_event_player_heatmap", None)
        parsed["competition_id"] = comp_id
        parsed["collected_at"] = self.now_iso
        for t in parsers.team_rows_from_event(event):
            self.db.upsert("teams", t, pk=["id"])
        self.db.upsert("matches", parsed, pk=["id"])
        self.db.commit()
        return parsed["id"]

    def _process_match_details(self, event_id: int) -> None:
        log.info("Processando partida %s", event_id)
        try:
            event = self.api.get_event(event_id)
        except SofascoreError as exc:
            log.warning("  evento %s indisponível: %s", event_id, exc)
            return
        if not event:
            log.warning("  evento %s não encontrado", event_id)
            return
        self._save_event_shell(event)

        status_type = safe_get(event, "status", "type")
        if status_type != "finished":
            log.info("  partida ainda não finalizada (%s) — detalhes serão baixados depois",
                     safe_get(event, "status", "description"))
            return

        incidents = []
        try:
            incidents = self.api.event_incidents(event_id)
        except SofascoreError as exc:
            log.warning("  incidentes indisponíveis: %s", exc)
        inc_rows = parsers.parse_incidents(incidents, event, self.team_id)
        if inc_rows:
            self.db.execute("DELETE FROM match_incidents WHERE match_id = ?", (event_id,))
            for r in inc_rows:
                self.db.upsert("match_incidents", r, pk=["match_id", "minute", "type", "player_name", "player_in_name"])
            log.info("  %d incidentes (gols/cartões/subs)", len(inc_rows))

        # escalação + stats por jogador
        lineups = None
        try:
            lineups = self.api.event_lineups(event_id)
        except SofascoreError as exc:
            log.warning("  escalação indisponível: %s", exc)

        has_lineups = 0
        has_player_stats = 0
        players, stat_rows, any_rating = parsers.parse_lineups(lineups, event, self.team_id)
        if players:
            has_lineups = 1
            log.info("  escalação encontrada — %d jogadores", len(players))
            for p in players:
                self.db.upsert("players", p, pk=["id"])

            card_counts = parsers.card_counts_from_incidents(incidents)
            ga_fallback = parsers.goals_assists_from_incidents(incidents)
            self.db.execute("DELETE FROM player_match_stats WHERE match_id = ?", (event_id,))
            n_with_stats = 0
            for row in stat_rows:
                pid = row["player_id"]
                cc = card_counts.get(pid)
                if cc:
                    row["yellow_cards"] = cc["yellow_cards"]
                    row["red_cards"] = cc["red_cards"]
                # fallback gols/assist quando a fonte não trouxe stats individuais
                if row.get("goals") is None and pid in ga_fallback:
                    row["goals"] = ga_fallback[pid].get("goals", 0)
                if row.get("assists") is None and pid in ga_fallback:
                    row["assists"] = ga_fallback[pid].get("assists", 0)
                if row.get("rating") is not None or row.get("minutes") is not None:
                    n_with_stats += 1
                self.db.upsert("player_match_stats", row, pk=["match_id", "player_id"])
            has_player_stats = 1 if any_rating or n_with_stats else 0
            log.info("  estatísticas individuais: %s (%d jogadores com dados)",
                     "encontradas" if has_player_stats else "ausentes nesta competição", n_with_stats)
        else:
            log.info("  escalação não disponível para esta partida")

        # estatísticas da partida (nível time)
        try:
            mstats = self.api.event_statistics(event_id)
        except SofascoreError as exc:
            mstats = None
            log.warning("  estatísticas da partida indisponíveis: %s", exc)
        st_rows = parsers.parse_match_statistics(mstats, event, self.team_id)
        if st_rows:
            self.db.execute("DELETE FROM match_team_stats WHERE match_id = ?", (event_id,))
            for r in st_rows:
                self.db.upsert("match_team_stats", r, pk=["match_id", "team_id", "period", "key"])
            log.info("  estatísticas da partida encontradas (%d itens)", len(st_rows))

        # mapa de calor (só jogadores do Santa Cruz que atuaram)
        has_heatmap = self._collect_heatmaps(event_id, stat_rows)

        self.db.upsert(
            "matches",
            {
                "id": event_id,
                "has_lineups": has_lineups,
                "has_player_stats": has_player_stats,
                "has_heatmap": has_heatmap,
                "collected_at": self.now_iso,
            },
            pk=["id"],
        )
        self.db.commit()
        log.info("  partida %s salva", event_id)

    def _collect_heatmaps(self, event_id: int, stat_rows: list[dict]) -> int:
        santacruz_players = [
            r for r in stat_rows
            if r.get("is_santacruz") == 1 and (r.get("minutes") or 0) > 0
        ]
        if not santacruz_players:
            return 0
        saved = 0
        for r in santacruz_players:
            pid = r["player_id"]
            exists = self.db.scalar(
                "SELECT 1 FROM player_heatmap WHERE match_id = ? AND player_id = ?",
                (event_id, pid),
            )
            if exists:
                saved += 1
                continue
            try:
                points = self.api.player_heatmap(event_id, pid)
            except SofascoreError as exc:
                log.warning("  heatmap do jogador %s indisponível: %s", pid, exc)
                continue
            if not points:
                continue
            self.db.upsert(
                "player_heatmap",
                {
                    "match_id": event_id,
                    "player_id": pid,
                    "points_json": json.dumps(points, ensure_ascii=False),
                    "point_count": len(points),
                    "collected_at": self.now_iso,
                },
                pk=["match_id", "player_id"],
            )
            saved += 1
        if saved:
            log.info("  mapa de calor: %d jogadores", saved)
        return 1 if saved else 0

    # ------------------------------------------------------------------
    def collect_standings(self) -> None:
        row = self.db.execute(
            "SELECT c.unique_tournament_id, c.season_id, c.id, c.name "
            "FROM competitions c JOIN matches m ON m.competition_id = c.id "
            "WHERE m.status_type = 'finished' AND c.season_id IS NOT NULL "
            "GROUP BY c.id ORDER BY MAX(m.start_timestamp) DESC LIMIT 1"
        ).fetchone()
        if not row:
            return
        ut_id, season_id, comp_id, name = row
        try:
            data = self.api.standings(ut_id, season_id)
        except SofascoreError as exc:
            log.warning("Classificação indisponível: %s", exc)
            return
        today = _dt.date.today().isoformat()
        rows = parsers.parse_standings(data, today)
        for r in rows:
            r["competition_id"] = comp_id
            self.db.upsert("standings_snapshot", r, pk=["competition_id", "team_id", "snapshot_date"])
        self.db.commit()
        if rows:
            log.info("Classificação de %s salva (%d times)", name, len(rows))

    # ------------------------------------------------------------------
    def run(self, max_pages: int = config.COLLECT_MAX_PAGES, force: bool = False) -> dict:
        log.info("=== Coleta Santa Cruz Analytics — %s ===", self.now_iso)
        self.identify_team()
        matches = self.list_matches(max_pages)

        processed = skipped = failed = 0
        for ev in matches:
            mid = ev["id"]
            if not force and not self.db.match_needs_details(mid):
                skipped += 1
                continue
            try:
                self._process_match_details(mid)
                processed += 1
            except Exception as exc:  # noqa: BLE001 - um jogo com erro não para tudo
                failed += 1
                log.exception("Erro ao processar partida %s: %s", mid, exc)

        try:
            self.collect_standings()
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao coletar classificação: %s", exc)

        self.db.set_meta("last_collection", self.now_iso)
        self.db.set_meta("last_collection_processed", str(processed))
        log.info(
            "=== Fim: %d processadas, %d já atualizadas, %d com erro ===",
            processed, skipped, failed,
        )
        return {"processed": processed, "skipped": skipped, "failed": failed, "total": len(matches)}


def run_collection(max_pages: int = config.COLLECT_MAX_PAGES, force: bool = False) -> dict:
    """Ponto de entrada usado pelo CLI e pelo botão do dashboard."""
    return Collector().run(max_pages=max_pages, force=force)
