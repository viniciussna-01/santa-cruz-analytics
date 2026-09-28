"""Cliente HTTP para a API pública (não-oficial) do Sofascore.

Todos os endpoints abaixo foram testados com requisições reais em 2026-08-31
(ver docs/PESQUISA_FASE1.md). A API não é documentada e pode mudar.

Ponto crítico: `requests`/`httpx` puros recebem HTTP 403 (Cloudflare / TLS
fingerprint). Só funciona com `curl_cffi` usando `impersonate="chrome"`.

Contrato de erros:
* 404 / recurso ausente  -> retorna ``None`` (não é erro; ex.: reserva sem heatmap)
* rede / 403 / 5xx        -> tenta retry+backoff e hosts alternativos;
                             se tudo falhar, lança ``SofascoreError``.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from curl_cffi import requests as cr

from src import config
from src.utils.logging_utils import get_logger

log = get_logger(__name__)


class SofascoreError(RuntimeError):
    """Falha irrecuperável ao falar com o Sofascore."""


_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}


class SofascoreClient:
    def __init__(
        self,
        host: str | None = None,
        throttle: float | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        cache_raw: bool = True,
    ) -> None:
        self.hosts = [host or config.SOFASCORE_HOST] + [
            h for h in config.SOFASCORE_FALLBACK_HOSTS if h != (host or config.SOFASCORE_HOST)
        ]
        self.throttle = config.HTTP_THROTTLE_SECONDS if throttle is None else throttle
        self.timeout = config.HTTP_TIMEOUT if timeout is None else timeout
        self.max_retries = config.HTTP_MAX_RETRIES if max_retries is None else max_retries
        self.cache_raw = cache_raw
        self._last_call = 0.0

    # ------------------------------------------------------------------
    # infra
    # ------------------------------------------------------------------
    def _sleep_throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self.throttle:
            time.sleep(self.throttle - elapsed)
        self._last_call = time.time()

    def _raw_path(self, path: str) -> Path:
        safe = path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-")
        return config.RAW_DIR / f"{safe}.json"

    def _get(self, path: str, *, allow_404: bool = True) -> Optional[dict]:
        """GET em ``/api/v1/<path>``. Retorna dict, ou None se 404."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            for host in self.hosts:
                url = f"{host}/api/v1/{path.lstrip('/')}"
                self._sleep_throttle()
                try:
                    resp = cr.get(
                        url,
                        headers=_HEADERS,
                        impersonate=config.BROWSER_IMPERSONATE,
                        timeout=self.timeout,
                    )
                except Exception as exc:  # rede caiu, DNS, etc.
                    last_exc = exc
                    log.warning("Falha de rede em %s (tentativa %d): %s", url, attempt, exc)
                    continue

                if resp.status_code == 404:
                    if allow_404:
                        return None
                    last_exc = SofascoreError(f"404 em {url}")
                    continue
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except Exception as exc:
                        last_exc = exc
                        log.warning("JSON inválido em %s: %s", url, exc)
                        continue
                    if self.cache_raw:
                        try:
                            self._raw_path(path).write_text(
                                json.dumps(data, ensure_ascii=False), encoding="utf-8"
                            )
                        except OSError:
                            pass
                    return data
                if resp.status_code == 429:
                    wait = min(30, 2 ** attempt)
                    log.warning("Rate limit (429) em %s — aguardando %ds", url, wait)
                    time.sleep(wait)
                    last_exc = SofascoreError(f"429 em {url}")
                    continue
                # 403 / 5xx -> tenta próximo host / próxima rodada
                last_exc = SofascoreError(f"HTTP {resp.status_code} em {url}")
                log.warning("HTTP %s em %s (tentativa %d)", resp.status_code, url, attempt)

            time.sleep(min(10, 2 ** attempt))  # backoff entre rodadas

        raise SofascoreError(
            f"Não foi possível obter '{path}' após {self.max_retries} tentativas: {last_exc}"
        )

    # ------------------------------------------------------------------
    # endpoints (todos validados)
    # ------------------------------------------------------------------
    def search_teams(self, query: str) -> list[dict]:
        data = self._get(f"search/all?q={quote(query)}")
        results = (data or {}).get("results", [])
        return [r["entity"] for r in results if r.get("type") == "team" and r.get("entity")]

    def get_team(self, team_id: int) -> Optional[dict]:
        data = self._get(f"team/{team_id}")
        return (data or {}).get("team") if data else None

    def team_events_last(self, team_id: int, page: int = 0) -> dict:
        return self._get(f"team/{team_id}/events/last/{page}") or {"events": [], "hasNextPage": False}

    def team_events_next(self, team_id: int, page: int = 0) -> dict:
        return self._get(f"team/{team_id}/events/next/{page}") or {"events": [], "hasNextPage": False}

    def get_event(self, event_id: int) -> Optional[dict]:
        data = self._get(f"event/{event_id}")
        return (data or {}).get("event") if data else None

    def event_lineups(self, event_id: int) -> Optional[dict]:
        return self._get(f"event/{event_id}/lineups")

    def event_statistics(self, event_id: int) -> Optional[dict]:
        return self._get(f"event/{event_id}/statistics")

    def event_incidents(self, event_id: int) -> list[dict]:
        data = self._get(f"event/{event_id}/incidents")
        return (data or {}).get("incidents", [])

    def event_managers(self, event_id: int) -> Optional[dict]:
        return self._get(f"event/{event_id}/managers")

    def event_best_players(self, event_id: int) -> Optional[dict]:
        return self._get(f"event/{event_id}/best-players")

    def player_heatmap(self, event_id: int, player_id: int) -> Optional[list[dict]]:
        """Retorna lista [{'x':..,'y':..}] ou None (reserva que não jogou = 404)."""
        data = self._get(f"event/{event_id}/player/{player_id}/heatmap")
        return (data or {}).get("heatmap") if data else None

    def average_positions(self, event_id: int) -> Optional[dict]:
        return self._get(f"event/{event_id}/average-positions")

    def standings(self, unique_tournament_id: int, season_id: int, kind: str = "total") -> Optional[dict]:
        return self._get(
            f"unique-tournament/{unique_tournament_id}/season/{season_id}/standings/{kind}"
        )
