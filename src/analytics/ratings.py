"""Notas dos jogadores + Índice de Performance Santa Cruz (IPS).

O IPS é COMPLEMENTAR à nota do Sofascore, nunca substituto.
Metodologia completa e fórmula em docs/METODOLOGIA.md. Resumo:

    IPS = 0.5 * nota_media_sofascore  +  0.5 * IPS_bruto            (0-10)

onde IPS_bruto é a média ponderada (pesos por posição) de 6 sub-índices
0-10 calculados a partir de estatísticas por 90 minutos, comparadas a
"benchmarks" fixos e transparentes.

Se não houver nota Sofascore, IPS = IPS_bruto e marcamos `confianca` baixa.
Se não houver NENHUMA estatística (sem minutos e sem nota), IPS = None e o
campo `limitacao` explica o motivo — não inventamos número.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from src.analytics import loaders
from src.database import Database

# ---------------------------------------------------------------------------
# Pesos por posição (somam 1). Ordem: off, cria, passe, defesa, disciplina, gk
# ---------------------------------------------------------------------------
_POS_WEIGHTS = {
    "G": dict(off=0.00, cria=0.05, passe=0.20, defesa=0.15, disc=0.15, gk=0.45),
    "D": dict(off=0.08, cria=0.10, passe=0.22, defesa=0.45, disc=0.15, gk=0.00),
    "M": dict(off=0.18, cria=0.30, passe=0.25, defesa=0.20, disc=0.07, gk=0.00),
    "F": dict(off=0.45, cria=0.22, passe=0.10, defesa=0.10, disc=0.13, gk=0.00),
}
_DEFAULT_POS = "M"

# Benchmarks por 90 min: valor que corresponde a "nota 10" no sub-índice.
_BENCH = dict(
    off=4.0,     # 3*gols + 1*chutes_no_alvo + 2*xG
    cria=4.0,    # 3*assist + 1*passes_chave + 2*grandes_chances_criadas + 2*xA
    passe_vol=55.0,     # passes certos / 90
    passe_acc=0.86,     # % de acerto de passe
    defesa=9.0,  # 1.2*desarmes_ganhos + 1.2*intercept. + 0.6*cortes + 1.0*bloqueios + 0.4*recuperações + 0.5*duelos_ganhos
    gk_saves=3.5,       # defesas / 90
)


def _num(value) -> float:
    """None / NaN / '' -> 0.0 (para somatórios de sub-índice)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if f != f else f  # NaN check


def _p90(series_sum: float, minutes: float) -> float:
    minutes = _num(minutes)
    if minutes <= 0:
        return 0.0
    return _num(series_sum) / minutes * 90.0


def _scale(value: float, bench: float, cap: float = 12.0) -> float:
    if bench <= 0:
        return 0.0
    return float(min(cap, max(0.0, value / bench * 10.0)))


def _subindices(row: pd.Series) -> dict:
    m = _num(row.get("minutos"))
    g = lambda k: _num(row.get(k))  # noqa: E731

    off_raw = _p90(3 * g("gols") + 1 * g("finalizacoes_alvo") + 2 * g("xg"), m)
    cria_raw = _p90(
        3 * g("assistencias") + 1 * g("passes_chave") + 2 * g("grandes_chances") + 2 * g("xa"), m
    )
    defesa_raw = _p90(
        1.2 * g("desarmes") + 1.2 * g("interceptacoes") + 0.6 * g("cortes")
        + 1.0 * g("bloqueios") + 0.4 * g("recuperacoes") + 0.5 * g("duelos_ganhos"),
        m,
    )
    passe_vol = _p90(g("passes_certos"), m)
    passe_acc = (g("passes_certos") / g("passes")) if g("passes") else 0.0
    passe_sub = 10.0 * (
        0.6 * min(passe_vol / _BENCH["passe_vol"], 1.0)
        + 0.4 * min(passe_acc / _BENCH["passe_acc"], 1.0)
    )

    # disciplina/posse: começa em 8, penaliza perdas e faltas/cartões
    disc = 8.0
    disc -= min(4.0, _p90(g("posse_perdida"), m) / 6.0)
    disc -= min(3.0, _p90(g("faltas"), m))
    disc -= _p90(g("amarelos"), m) * 2.0
    disc -= _p90(g("vermelhos"), m) * 5.0
    disc = float(min(10.0, max(0.0, disc)))

    gk_sub = _scale(_p90(g("defesas"), m), _BENCH["gk_saves"])

    return {
        "off": _scale(off_raw, _BENCH["off"]),
        "cria": _scale(cria_raw, _BENCH["cria"]),
        "passe": float(min(10.0, max(0.0, passe_sub))),
        "defesa": _scale(defesa_raw, _BENCH["defesa"]),
        "disc": disc,
        "gk": gk_sub,
    }


def _ips_bruto(sub: dict, position: Optional[str]) -> float:
    pos = (position or _DEFAULT_POS)[:1].upper()
    w = _POS_WEIGHTS.get(pos, _POS_WEIGHTS[_DEFAULT_POS])
    return float(sum(w[k] * sub[k] for k in w))


