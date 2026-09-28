"""Configuração central do Santa Cruz Analytics.

Todos os valores têm padrão seguro. `.env` é opcional e só serve para
sobrescrever (ex.: trocar o time, número de páginas, throttle).
"""
from __future__ import annotations

import os
from pathlib import Path

try:  # dotenv é opcional
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - ambiente sem python-dotenv
    pass


# ----------------------------------------------------------------------------
# Caminhos
# ----------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_DIR = DATA_DIR / "database"
DB_PATH = DB_DIR / "santacruz.db"
DOCS_DIR = ROOT_DIR / "docs"

for _d in (RAW_DIR, DB_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------
# Time / temporada alvo
# ----------------------------------------------------------------------------
SANTACRUZ_TEAM_ID = _int("SANTACRUZ_TEAM_ID", 1976)
SANTACRUZ_TEAM_NAME = "Santa Cruz"
SEASON_YEAR = _int("SANTACRUZ_SEASON_YEAR", 2026)

# ----------------------------------------------------------------------------
# Coleta
# ----------------------------------------------------------------------------
COLLECT_MAX_PAGES = _int("COLLECT_MAX_PAGES", 3)
HTTP_THROTTLE_SECONDS = _float("HTTP_THROTTLE_SECONDS", 0.35)
HTTP_TIMEOUT = _int("HTTP_TIMEOUT", 25)
HTTP_MAX_RETRIES = _int("HTTP_MAX_RETRIES", 3)

# ----------------------------------------------------------------------------
# Fonte
# ----------------------------------------------------------------------------
SOFASCORE_HOST = os.getenv("SOFASCORE_HOST", "https://api.sofascore.com").rstrip("/")
SOFASCORE_FALLBACK_HOSTS = [
    "https://www.sofascore.com",
    "https://api.sofascore.app",
]
BROWSER_IMPERSONATE = os.getenv("BROWSER_IMPERSONATE", "chrome")

# Status Sofascore considerados "jogo terminado" (dados finais e estáveis)
FINISHED_STATUS_TYPES = {"finished"}
# Status que ainda podem mudar -> sempre re-coletar
LIVE_STATUS_TYPES = {"inprogress", "notstarted"}
