"""Comparação lado a lado entre dois jogadores do Santa Cruz.

Mostra os números; não elege "o melhor". Cabe a quem olha interpretar —
por isso as funções aqui nunca retornam um rótulo de vencedor.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from src.analytics import players as players_mod
from src.analytics import ratings as ratings_mod
from src.database import Database

# Agrupadas por escala — comparar "minutos" (centenas) com "gols" (unidades)
# no mesmo eixo tornaria as barras pequenas ilegíveis, então cada grupo vira
# um gráfico próprio no dashboard.
_METRIC_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Volume de jogo", [
        ("jogos", "Jogos"), ("minutos", "Minutos"), ("passes", "Passes"),
    ]),
    ("Produção ofensiva", [
        ("gols", "Gols"), ("assistencias", "Assistências"),
        ("participacao_gols", "Participação em gols"),
        ("finalizacoes", "Finalizações"), ("finalizacoes_alvo", "Finalizações no alvo"),
        ("passes_chave", "Passes-chave"),
    ]),
    ("Defesa e disciplina", [
        ("desarmes", "Desarmes"), ("interceptacoes", "Interceptações"),
        ("cartoes_amarelos", "Cartões amarelos"), ("cartoes_vermelhos", "Cartões vermelhos"),
    ]),
    ("Por 90 minutos", [
        ("gols_por_90", "Gols / 90min"), ("part_gols_por_90", "Participação em gols / 90min"),
    ]),
]
_METRICS = [m for _, group in _METRIC_GROUPS for m in group]


def available_players(db: Database, **filters) -> pd.DataFrame:
    """Lista jogador_id/nome elegíveis para comparação no recorte atual."""
    pt = players_mod.player_table(db, min_matches=1, **filters)
    return pt[["player_id", "jogador", "posicao", "jogos"]] if not pt.empty else pt


def compare(db: Database, player_a_id: int, player_b_id: int, **filters) -> dict:
    pt = players_mod.player_table(db, min_matches=0, **filters)
    ri = ratings_mod.rating_and_index(db, min_matches=1, **filters)

    def row_of(pid: int, table: pd.DataFrame) -> Optional[pd.Series]:
        if table.empty:
            return None
        m = table[table["player_id"] == pid]
        return None if m.empty else m.iloc[0]

    a, b = row_of(player_a_id, pt), row_of(player_b_id, pt)
    ra, rb = row_of(player_a_id, ri), row_of(player_b_id, ri)

    if a is None or b is None:
        return {"ok": False, "reason": "Um dos jogadores não tem estatísticas no recorte selecionado."}

    rows = []
    for grupo, metrics in _METRIC_GROUPS:
        for col, label in metrics:
            rows.append({"grupo": grupo, "metrica": label, "jogador_a": a.get(col), "jogador_b": b.get(col)})

    notas = {
        "nota_media": "Nota média Sofascore",
        "ips": "Índice de Performance Santa Cruz",
    }
    for key, label in notas.items():
        rows.append({
            "grupo": "Notas",
            "metrica": label,
            "jogador_a": None if ra is None else ra.get(key),
            "jogador_b": None if rb is None else rb.get(key),
        })

    return {
        "ok": True,
        "jogador_a": {"nome": a["jogador"], "posicao": a["posicao"]},
        "jogador_b": {"nome": b["jogador"], "posicao": b["posicao"]},
        "tabela": pd.DataFrame(rows),
        "sub_indices_a": None if ra is None else ra[["sub_ofensivo", "sub_criacao", "sub_passe",
                                                       "sub_defesa", "sub_disciplina"]].to_dict(),
        "sub_indices_b": None if rb is None else rb[["sub_ofensivo", "sub_criacao", "sub_passe",
                                                       "sub_defesa", "sub_disciplina"]].to_dict(),
    }