def rating_and_index(
    db: Database,
    season_year: Optional[str | int] = None,
    competition_id: Optional[int] = None,
    min_matches: int = 3,
    w_sofascore: float = 0.5,
) -> pd.DataFrame:
    """Por jogador: nota Sofascore (média/melhor/pior/últimos 5-10) + IPS.

    Colunas: jogador, posicao, jogos, minutos, gols, assistencias,
             nota_media, melhor_nota, pior_nota, nota_ult5, nota_ult10,
             ips, ips_bruto, confianca, limitacao
    """
    pm = loaders.santacruz_player_matches(db, season_year=season_year, competition_id=competition_id)
    cols = [
        "player_id", "jogador", "posicao", "jogos", "minutos", "gols", "assistencias",
        "nota_media", "melhor_nota", "pior_nota", "nota_ult5", "nota_ult10",
        "ips", "ips_bruto", "sub_ofensivo", "sub_criacao", "sub_passe", "sub_defesa",
        "sub_disciplina", "sub_goleiro", "confianca", "limitacao",
    ]
    if pm.empty:
        return pd.DataFrame(columns=cols)

    out = []
    for pid, grp in pm.groupby("player_id"):
        grp = grp.sort_values("start_timestamp", ascending=False)
        jogos = grp["match_id"].nunique()
        if jogos < min_matches:
            continue
        ratings = grp["rating"].dropna()
        minutos = float(grp["minutes"].fillna(0).sum())
        agg = {
            "grandes_chances": grp["big_chances_created"].sum(min_count=1),
            "xg": grp["xg"].sum(min_count=1),
            "xa": grp["xa"].sum(min_count=1),
            "gols": grp["goals"].sum(min_count=1),
            "assistencias": grp["assists"].sum(min_count=1),
            "finalizacoes_alvo": grp["shots_on_target"].sum(min_count=1),
            "passes_chave": grp["key_passes"].sum(min_count=1),
            "passes": grp["passes"].sum(min_count=1),
            "passes_certos": grp["accurate_passes"].sum(min_count=1),
            "desarmes": grp["tackles_won"].sum(min_count=1),
            "interceptacoes": grp["interceptions"].sum(min_count=1),
            "cortes": grp["clearances"].sum(min_count=1),
            "bloqueios": grp["blocks"].sum(min_count=1),
            "recuperacoes": grp["ball_recoveries"].sum(min_count=1),
            "duelos_ganhos": grp["duels_won"].sum(min_count=1),
            "posse_perdida": grp["possession_lost"].sum(min_count=1),
            "faltas": grp["fouls"].sum(min_count=1),
            "amarelos": grp["yellow_cards"].sum(min_count=1),
            "vermelhos": grp["red_cards"].sum(min_count=1),
            "defesas": grp["saves"].sum(min_count=1),
            "minutos": minutos,
        }
        position = grp["position"].dropna().iloc[0] if grp["position"].notna().any() else None

        limitacao = None
        sub = None
        if minutos <= 0 and ratings.empty:
            ips = ips_bruto = None
            confianca = 0.0
            limitacao = "Sem minutos e sem nota nesta competição — IPS não calculado."
        else:
            sub = _subindices(pd.Series(agg))
            ips_bruto = round(_ips_bruto(sub, position), 2)
            if not ratings.empty:
                ips = round(w_sofascore * ratings.mean() + (1 - w_sofascore) * ips_bruto, 2)
            else:
                ips = ips_bruto
                limitacao = "Sem nota Sofascore nesta competição — IPS usa apenas o índice bruto."
            confianca = round(min(1.0, minutos / (90 * 6)), 2)
            if confianca < 0.4 and limitacao is None:
                limitacao = "Amostra pequena (poucos minutos) — interpretar com cautela."

        out.append({
            "player_id": int(pid),
            "jogador": grp["name"].iloc[0],
            "posicao": position,
            "jogos": int(jogos),
            "minutos": int(minutos),
            "gols": int(_num(agg["gols"])),
            "assistencias": int(_num(agg["assistencias"])),
            "nota_media": round(ratings.mean(), 2) if not ratings.empty else None,
            "melhor_nota": round(ratings.max(), 2) if not ratings.empty else None,
            "pior_nota": round(ratings.min(), 2) if not ratings.empty else None,
            "nota_ult5": round(ratings.head(5).mean(), 2) if not ratings.empty else None,
            "nota_ult10": round(ratings.head(10).mean(), 2) if not ratings.empty else None,
            "ips": ips,
            "ips_bruto": ips_bruto,
            "sub_ofensivo": round(sub["off"], 2) if sub else None,
            "sub_criacao": round(sub["cria"], 2) if sub else None,
            "sub_passe": round(sub["passe"], 2) if sub else None,
            "sub_defesa": round(sub["defesa"], 2) if sub else None,
            "sub_disciplina": round(sub["disc"], 2) if sub else None,
            "sub_goleiro": round(sub["gk"], 2) if sub else None,
            "confianca": confianca,
            "limitacao": limitacao,
        })

    df = pd.DataFrame(out, columns=cols)
    if not df.empty:
        df = df.sort_values(["ips", "nota_media"], ascending=False, na_position="last").reset_index(drop=True)
    return df


def rating_timeline(db: Database, player_id: int, **kw) -> pd.DataFrame:
    pm = loaders.santacruz_player_matches(db, **kw)
    grp = pm[pm["player_id"] == player_id].sort_values("start_timestamp")
    return grp[["match_date", "opponent_name", "competition", "minutes", "rating", "goals", "assists"]].copy()
