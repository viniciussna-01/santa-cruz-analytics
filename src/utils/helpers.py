"""Funções auxiliares puras (sem I/O) — fáceis de testar."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def ts_to_iso(timestamp: Optional[int]) -> Optional[str]:
    """Timestamp UNIX (segundos) -> 'YYYY-MM-DD HH:MM' em UTC."""
    if timestamp in (None, 0):
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def ts_to_date(timestamp: Optional[int]) -> Optional[str]:
    if timestamp in (None, 0):
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d")


def safe_get(dct: Any, *keys: Any, default: Any = None) -> Any:
    """Acesso aninhado tolerante: safe_get(d, 'a', 'b', default=0)."""
    cur = dct
    for key in keys:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        elif isinstance(cur, (list, tuple)) and isinstance(key, int) and -len(cur) <= key < len(cur):
            cur = cur[key]
        else:
            return default
    return cur if cur is not None else default


def to_float(value: Any) -> Optional[float]:
    """Converte para float ou devolve None (nunca inventa 0)."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> Optional[int]:
    f = to_float(value)
    return int(f) if f is not None else None


def pct(part: float, whole: float, ndigits: int = 1) -> Optional[float]:
    """Percentual seguro. whole==0 -> None."""
    if not whole:
        return None
    return round(100.0 * part / whole, ndigits)


def age_years(dob_timestamp: Optional[int]) -> Optional[int]:
    """Idade atual a partir da data de nascimento (timestamp UNIX). None se ausente."""
    if not dob_timestamp:
        return None
    dob = datetime.fromtimestamp(int(dob_timestamp), tz=timezone.utc)
    today = datetime.now(timezone.utc)
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return years


def result_letter(gf: Optional[int], ga: Optional[int]) -> Optional[str]:
    """'V' / 'E' / 'D' a partir do placar do ponto de vista do time."""
    if gf is None or ga is None:
        return None
    if gf > ga:
        return "V"
    if gf < ga:
        return "D"
    return "E"
