"""Análise Tática — médias de equipe por partida (Santa Cruz x Adversário)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.analytics import loaders, tactical
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("🧭 Análise Tática", "Médias por partida das estatísticas de equipe — dado disponível na fonte.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)

rep = tactical.team_stats_summary(
    db, season_year=filt["season_year"], competition_id=filt["competition_id"], last_n=filt["last_n"]
)

st.markdown(
    "<span class='scda-pill'>✅ Dado disponível — média direta das estatísticas oficiais do Sofascore por partida</span>",
    unsafe_allow_html=True,
)
st.write("")

if not rep["groups"]:
    C.empty_state("Sem estatísticas de equipe coletadas para o recorte selecionado.")
else:
    tabs = st.tabs([g["grupo"] for g in rep["groups"]])
    for tab, g in zip(tabs, rep["groups"]):
        with tab:
            lin = g["linhas"]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=lin["label"], x=lin["santacruz"], name="Santa Cruz",
                                 orientation="h", marker_color=theme.RED))
            fig.add_trace(go.Bar(y=lin["label"], x=lin["adversario"], name="Adversários",
                                 orientation="h", marker_color=theme.GRAY))
            fig.update_layout(barmode="group", height=110 + 65 * len(lin),
                              yaxis=dict(autorange="reversed"),
                              xaxis_title=f"média por partida ({g['grupo']})")
            st.plotly_chart(C.style_fig(fig), use_container_width=True)
            st.caption(f"Baseado em {int(lin['n'].max())} partida(s) com estatística disponível na fonte.")

st.divider()
C.section("Zonas de atuação por tipo de ação", "Ex.: finalizações no último terço, passes por corredor.")
C.empty_state(
    "**FONTE NECESSÁRIA** — o Sofascore não disponibiliza publicamente eventos posicionados "
    "individualmente (só o mapa de calor agregado, na página **Mapa de calor**). Para esse nível "
    "de detalhe seria preciso uma fonte adicional (ex.: dados de eventos com coordenadas, hoje "
    "restritos a provedores pagos)."
)

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
