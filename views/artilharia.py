"""Central de Artilharia — gols, assistências e participação."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.analytics import loaders, scorers
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("🎯 Central de Artilharia", "Gols, assistências e participação — Santa Cruz.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}

jc = st.radio("Recorte", ["Temporada/recorte", "Últimos 5 jogos", "Últimos 10 jogos"], horizontal=True)
lnm = {"Temporada/recorte": None, "Últimos 5 jogos": 5, "Últimos 10 jogos": 10}[jc]
sc = scorers.scorers_table(db, last_n_matches=lnm, **FILT)
gi = scorers.goal_involvement_summary(db, last_n_matches=lnm, **FILT)

if sc.empty:
    C.empty_state("Sem gols/assistências registrados no recorte selecionado.")
    st.stop()

C.kpi_row([
    {"label": "Artilheiro", "value": gi["artilheiro"]["jogador"] if gi["artilheiro"] else "—",
     "delta": f"{gi['artilheiro']['gols']} gols" if gi["artilheiro"] else None, "accent": True},
    {"label": "Garçom", "value": gi["garcom"]["jogador"] if gi["garcom"] else "—",
     "delta": f"{gi['garcom']['assistencias']} assist." if gi["garcom"] else None},
    {"label": "Gols da equipe", "value": gi["total_gols"]},
    {"label": "Assistências da equipe", "value": gi["total_assist"]},
])

st.write("")
st.dataframe(
    sc.rename(columns={"jogador": "Jogador", "gols": "Gols", "assistencias": "Assistências",
                       "jogos": "Jogos", "minutos": "Minutos", "participacoes": "G+A",
                       "part_por_90": "G+A/90min"}),
    hide_index=True, use_container_width=True,
)

cc = st.columns(2)
top = sc.head(12)
f1 = px.bar(top, x="gols", y="jogador", orientation="h", title="Artilheiros",
           color_discrete_sequence=[theme.RED])
f1.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="gols", yaxis_title="")
cc[0].plotly_chart(C.style_fig(f1), use_container_width=True)

topa = sc.sort_values("assistencias", ascending=False).head(12)
f2 = px.bar(topa, x="assistencias", y="jogador", orientation="h", title="Assistências",
           color_discrete_sequence=[theme.GRAY])
f2.update_layout(yaxis={"categoryorder": "total ascending"}, xaxis_title="assistências", yaxis_title="")
cc[1].plotly_chart(C.style_fig(f2), use_container_width=True)

f3 = px.scatter(sc, x="minutos", y="participacoes", size="participacoes", color="gols",
                hover_name="jogador", title="Participação em gols x minutos em campo",
                color_continuous_scale=["#3a3d44", theme.RED])
st.plotly_chart(C.style_fig(f3), use_container_width=True)

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
