"""Cenários — simulação de Monte Carlo dos jogos restantes do Santa Cruz."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.analytics import loaders, scenarios
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("🎲 Cenários", "Simulação de Monte Carlo dos jogos restantes — com base no aproveitamento real da temporada.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)

sim = scenarios.simulate(db, season_year=filt["season_year"] or None, n_sims=10000)

if not sim.get("ok"):
    C.empty_state(sim.get("reason", "Sem dados suficientes para simular."))
    st.stop()

if sim["n_fases_detectadas"] > 1:
    st.markdown(
        f"<span class='scda-pill'>📐 {sim['n_fases_detectadas']} fases detectadas em "
        f"{sim['competicao']} (a rodada reinicia — sinal real de troca de fase)</span> "
        f"<span class='scda-pill'>Simulando a fase {sim['fase_numero']} (atual)</span>",
        unsafe_allow_html=True,
    )

if sim["n_remaining"] == 0:
    C.empty_state(
        f"A fase atual de {sim['competicao']} já não tem jogos agendados coletados — "
        "nada para simular no momento."
    )
else:
    C.kpi_row([
        {"label": "Competição", "value": sim["competicao"]},
        {"label": "Jogos disputados na fase", "value": sim["jogos_disputados_na_fase"]},
        {"label": "Pontos na fase", "value": sim["current_points"], "accent": True},
        {"label": "Jogos restantes", "value": sim["n_remaining"]},
    ])

    tx = sim["taxa_competicao"]
    st.caption(
        f"Taxas usadas no sorteio (aproveitamento do Santa Cruz nesta competição, {tx['jogos']} jogos): "
        f"vitória {tx['vitoria']:.0%} · empate {tx['empate']:.0%} · derrota {tx['derrota']:.0%}."
    )

    summ = scenarios.phase_summary(sim)
    st.write("")
    C.kpi_row([
        {"label": "Pontos finais — média", "value": summ["media"]},
        {"label": "Pior caso (P10)", "value": summ["p10"]},
        {"label": "Mediana (P50)", "value": summ["p50"]},
        {"label": "Melhor caso (P90)", "value": summ["p90"]},
    ])

    fig = go.Figure(go.Histogram(x=sim["final_points_dist"], marker_color=theme.RED, nbinsx=summ["max"] - summ["min"] + 1))
    fig.update_layout(title=f"Distribuição de pontos finais da fase — {sim['n_sims']:,} simulações".replace(",", "."),
                      xaxis_title="pontos ao fim da fase", yaxis_title="nº de simulações")
    st.plotly_chart(C.style_fig(fig), use_container_width=True)

    st.markdown("**Jogos restantes simulados**")
    st.dataframe(
        sim["fixtures"].rename(columns={"date": "Data", "adversario": "Adversário", "mando": "Mando"})
        .drop(columns=["match_id"]),
        hide_index=True, use_container_width=True,
    )

    with st.expander("Jogos já disputados na fase atual"):
        st.dataframe(sim["played_in_phase"].rename(columns={
            "date": "Data", "home_team_name": "Casa", "away_team_name": "Fora", "santacruz_result": "Resultado",
        }), hide_index=True, use_container_width=True)

st.divider()
C.section("Como terminou a fase anterior")
std = loaders.standings(db)
sc_row = std[std["team_name"] == "Santa Cruz"] if not std.empty else std
if sc_row.empty:
    C.empty_state("Classificação da fase anterior não coletada.")
else:
    r = sc_row.iloc[0]
    C.kpi_row([
        {"label": "Posição final", "value": int(r["position"])},
        {"label": "Pontos", "value": int(r["points"])},
        {"label": "Jogos", "value": int(r["played"])},
        {"label": "Total de times na tabela", "value": len(std)},
    ])
    st.caption("Fato registrado ao final da 1ª fase (tabela geral) — não é projeção.")

st.divider()
C.empty_state(
    "**Sobre probabilidade de acesso/rebaixamento:** não calculamos essa probabilidade. "
    "Faria falta confirmar com certeza o regulamento exato da fase atual (quantos times avançam, "
    "critérios de desempate) e simular também o calendário e a forma dos demais 19 times — dado que "
    "não coletamos. **FONTE NECESSÁRIA.** O que mostramos acima é só a distribuição de pontos do "
    "próprio Santa Cruz nos jogos que faltam, a partir do aproveitamento real que ele já teve."
)

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']}", atualizado=h["last_collection"] or "—")
