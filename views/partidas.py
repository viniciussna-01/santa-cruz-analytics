"""Partidas — detalhe completo de cada jogo coletado."""
from __future__ import annotations

import streamlit as st

from src.analytics import loaders
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("📅 Partidas", "Escalação, gols, cartões, substituições e estatísticas de cada jogo.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)

matches = loaders.santacruz_matches(db, season_year=filt["season_year"], competition_id=filt["competition_id"])
if matches.empty:
    C.empty_state("Sem partidas no recorte.")
    st.stop()

matches = matches.copy()
matches["rot"] = (
    matches["date"].astype(str) + " · " + matches["home_team_name"] + " " +
    matches["home_score"].astype("Int64").astype(str) + "–" +
    matches["away_score"].astype("Int64").astype(str) + " " + matches["away_team_name"] +
    " · " + matches["competition"].fillna("")
)
sel = st.selectbox("Partida", matches["rot"].tolist())
row = matches[matches["rot"] == sel].iloc[0]
mid = int(row["id"])

placar = f"{row.get('home_score')}–{row.get('away_score')}" if row.get("home_score") is not None else "x"
st.markdown(f"### {row['home_team_name']} {placar} {row['away_team_name']}")
badge_color = theme.RESULT_COLORS.get(row.get("santacruz_result"), theme.GRAY)
st.markdown(
    f"<span class='scda-badge' style='background:{badge_color}'>{row.get('santacruz_result') or '?'}</span> "
    f"<span class='scda-pill'>{row['date']}</span> <span class='scda-pill'>{row['competition']}</span> "
    f"<span class='scda-pill'>{'Casa' if row['is_santacruz_home'] else 'Fora'}</span>",
    unsafe_allow_html=True,
)
st.write("")

inc = db.query_df(
    "SELECT minute, type, sub_type, is_santacruz, player_name, assist_player_name, "
    "player_in_name, player_out_name FROM match_incidents WHERE match_id=? ORDER BY minute",
    (mid,),
)
cc = st.columns(3)
goals = inc[inc["type"] == "goal"]
cards = inc[inc["type"] == "card"]
subs = inc[inc["type"] == "substitution"]
with cc[0]:
    C.section("Gols")
    for _, g in goals.iterrows():
        lado = "SC" if g["is_santacruz"] else "ADV"
        ass = f" (assist. {g['assist_player_name']})" if g["assist_player_name"] else ""
        st.write(f"{int(g['minute'])}' [{lado}] {g['player_name']}{ass}")
    if goals.empty:
        st.caption("—")
with cc[1]:
    C.section("Cartões")
    for _, cd in cards.iterrows():
        st.write(f"{int(cd['minute'])}' {'🟥' if 'red' in str(cd['sub_type']) else '🟨'} {cd['player_name']}")
    if cards.empty:
        st.caption("—")
with cc[2]:
    C.section("Substituições")
    for _, sb in subs.iterrows():
        st.write(f"{int(sb['minute'])}' ↑{sb['player_in_name']}  ↓{sb['player_out_name']}")
    if subs.empty:
        st.caption("—")

tstats = db.query_df(
    "SELECT name, group_name, is_santacruz, display FROM match_team_stats "
    "WHERE match_id=? AND period='ALL' ORDER BY group_name",
    (mid,),
)
if not tstats.empty:
    piv = tstats.pivot_table(index=["group_name", "name"], columns="is_santacruz",
                             values="display", aggfunc="first").reset_index()
    piv.columns = ["Grupo", "Estatística"] + [("Santa Cruz" if c == 1 else "Adversário") for c in piv.columns[2:]]
    st.markdown("**Estatísticas da partida**")
    st.dataframe(piv, hide_index=True, use_container_width=True)
else:
    C.empty_state("Estatísticas da partida não disponíveis na fonte para este jogo.")

pstats = db.query_df(
    """
    SELECT p.name AS Jogador, s.position AS Pos, s.started AS Tit, s.minutes AS Min,
           s.rating AS Nota, s.goals AS G, s.assists AS A, s.shots AS Fin,
           s.shots_on_target AS "Fin.Alvo", s.passes AS Passes, s.key_passes AS "P.Chave",
           s.tackles_won AS Desarm, s.interceptions AS Interc,
           s.yellow_cards AS "🟨", s.red_cards AS "🟥"
    FROM player_match_stats s JOIN players p ON p.id=s.player_id
    WHERE s.match_id=? AND s.is_santacruz=1
    ORDER BY s.started DESC, s.minutes DESC
    """,
    (mid,),
)
if not pstats.empty:
    st.markdown("**Desempenho dos jogadores (Santa Cruz)**")
    st.dataframe(pstats, hide_index=True, use_container_width=True, height=460)
else:
    C.empty_state("Sem estatísticas individuais para esta partida na fonte.")

h = loaders.data_health(db)
C.source_footer(atualizado=h["last_collection"] or "—")
