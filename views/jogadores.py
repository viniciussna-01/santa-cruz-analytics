"""Jogadores — ranking completo com filtros."""
from __future__ import annotations

import streamlit as st

from src.analytics import loaders, players
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("👥 Jogadores", "Estatísticas por jogador — só o que existe na fonte entra na tabela.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}

cc = st.columns(3)
poss = players.positions_available(db, **FILT)
pos_sel = cc[0].selectbox("Posição", ["Todas"] + poss)
min_j = cc[1].number_input("Mínimo de jogos", 0, 40, 1)
janela_j = cc[2].selectbox("Período", ["Temporada/recorte", "Últimos 5 jogos", "Últimos 10 jogos"])
ln_map = {"Temporada/recorte": None, "Últimos 5 jogos": 5, "Últimos 10 jogos": 10}

pt = players.player_table(
    db, last_n_matches=ln_map[janela_j], position=None if pos_sel == "Todas" else pos_sel,
    min_matches=int(min_j), **FILT,
)
if pt.empty:
    C.empty_state("Sem estatísticas individuais no recorte selecionado.")
else:
    C.kpi_row([
        {"label": "Jogadores no recorte", "value": len(pt)},
        {"label": "Gols da equipe (soma)", "value": int(pt["gols"].sum())},
        {"label": "Assistências (soma)", "value": int(pt["assistencias"].sum())},
        {"label": "Nota média geral", "value": round(pt["nota_media"].mean(), 2) if pt["nota_media"].notna().any() else "—"},
    ])
    st.write("")
    st.dataframe(
        pt.drop(columns=["player_id"]).rename(columns={
            "jogador": "Jogador", "posicao": "Pos", "jogos": "J", "titularidades": "Tit",
            "minutos": "Min", "gols": "G", "assistencias": "A", "participacao_gols": "G+A",
            "nota_media": "Nota", "finalizacoes": "Fin", "finalizacoes_alvo": "Fin.Alvo",
            "passes": "Passes", "passes_chave": "P.Chave", "desarmes": "Desarm",
            "interceptacoes": "Interc", "cartoes_amarelos": "🟨", "cartoes_vermelhos": "🟥",
            "gols_por_90": "G/90", "part_gols_por_90": "G+A/90",
        }),
        hide_index=True, use_container_width=True, height=560,
    )
    st.caption("Clique no cabeçalho de uma coluna para ordenar.")

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
