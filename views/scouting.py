"""Scouting — perfil individual do jogador."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.analytics import loaders, players, ratings
from src.dashboard import components as C
from src.dashboard import state, theme
from src.utils.helpers import age_years

theme.inject()
theme.brand_header()
C.section("🔎 Scouting", "Perfil individual — só métricas calculáveis a partir da fonte entram aqui.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}

pt = players.player_table(db, min_matches=1, **FILT)
if pt.empty:
    C.empty_state("Sem jogadores com estatística no recorte selecionado.")
    st.stop()

nome_sel = st.selectbox("Jogador", pt.sort_values("jogador")["jogador"].tolist())
pid = int(pt[pt["jogador"] == nome_sel]["player_id"].iloc[0])

row = pt[pt["player_id"] == pid].iloc[0]
info = db.execute("SELECT position, dob_timestamp, country FROM players WHERE id = ?", (pid,)).fetchone()
idade = age_years(info["dob_timestamp"]) if info else None

ri = ratings.rating_and_index(db, min_matches=1, **FILT)
rrow = ri[ri["player_id"] == pid]
rrow = rrow.iloc[0] if not rrow.empty else None

c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(
        f"### {nome_sel}  {C.position_badge(row['posicao'])}",
        unsafe_allow_html=True,
    )
    meta = [f"Clube: **Santa Cruz**"]
    if idade is not None:
        meta.append(f"Idade: **{idade} anos**")
    if info and info["country"]:
        meta.append(f"País: **{info['country']}**")
    meta.append(f"Temporada: **{filt['season_label']}**")
    st.caption(" · ".join(meta))
with c2:
    if rrow is not None and rrow["ips"] is not None:
        st.markdown(C.kpi_card("IPS", f"{rrow['ips']:.2f}", accent=True), unsafe_allow_html=True)

C.kpi_row([
    {"label": "Jogos", "value": int(row["jogos"])},
    {"label": "Titularidades", "value": int(row["titularidades"]) if row["titularidades"] == row["titularidades"] else "—"},
    {"label": "Minutos", "value": int(row["minutos"]) if row["minutos"] == row["minutos"] else "—"},
    {"label": "Gols", "value": int(row["gols"])},
    {"label": "Assistências", "value": int(row["assistencias"])},
    {"label": "Nota média", "value": f"{row['nota_media']:.2f}" if row["nota_media"] == row["nota_media"] else "—"},
])

st.divider()
tabP, tabE, tabT = st.tabs(["Performance (índice)", "Evolução da nota", "Estatísticas completas"])

with tabP:
    if rrow is None or rrow["ips_bruto"] is None:
        C.empty_state(
            "Sem minutos e/ou nota Sofascore suficientes neste recorte para calcular os "
            "sub-índices de performance."
        )
    else:
        st.caption(
            "Sub-índices 0–10 por 90 minutos, comparados a benchmarks fixos — ver metodologia em "
            "docs/METODOLOGIA.md. **Não são notas oficiais do Sofascore.**"
        )
        subs = {
            "Ofensivo": rrow["sub_ofensivo"], "Criação": rrow["sub_criacao"],
            "Passe": rrow["sub_passe"], "Defesa": rrow["sub_defesa"],
            "Disciplina": rrow["sub_disciplina"],
        }
        if row["posicao"] and str(row["posicao"]).upper().startswith("G"):
            subs["Goleiro"] = rrow["sub_goleiro"]
        fig = go.Figure(go.Bar(
            x=list(subs.values()), y=list(subs.keys()), orientation="h",
            marker_color=theme.RED, text=[f"{v:.1f}" for v in subs.values()], textposition="outside",
        ))
        fig.update_layout(title="Sub-índices de performance", xaxis=dict(range=[0, 10]))
        st.plotly_chart(C.style_fig(fig, height=320), use_container_width=True)
        if rrow["limitacao"]:
            st.caption(f"⚠️ {rrow['limitacao']}")

with tabE:
    tl = ratings.rating_timeline(db, pid, **FILT)
    tl = tl[tl["rating"].notna()]
    if tl.empty:
        C.empty_state("Sem notas registradas para este jogador no recorte.")
    else:
        tl = tl.sort_values("match_date")
        fig = go.Figure(go.Scatter(x=tl["match_date"], y=tl["rating"], mode="lines+markers",
                                   line=dict(color=theme.RED), hovertext=tl["opponent_name"]))
        fig.add_hline(y=tl["rating"].mean(), line_dash="dot", line_color=theme.GRAY,
                     annotation_text=f"média {tl['rating'].mean():.2f}")
        fig.update_layout(title="Nota Sofascore por partida", yaxis=dict(range=[0, 10]))
        st.plotly_chart(C.style_fig(fig), use_container_width=True)

with tabT:
    tidy = row.drop(labels=["player_id"]).reset_index()
    tidy.columns = ["Campo", "Valor"]
    tidy["Valor"] = tidy["Valor"].apply(
        lambda v: "—" if v is None or (isinstance(v, float) and v != v) else str(v)
    )
    st.dataframe(tidy, hide_index=True, use_container_width=True, height=560)

h = loaders.data_health(db)
C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
