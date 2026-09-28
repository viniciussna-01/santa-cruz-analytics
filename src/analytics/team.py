"""Análise de desempenho do time (Santa Cruz)."""
from __future__ import annotations

from typing import Optional

import pandas as pd

from src.analytics import loaders
from src.database import Database
from src.utils.helpers import pct


def _slice(df: pd.DataFrame, last_n: Optional[int], venue: Optional[str]) -> pd.DataFrame:
    if venue == "home":
        df = df[df["is_santacruz_home"] == 1]
    elif venue == "away":
        df = df[df["is_santacruz_home"] == 0]
    if last_n:
        df = df.head(last_n)  # df já vem ordenado desc
    return df


def summary(
    db: Database,
    last_n: Optional[int] = None,
    venue: Optional[str] = None,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
) -> dict:
    """Resumo de resultados/gols. `venue` in {None,'home','away'}.

    Se não houver jogos no recorte, devolve dict com zeros e `jogos=0`
    (não inventa médias)."""
    matches = loaders.santacruz_matches(
        db, season_year=season_year, competition_id=competition_id
    )
    df = _slice(matches, last_n, venue)
    n = len(df)
    if n == 0:
        return {
            "jogos": 0, "vitorias": 0, "empates": 0, "derrotas": 0,
            "aproveitamento": None, "gols_marcados": 0, "gols_sofridos": 0,
            "saldo": 0, "media_gols": None, "media_gols_sofridos": None,
            "forma": [], "clean_sheets": 0,
        }
    v = int((df["santacruz_result"] == "V").sum())
    e = int((df["santacruz_result"] == "E").sum())
    d = int((df["santacruz_result"] == "D").sum())
    gf = int(df["santacruz_gf"].fillna(0).sum())
    ga = int(df["santacruz_ga"].fillna(0).sum())
    pts = v * 3 + e
    return {
        "jogos": n,
        "vitorias": v,
        "empates": e,
        "derrotas": d,
        "pontos": pts,
        "aproveitamento": pct(pts, n * 3),
        "gols_marcados": gf,
        "gols_sofridos": ga,
        "saldo": gf - ga,
        "media_gols": round(gf / n, 2),
        "media_gols_sofridos": round(ga / n, 2),
        "clean_sheets": int((df["santacruz_ga"].fillna(-1) == 0).sum()),
        # forma em ordem cronológica (antigo -> recente), como "V E V D V"
        "forma": list(df["santacruz_result"].dropna()[::-1]),
    }


def form_string(db: Database, n: int = 5, **kw) -> str:
    return " ".join(summary(db, last_n=n, **kw)["forma"])


def home_away_split(db: Database, **kw) -> dict:
    return {
        "mandante": summary(db, venue="home", **kw),
        "visitante": summary(db, venue="away", **kw),
    }


def evolution(db: Database, windows=(5, 10, 15), **kw) -> pd.DataFrame:
    """Compara últimos 5 / 10 / 15 jogos lado a lado."""
    rows = []
    for w in windows:
        s = summary(db, last_n=w, **kw)
        rows.append(
            {
                "janela": f"Últimos {w}",
                "jogos": s["jogos"],
                "V": s["vitorias"],
                "E": s["empates"],
                "D": s["derrotas"],
                "gols_pró": s["gols_marcados"],
                "gols_contra": s["gols_sofridos"],
                "saldo": s["saldo"],
                "média_gols": s["media_gols"],
                "média_sofridos": s["media_gols_sofridos"],
                "aproveitamento": s["aproveitamento"],
            }
        )
    return pd.DataFrame(rows)


def match_by_match(db: Database, last_n: Optional[int] = None, **kw) -> pd.DataFrame:
    """Série jogo a jogo (para gráficos de evolução)."""
    df = loaders.santacruz_matches(db, **kw)
    if last_n:
        df = df.head(last_n)
    df = df.sort_values("start_timestamp")
    out = df[
        [
            "id", "date", "competition", "opponent_name", "is_santacruz_home",
            "santacruz_gf", "santacruz_ga", "santacruz_result",
        ]
    ].copy()
    out["pontos"] = out["santacruz_result"].map({"V": 3, "E": 1, "D": 0})
    out["pontos_acum"] = out["pontos"].cumsum()
    out["saldo_acum"] = (out["santacruz_gf"].fillna(0) - out["santacruz_ga"].fillna(0)).cumsum()
    out["mandante"] = out["is_santacruz_home"].map({1: "Casa", 0: "Fora"})
    return out


def by_competition(db: Database, season_year: Optional[str | int] = None) -> pd.DataFrame:
    """Aproveitamento/gols agrupados por competição — 'desempenho por competição'."""
    df = loaders.santacruz_matches(db, season_year=season_year)
    if df.empty:
        return pd.DataFrame(columns=[
            "competicao", "jogos", "vitorias", "empates", "derrotas",
            "gols_marcados", "gols_sofridos", "aproveitamento",
        ])
    rows = []
    for comp, grp in df.groupby("competition", dropna=False):
        n = len(grp)
        v = int((grp["santacruz_result"] == "V").sum())
        e = int((grp["santacruz_result"] == "E").sum())
        d = int((grp["santacruz_result"] == "D").sum())
        gf = int(grp["santacruz_gf"].fillna(0).sum())
        ga = int(grp["santacruz_ga"].fillna(0).sum())
        rows.append({
            "competicao": comp or "Desconhecida", "jogos": n, "vitorias": v, "empates": e,
            "derrotas": d, "gols_marcados": gf, "gols_sofridos": ga,
            "aproveitamento": pct(v * 3 + e, n * 3),
        })
    out = pd.DataFrame(rows).sort_values("jogos", ascending=False).reset_index(drop=True)
    return out


def by_month(db: Database, season_year: Optional[str | int] = None) -> pd.DataFrame:
    """Aproveitamento por mês — 'desempenho por período'."""
    df = loaders.santacruz_matches(db, season_year=season_year)
    if df.empty:
        return pd.DataFrame(columns=["mes", "jogos", "aproveitamento", "gols_marcados", "gols_sofridos"])
    df = df.copy()
    df["mes"] = df["date"].astype(str).str.slice(0, 7)
    rows = []
    for mes, grp in df.groupby("mes"):
        n = len(grp)
        v = int((grp["santacruz_result"] == "V").sum())
        e = int((grp["santacruz_result"] == "E").sum())
        rows.append({
            "mes": mes, "jogos": n, "aproveitamento": pct(v * 3 + e, n * 3),
            "gols_marcados": int(grp["santacruz_gf"].fillna(0).sum()),
            "gols_sofridos": int(grp["santacruz_ga"].fillna(0).sum()),
        })
    return pd.DataFrame(rows).sort_values("mes").reset_index(drop=True)


def last_and_next(db: Database) -> dict:
    finished = loaders.santacruz_matches(db)
    last = None if finished.empty else finished.iloc[0].to_dict()
    nxt = loaders.next_match(db)
    return {"ultimo": last, "proximo": None if nxt is None else nxt.to_dict()}
