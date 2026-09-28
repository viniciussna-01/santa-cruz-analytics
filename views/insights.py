"""Insights — achados derivados por regras + exportação para LinkedIn."""
from __future__ import annotations

import streamlit as st

from src.analytics import insights, loaders, ratings, scorers, team
from src.dashboard import components as C
from src.dashboard import linkedin as li
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("💡 Insights", "Cada frase abaixo é derivada matematicamente dos dados — nunca opinião solta.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
filt = state.render_global_filters(db)
FILT = {"season_year": filt["season_year"], "competition_id": filt["competition_id"]}
last_n = filt["last_n"] or 5

frases = insights.momentum(db, window=last_n, season_year=filt["season_year"])
for f in frases:
    st.markdown(f"- {f}")

with st.expander("Notas sobre cobertura dos dados"):
    for n in insights.data_notes(db):
        st.markdown(f"- {n}")

st.divider()
C.section("📝 Texto para post no LinkedIn", "Gerado a partir dos números reais do recorte selecionado — edite à vontade antes de publicar.")

s = team.summary(db, last_n=last_n, **FILT)
sc = scorers.scorers_table(db, last_n_matches=last_n, **FILT)
ri = ratings.rating_and_index(db, min_matches=3, **FILT)
h = loaders.data_health(db)

top_scorer = sc.iloc[0] if not sc.empty else None
best_rating = ri.dropna(subset=["nota_media"]).sort_values("nota_media", ascending=False)
best_rating = best_rating.iloc[0] if not best_rating.empty else None

periodo_txt = f"últimos {s['jogos']} jogos" if last_n else "temporada selecionada"
linhas = [
    f"📊 Analisei {s['jogos']} partidas do Santa Cruz-PE utilizando dados públicos do Sofascore ({periodo_txt}).",
    "",
    f"Durante o período:",
    f"• {s['vitorias']}V {s['empates']}E {s['derrotas']}D"
    + (f" — {s['aproveitamento']:.0f}% de aproveitamento" if s["aproveitamento"] is not None else ""),
    f"• {s['gols_marcados']} gols marcados / {s['gols_sofridos']} sofridos (saldo {s['saldo']:+d})",
]
if s["media_gols"] is not None:
    linhas.append(f"• Média de {s['media_gols']:.2f} gols marcados por partida")
if top_scorer is not None:
    part_pct = (top_scorer["gols"] + top_scorer["assistencias"]) / max(1, s["gols_marcados"]) * 100
    linhas.append(
        f"• {top_scorer['jogador']} participou de {int(top_scorer['gols'] + top_scorer['assistencias'])} "
        f"gol(s) da equipe ({top_scorer['gols']:.0f} gols + {top_scorer['assistencias']:.0f} assist.)"
    )
if best_rating is not None:
    linhas.append(f"• {best_rating['jogador']} teve a maior nota média Sofascore no período ({best_rating['nota_media']:.2f})")
linhas += [
    "",
    "A partir desses dados, foi possível identificar padrões de desempenho por mando de campo, "
    "evolução de forma e participação individual em gols — sem estatística inventada: o que não "
    "existe na fonte simplesmente não entra na análise.",
    "",
    f"🔧 Stack: Python, curl_cffi, pandas, SQLite, Streamlit, Plotly.",
    f"📡 Fonte: Sofascore (dados públicos, API não-oficial) — coleta em {h['last_collection'] or '—'}.",
    "",
    "#DataAnalytics #SportsAnalytics #Python #SantaCruz #Futebol",
]
post_text = "\n".join(linhas)
st.text_area("Prévia (copie e ajuste antes de publicar)", post_text, height=340)
st.download_button("⬇️ Baixar texto (.txt)", post_text.encode("utf-8"),
                   file_name="santa_cruz_analytics_post.txt", mime="text/plain")

st.divider()
C.section("🖼️ Cards para LinkedIn", "Imagens 1080×1350 geradas a partir dos dados reais do recorte atual.")

periodo_label = filt["season_label"]
fonte_label = "Sofascore"

if st.button("Gerar cards", type="primary"):
    cards = []
    cards.append(("01_santa_cruz_em_numeros.png", li.numbers_card(
        "Santa Cruz em números", periodo_label,
        [("Jogos", str(s["jogos"])), ("Vitórias", str(s["vitorias"])), ("Empates", str(s["empates"])),
         ("Derrotas", str(s["derrotas"])), ("Gols marcados", str(s["gols_marcados"])),
         ("Gols sofridos", str(s["gols_sofridos"])),
         ("Aproveitamento", f"{s['aproveitamento']:.0f}%" if s["aproveitamento"] is not None else "—"),
         ("Saldo", f"{s['saldo']:+d}")],
        fonte_label, periodo_label,
    )))
    ev = team.evolution(db, windows=(5, 10, 15), **FILT)
    ev_ok = ev[ev["jogos"] > 0].dropna(subset=["aproveitamento"])
    if not ev_ok.empty:
        cards.append(("02_desempenho.png", li.bar_card(
            "Desempenho", "Aproveitamento (%) por janela de jogos",
            ev_ok["janela"].tolist(), ev_ok["aproveitamento"].tolist(),
            fonte_label, periodo_label, value_fmt="{:.0f}%",
        )))
    if not sc.empty:
        top5 = sc.head(5)
        cards.append(("03_artilharia.png", li.bar_card(
            "Artilharia", "Gols no período", top5["jogador"].tolist(), top5["gols"].tolist(),
            fonte_label, periodo_label,
        )))
    if not ri.empty:
        topr = ri.dropna(subset=["nota_media"]).sort_values("nota_media", ascending=False).head(5)
        if not topr.empty:
            cards.append(("04_jogadores.png", li.bar_card(
                "Jogadores", "Maiores notas Sofascore", topr["jogador"].tolist(),
                topr["nota_media"].tolist(), fonte_label, periodo_label, value_fmt="{:.2f}",
            )))
    if frases:
        cards.append(("05_principais_insights.png", li.text_card(
            "Insights", "Principais achados", frases[:5], fonte_label, periodo_label,
        )))
    cards.append(("06_como_foi_construido.png", li.text_card(
        "Metodologia", "Como os dados foram construídos", [
            "Coleta automática via API pública do Sofascore (curl_cffi).",
            "Armazenamento em SQLite — dado ausente fica NULL, nunca inventado.",
            "Índice de Performance Santa Cruz: complementar à nota Sofascore, com pesos por posição.",
            "Pipeline 100% Python: pandas, Streamlit, Plotly.",
            f"Cobertura: {h['matches_with_player_stats']}/{h['matches_finished']} partidas com estatística individual.",
        ], fonte_label, periodo_label,
    )))

    st.session_state["_li_cards"] = cards

cards = st.session_state.get("_li_cards")
if cards:
    cols = st.columns(3)
    for i, (fname, img) in enumerate(cards):
        with cols[i % 3]:
            st.image(img, use_container_width=True)
            st.download_button("⬇️ Baixar", img, file_name=fname, mime="image/png", key=f"dl_{fname}")

C.source_footer(periodo=f"{filt['season_label']} · {filt['competition_label']}",
                atualizado=h["last_collection"] or "—")
