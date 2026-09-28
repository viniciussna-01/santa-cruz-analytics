"""Acesso ao SQLite: init do schema, upserts e consultas utilitárias."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

from src import config
from src.utils.logging_utils import get_logger

log = get_logger(__name__)

_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, path: str | Path | None = None, check_same_thread: bool = True) -> None:
        self.path = str(path or config.DB_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    # ------------------------------------------------------------------
    def init_schema(self) -> None:
        self.conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.conn.commit()
        self.close()

    # ------------------------------------------------------------------
    # helpers genéricos
    # ------------------------------------------------------------------
    def upsert(self, table: str, row: dict, pk: Iterable[str]) -> None:
        """INSERT ... ON CONFLICT(pk) DO UPDATE. Ignora chaves com valor None
        na hora do UPDATE? Não: gravamos None (=NULL) de propósito."""
        row = {k: v for k, v in row.items() if v is not None or True}
        cols = list(row.keys())
        placeholders = ", ".join("?" for _ in cols)
        collist = ", ".join(cols)
        pk_list = ", ".join(pk)
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in set(pk))
        sql = f"INSERT INTO {table} ({collist}) VALUES ({placeholders})"
        if updates:
            sql += f" ON CONFLICT({pk_list}) DO UPDATE SET {updates}"
        else:
            sql += f" ON CONFLICT({pk_list}) DO NOTHING"
        self.conn.execute(sql, [row[c] for c in cols])

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, tuple(params))

    def commit(self) -> None:
        self.conn.commit()

    def query_df(self, sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.conn, params=tuple(params))

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        cur = self.conn.execute(sql, tuple(params))
        row = cur.fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # meta
    # ------------------------------------------------------------------
    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.scalar("SELECT value FROM meta WHERE key = ?", (key,))
        return val if val is not None else default

    # ------------------------------------------------------------------
    # consultas de coleta incremental
    # ------------------------------------------------------------------
    def known_match_ids(self) -> set[int]:
        return {r[0] for r in self.conn.execute("SELECT id FROM matches")}

    def match_needs_details(self, match_id: int) -> bool:
        """True se a partida não existe, ou existe mas ainda sem escalação
        estando já finalizada (ou seja, vale a pena baixar detalhes)."""
        row = self.conn.execute(
            "SELECT status_type, has_lineups FROM matches WHERE id = ?", (match_id,)
        ).fetchone()
        if row is None:
            return True
        status_type, has_lineups = row
        if status_type in ("canceled", "postponed", "walkover", "abandoned", "interrupted"):
            return False  # status final, não vai virar "finished" nem ganhar escalação
        if status_type != "finished":
            return True  # ainda pode mudar (agendado ou em andamento)
        return not bool(has_lineups)

    def competition_id_for(
        self, unique_tournament_id: int, season_id: Optional[int], name: str, season_year: Optional[str]
    ) -> int:
        cur = self.conn.execute(
            "SELECT id FROM competitions WHERE unique_tournament_id = ? AND season_id IS ?",
            (unique_tournament_id, season_id),
        )
        row = cur.fetchone()
        if row:
            return row[0]
        cur = self.conn.execute(
            "INSERT INTO competitions(unique_tournament_id, season_id, name, season_year) "
            "VALUES (?, ?, ?, ?)",
            (unique_tournament_id, season_id, name, season_year),
        )
        self.conn.commit()
        return int(cur.lastrowid)


_singleton: Optional[Database] = None


def get_db(path: str | Path | None = None) -> Database:
    """Instância única para o processo (usada pelo dashboard)."""
    global _singleton
    if path is not None:
        return Database(path)
    if _singleton is None:
        _singleton = Database()
    return _singleton
