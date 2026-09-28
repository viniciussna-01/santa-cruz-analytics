"""Qualidade dos Dados — auditoria transparente do que está no banco."""
from __future__ import annotations

import streamlit as st

from src.analytics import quality
from src.dashboard import components as C
from src.dashboard import state, theme

theme.inject()
theme.brand_header()
C.section("✅ Qualidade dos Dados", "Cobertura, consistência e frescor da coleta — auditado a cada carregamento.")

db = state.get_database()
if not state.require_data(db):
    st.stop()
state.render_global_filters(db)

rep = quality.run(db)

sev_color = {"alta": theme.RED, "média": theme.INK, "baixa": theme.GRAY, "info": theme.GRAY}
score_kind = "up" if rep.score >= 70 else ("flat" if rep.score >= 40 else "down")

c1, c2 = st.columns([1, 2])
with c1:
    st.markdown(C.kpi_card("Score de qualidade", f"{rep.score:.0f}/100", accent=True), unsafe_allow_html=True)
    st.caption(f"Calculado em {rep.checked_at}")
with c2:
    h = rep.health
    C.kpi_row([
        {"label": "Partidas finalizadas", "value": h["matches_finished"]},
        {"label": "Com escalação", "value": h["matches_with_lineups"]},
        {"label": "Com estatística individual", "value": h["matches_with_player_stats"]},
        {"label": "Com mapa de calor", "value": h["matches_with_heatmap"]},
    ])

st.write("")
finished = rep.health["matches_finished"] or 1
C.progress_bar(100 * rep.health["matches_with_lineups"] / finished, "Cobertura de escalação")
C.progress_bar(100 * rep.health["matches_with_player_stats"] / finished, "Cobertura de estatística individual")
C.progress_bar(100 * rep.health["matches_with_heatmap"] / finished, "Cobertura de mapa de calor")

st.divider()
C.section("Checagens", "Duplicidade, dados ausentes, datas inválidas e inconsistências físicas.")
if not rep.issues:
    st.success("Nenhuma inconsistência encontrada nas checagens automáticas.")
else:
    for i in sorted(rep.issues, key=lambda x: {"alta": 0, "média": 1, "baixa": 2, "info": 3}[x.severity]):
        color = sev_color[i.severity]
        st.markdown(
            f"<div style='border-left:3px solid {color};padding:6px 12px;margin-bottom:8px;"
            f"background:{theme.SURFACE};border-radius:0 8px 8px 0'>"
            f"<span class='scda-badge' style='background:{color}'>{i.severity.upper()}</span> "
            f"<b>{i.titulo}</b>"
            + (f" — {i.contagem}" if i.contagem else "")
            + (f"<div style='color:{theme.TEXT_MUTED};font-size:.85rem;margin-top:2px'>{i.detalhe}</div>" if i.detalhe else "")
            + "</div>",
            unsafe_allow_html=True,
        )

C.source_footer(atualizado=rep.health["last_collection"] or "—")
