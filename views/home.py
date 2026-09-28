"""Home — Santa Cruz Data Analytics."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.analytics import insights, loaders, team
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}
last_n = filt["last_n"]

ln = team.last_and_next(db)
s = team.summary(db, last_n=last_n, **FILT)


def fmt_match(m) -> str:
    if m is None:
        return "—"
    m = dict(m)
    placar = f"{m.get('home_score')}–{m.get('away_score')}" if m.get("home_score") is not None else "x"
    return f"{m.get('home_team_name')} {placar} {m.get('away_team_name')}"


c1, c2 = st.columns(2)
with c1:
    C.section("Último jogo")
    if ln["ultimo"]:
        u = ln["ultimo"]
        st.markdown(f"**{fmt_match(u)}**")
        st.caption(f"{u.get('date')} · {u.get('competition')} · "
                  f"{'Casa' if u.get('is_santacruz_home') else 'Fora'} · resultado: {u.get('santacruz_result')}")
    else:
        C.empty_state("Nenhuma partida finalizada encontrada.")
with c2:
    C.section("Próximo jogo")
    if ln["proximo"]:
        p = ln["proximo"]
        st.markdown(f"**{p.get('home_team_name')} x {p.get('away_team_name')}**")
        st.caption(f"{p.get('date')} · {p.get('competition')}")
    else:
        C.empty_state("Sem próximo jogo agendado na fonte.")

st.markdown(
    f"<div style='margin:.9rem 0 .3rem;color:{theme.TEXT_MUTED};font-size:.85rem'>"
    f"Forma — últimos {last_n or 'todos'} jogos</div>", unsafe_allow_html=True,
)
C.result_badges(s["forma"])

st.write("")
C.kpi_row([
    {"label": "Jogos", "value": s["jogos"]},
    {"label": "Vitórias", "value": s["vitorias"], "accent": True},
    {"label": "Empates", "value": s["empates"]},
    {"label": "Derrotas", "value": s["derrotas"]},
    {"label": "Gols marcados", "value": s["gols_marcados"]},
    {"label": "Gols sofridos", "value": s["gols_sofridos"]},
    {"label": "Aproveitamento", "value": f"{s['aproveitamento']:.0f}%" if s["aproveitamento"] is not None else "—"},
])
st.write("")
C.kpi_row([
    {"label": "Saldo de gols", "value": s["saldo"]},
    {"label": "Média de gols/jogo", "value": s["media_gols"] if s["media_gols"] is not None else "—"},
    {"label": "Média sofrida/jogo", "value": s["media_gols_sofridos"] if s["media_gols_sofridos"] is not None else "—"},
    {"label": "Jogos sem sofrer gol", "value": s["clean_sheets"]},
])

st.divider()
C.section("🔎 Análise do momento", "Frases geradas por regras estatísticas a partir dos dados coletados.")
for frase in insights.momentum(db, window=(last_n or 5), season_year=filt["season_year"]):
    st.markdown(f"- {frase}")
st.caption("Ver mais em **Insights** →")

mbm = team.match_by_match(db, last_n=last_n, **FILT)
if not mbm.empty:
    st.write("")
    mbm2 = mbm.copy()
    mbm2["rótulo"] = mbm2["date"].astype(str) + " · " + mbm2["opponent_name"].fillna("?")
    fig = px.bar(mbm2, x="rótulo", y="pontos", color="santacruz_result",
                color_discrete_map=theme.RESULT_COLORS, title="Pontos por partida")
    fig.update_layout(xaxis_title="", yaxis_title="pontos", showlegend=False,
                      xaxis={"categoryorder": "array", "categoryarray": list(mbm2["rótulo"])})
    st.plotly_chart(C.style_fig(fig, height=280), use_container_width=True)

h = loaders.data_health(db)
C.source_footer(
    periodo=f"{filt['season_label']} · {filt['competition_label']}",
    atualizado=h["last_collection"] or "—",
)
