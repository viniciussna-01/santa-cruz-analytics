"""Comparar Jogadores — lado a lado, sem eleger "o melhor"."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.analytics import compare, loaders
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("⚖️ Comparar Jogadores", "Os números são exibidos lado a lado — a interpretação é sua.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}

avail = compare.available_players(db, **FILT)
if avail.empty or len(avail) < 2:
    C.empty_state("Não há jogadores suficientes com estatística no recorte selecionado.")
    st.stop()

names = avail.sort_values("jogador")["jogador"].tolist()
c1, c2 = st.columns(2)
a_name = c1.selectbox("Jogador A", names, index=0)
b_name = c2.selectbox("Jogador B", names, index=min(1, len(names) - 1))

if a_name == b_name:
    C.empty_state("Escolha dois jogadores diferentes.")
    st.stop()

pid_a = int(avail[avail["jogador"] == a_name]["player_id"].iloc[0])
pid_b = int(avail[avail["jogador"] == b_name]["player_id"].iloc[0])

res = compare.compare(db, pid_a, pid_b, **FILT)
if not res["ok"]:
    C.empty_state(res["reason"])
    st.stop()

c1, c2 = st.columns(2)
c1.markdown(f"#### {a_name} {C.position_badge(res['jogador_a']['posicao'])}", unsafe_allow_html=True)
c2.markdown(f"#### {b_name} {C.position_badge(res['jogador_b']['posicao'])}", unsafe_allow_html=True)

tab = res["tabela"].dropna(how="all", subset=["jogador_a", "jogador_b"])
st.caption(
    "Cada grupo usa sua própria escala — comparar minutos (centenas) com gols (unidades) "
    "no mesmo eixo tornaria as barras pequenas ilegíveis."
)
for grupo, gdf in tab.groupby("grupo", sort=False):
    if gdf.empty:
        continue
    fig = go.Figure()
    fig.add_trace(go.Bar(y=gdf["metrica"], x=gdf["jogador_a"], name=a_name, orientation="h",
                         marker_color=theme.RED))
    fig.add_trace(go.Bar(y=gdf["metrica"], x=gdf["jogador_b"], name=b_name, orientation="h",
                         marker_color=theme.GRAY))
    fig.update_layout(barmode="group", title=grupo, height=120 + 70 * len(gdf),
                      yaxis=dict(autorange="reversed"))
    st.plotly_chart(C.style_fig(fig), use_container_width=True)

sa, sb = res["sub_indices_a"], res["sub_indices_b"]
if sa and sb:
    labels = {"sub_ofensivo": "Ofensivo", "sub_criacao": "Criação", "sub_passe": "Passe",
             "sub_defesa": "Defesa", "sub_disciplina": "Disciplina"}
    cats = list(labels.values())
    va = [sa.get(k) or 0 for k in labels]
    vb = [sb.get(k) or 0 for k in labels]
    radar = go.Figure()
    radar.add_trace(go.Scatterpolar(r=va + [va[0]], theta=cats + [cats[0]], fill="toself",
                                    name=a_name, line_color=theme.RED))
    radar.add_trace(go.Scatterpolar(r=vb + [vb[0]], theta=cats + [cats[0]], fill="toself",
                                    name=b_name, line_color=theme.GRAY))
    radar.update_layout(title="Sub-índices de performance (0–10)",
                        polar=dict(radialaxis=dict(range=[0, 10], gridcolor=theme.BORDER)))
    st.plotly_chart(C.style_fig(radar, height=460), use_container_width=True)
    st.caption("Sub-índices derivados (ver docs/METODOLOGIA.md) — não são notas oficiais do Sofascore.")

st.markdown("**Tabela completa**")
st.dataframe(
    tab.rename(columns={"grupo": "Grupo", "metrica": "Métrica", "jogador_a": a_name, "jogador_b": b_name}),
    hide_index=True, use_container_width=True,
)

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
