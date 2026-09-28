"""Desempenho — resultados, evolução, mando de campo, competição e período."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analytics import loaders, team
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("📈 Desempenho", "Resultados, evolução e padrões de mando de campo.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}
last_n = filt["last_n"]

s = team.summary(db, last_n=last_n, **FILT)
C.kpi_row([
    {"label": "Jogos", "value": s["jogos"]},
    {"label": "Vitórias", "value": s["vitorias"]},
    {"label": "Empates", "value": s["empates"]},
    {"label": "Derrotas", "value": s["derrotas"]},
    {"label": "Gols", "value": s["gols_marcados"]},
    {"label": "Saldo", "value": s["saldo"], "accent": s["saldo"] > 0 if s["saldo"] else False},
    {"label": "Aproveitamento", "value": f"{s['aproveitamento']:.0f}%" if s["aproveitamento"] is not None else "—"},
])

st.write("")
tab_res, tab_mando, tab_comp, tab_periodo, tab_class = st.tabs(
    ["Resultado por partida", "Mandante x Visitante", "Por competição", "Por período", "Classificação"]
)

with tab_res:
    mbm = team.match_by_match(db, last_n=last_n, **FILT)
    if mbm.empty:
        C.empty_state("Sem partidas no recorte selecionado.")
    else:
        mbm["rótulo"] = mbm["date"].astype(str) + " · " + mbm["opponent_name"].fillna("?")
        f1 = px.bar(mbm, x="rótulo", y="pontos", color="santacruz_result",
                   color_discrete_map=theme.RESULT_COLORS, title="Pontos conquistados por partida",
                   hover_data=["competition", "santacruz_gf", "santacruz_ga", "mandante"])
        f1.update_layout(xaxis_title="", yaxis_title="pontos", legend_title="Resultado",
                         xaxis={"categoryorder": "array", "categoryarray": list(mbm["rótulo"])})
        st.plotly_chart(C.style_fig(f1), use_container_width=True)

        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=mbm["rótulo"], y=mbm["santacruz_gf"], name="Gols marcados",
                                mode="lines+markers", line=dict(color=theme.GREEN)))
        f2.add_trace(go.Scatter(x=mbm["rótulo"], y=mbm["santacruz_ga"], name="Gols sofridos",
                                mode="lines+markers", line=dict(color=theme.RED)))
        f2.update_layout(title="Gols marcados x sofridos (jogo a jogo)", yaxis_title="gols")
        st.plotly_chart(C.style_fig(f2), use_container_width=True)

        f3 = px.line(mbm, x="rótulo", y="pontos_acum", markers=True, title="Pontos acumulados",
                     color_discrete_sequence=[theme.RED])
        f3.update_layout(yaxis_title="pontos")
        st.plotly_chart(C.style_fig(f3), use_container_width=True)

with tab_mando:
    ha = team.home_away_split(db, last_n=last_n, **FILT)
    hm, aw = ha["mandante"], ha["visitante"]
    c1, c2 = st.columns(2)
    with c1:
        C.section("Como mandante")
        C.kpi_row([
            {"label": "Jogos", "value": hm["jogos"]},
            {"label": "V-E-D", "value": f"{hm['vitorias']}-{hm['empates']}-{hm['derrotas']}"},
            {"label": "Aproveit.", "value": f"{hm['aproveitamento']:.0f}%" if hm["aproveitamento"] is not None else "—"},
        ])
        C.progress_bar(hm["aproveitamento"], "Aproveitamento em casa")
    with c2:
        C.section("Como visitante")
        C.kpi_row([
            {"label": "Jogos", "value": aw["jogos"]},
            {"label": "V-E-D", "value": f"{aw['vitorias']}-{aw['empates']}-{aw['derrotas']}"},
            {"label": "Aproveit.", "value": f"{aw['aproveitamento']:.0f}%" if aw["aproveitamento"] is not None else "—"},
        ])
        C.progress_bar(aw["aproveitamento"], "Aproveitamento fora")
    if hm["jogos"] or aw["jogos"]:
        cmp = px.bar(
            x=["Casa", "Fora"], y=[hm["gols_marcados"], aw["gols_marcados"]],
            title="Gols marcados: casa x fora", color_discrete_sequence=[theme.RED],
        )
        cmp.update_layout(yaxis_title="gols", xaxis_title="")
        st.plotly_chart(C.style_fig(cmp), use_container_width=True)

with tab_comp:
    bc = team.by_competition(db, season_year=filt["season_year"])
    if bc.empty:
        C.empty_state("Sem partidas no recorte selecionado.")
    else:
        st.dataframe(
            bc.rename(columns={"competicao": "Competição", "jogos": "J", "vitorias": "V",
                               "empates": "E", "derrotas": "D", "gols_marcados": "GM",
                               "gols_sofridos": "GS", "aproveitamento": "Aprov. %"}),
            hide_index=True, use_container_width=True,
        )
        fig = px.bar(bc, x="competicao", y="aproveitamento", title="Aproveitamento por competição",
                    color_discrete_sequence=[theme.RED])
        fig.update_layout(xaxis_title="", yaxis_title="aproveitamento %")
        st.plotly_chart(C.style_fig(fig), use_container_width=True)

with tab_periodo:
    bm = team.by_month(db, season_year=filt["season_year"])
    if bm.empty:
        C.empty_state("Sem partidas no recorte selecionado.")
    else:
        fig = px.line(bm, x="mes", y="aproveitamento", markers=True, title="Aproveitamento por mês",
                     color_discrete_sequence=[theme.RED])
        fig.update_layout(xaxis_title="", yaxis_title="aproveitamento %")
        st.plotly_chart(C.style_fig(fig), use_container_width=True)

        ev = team.evolution(db, **FILT)
        st.markdown("**Comparativo — últimos 5 / 10 / 15 jogos**")
        st.dataframe(ev, hide_index=True, use_container_width=True)

with tab_class:
    std = loaders.standings(db)
    if std.empty:
        C.empty_state("Classificação ainda não coletada para esta competição.")
    else:
        st.dataframe(
            std[["position", "team_name", "points", "played", "wins", "draws", "losses",
                 "goals_for", "goals_against"]].rename(columns={
                "position": "Pos", "team_name": "Time", "points": "Pts", "played": "J",
                "wins": "V", "draws": "E", "losses": "D", "goals_for": "GM", "goals_against": "GS",
            }),
            hide_index=True, use_container_width=True, height=520,
        )

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
