"""Mapa de Calor — coordenadas reais do Sofascore, por partida ou agregadas."""
from __future__ import annotations

import streamlit as st

from src.analytics import loaders
from src.dashboard import components as C
from src.dashboard import state, theme
from src.dashboard.pitch import heatmap_figure

theme.inject()
theme.brand_header()
C.section("🔥 Mapa de Calor", "Posicionamento em campo — dados reais do Sofascore, quando existem.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)

hm_players = db.query_df(
    """
    SELECT DISTINCT p.id, p.name
    FROM player_heatmap h JOIN players p ON p.id = h.player_id
    JOIN matches m ON m.id = h.match_id
    JOIN player_match_stats s ON s.match_id=h.match_id AND s.player_id=h.player_id
    WHERE s.is_santacruz = 1
    ORDER BY p.name
    """
)
if hm_players.empty:
    C.empty_state(
        "Dados de localização de eventos não disponíveis nesta fonte para o recorte atual. "
        "O Sofascore só fornece coordenadas de posicionamento para jogadores que atuaram na partida."
    )
    st.stop()

cA, cB = st.columns([1, 1])
pname = cA.selectbox("Jogador", hm_players["name"].tolist())
pid = int(hm_players[hm_players["name"] == pname]["id"].iloc[0])

pm = db.query_df(
    """
    SELECT h.match_id, m.date, m.opponent_name, m.competition_id, c.name AS competition,
           m.start_timestamp
    FROM player_heatmap h JOIN matches m ON m.id=h.match_id
    LEFT JOIN competitions c ON c.id=m.competition_id
    WHERE h.player_id = ? ORDER BY m.start_timestamp DESC
    """,
    (pid,),
)
modo = cB.radio("Modo", ["Uma partida", "Últimos 5 jogos (agregado)"], horizontal=True)
if modo == "Uma partida":
    pm["rot"] = pm["date"].astype(str) + " · " + pm["opponent_name"].fillna("?") + " · " + pm["competition"].fillna("")
    sel = st.selectbox("Partida", pm["rot"].tolist())
    match_id = int(pm[pm["rot"] == sel]["match_id"].iloc[0])
    pts = loaders.heatmap_points(db, match_id, pid)
    st.plotly_chart(heatmap_figure(pts, f"{pname} — {sel}"), use_container_width=True)
    st.caption(f"{len(pts)} pontos de posição registrados pela fonte nesta partida.")
else:
    ids = pm["match_id"].head(5).tolist()
    pts = loaders.heatmap_points_multi(db, pid, ids)
    st.plotly_chart(heatmap_figure(pts, f"{pname} — últimos {len(ids)} jogos com dados"),
                    use_container_width=True)
    st.caption(f"Agregado de {len(ids)} partidas com dado disponível · {len(pts)} pontos.")

C.empty_state(
    "Zonas de atuação detalhadas por tipo de ação (finalização, passe, recuperação) exigiriam "
    "eventos posicionados individualmente — **FONTE NECESSÁRIA**: o Sofascore não disponibiliza "
    "esse nível de detalhe publicamente."
)

h = loaders.data_health(db)
C.source_footer(atualizado=h["last_collection"] or "—")
