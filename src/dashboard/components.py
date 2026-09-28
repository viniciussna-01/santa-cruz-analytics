"""Componentes visuais reutilizáveis do Santa Cruz Data Analytics.

Nenhum componente aqui decide "o que é bom ou ruim" — só exibe. Cálculo e
interpretação ficam nas camadas de analytics; aqui é só apresentação.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

import plotly.graph_objects as go
import streamlit as st

from src.dashboard import theme


def section(title: str, subtitle: Optional[str] = None) -> None:
    html = f"<div class='scda-section-title'>{title}</div>"
    if subtitle:
        html += f"<div class='scda-section-sub'>{subtitle}</div>"
    st.markdown(html, unsafe_allow_html=True)


def kpi_card(label: str, value, delta: Optional[str] = None, delta_kind: str = "flat",
            accent: bool = False) -> str:
    """Retorna o HTML de um card — use dentro de `st.markdown(..., unsafe_allow_html=True)`
    (chamado por `kpi_row` para montar uma grade)."""
    cls = "scda-kpi accent" if accent else "scda-kpi"
    delta_html = f"<div class='delta {delta_kind}'>{delta}</div>" if delta else ""
    return (
        f"<div class='{cls}'><div class='label'>{label}</div>"
        f"<div class='value'>{value}</div>{delta_html}</div>"
    )


def kpi_row(items: Sequence[dict]) -> None:
    """items: [{'label':..., 'value':..., 'delta':None, 'delta_kind':'flat', 'accent':False}]"""
    cols = st.columns(len(items))
    for col, it in zip(cols, items):
        with col:
            st.markdown(
                kpi_card(
                    it["label"], it["value"], it.get("delta"),
                    it.get("delta_kind", "flat"), it.get("accent", False),
                ),
                unsafe_allow_html=True,
            )


def result_badges(letters: Sequence[str]) -> None:
    if not letters:
        st.markdown("<span class='scda-pill'>sem jogos no recorte</span>", unsafe_allow_html=True)
        return
    spans = "".join(
        f"<span class='scda-badge' style='background:{theme.RESULT_COLORS.get(l, theme.GRAY)}'>{l}</span>"
        for l in letters
    )
    st.markdown(spans, unsafe_allow_html=True)


def position_badge(pos: Optional[str]) -> str:
    if not pos:
        return "<span class='scda-pill'>—</span>"
    p = str(pos)[0].upper()
    color = theme.POSITION_COLORS.get(p, theme.GRAY)
    return f"<span class='scda-badge' style='background:{color}'>{p}</span>"


def progress_bar(pct: Optional[float], label: Optional[str] = None) -> None:
    pct = 0 if pct is None else max(0, min(100, pct))
    label_html = f"<div style='font-size:.78rem;color:{theme.TEXT_MUTED};margin-bottom:3px'>{label}</div>" if label else ""
    st.markdown(
        f"{label_html}<div class='scda-bar-track'><div class='scda-bar-fill' style='width:{pct}%'></div></div>",
        unsafe_allow_html=True,
    )


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def empty_state(message: str) -> None:
    """Aviso em caixa tracejada. Suporta **negrito** (convertido para <b> —
    dentro de um bloco HTML bruto o Markdown não processa `**`)."""
    html = _BOLD_RE.sub(r"<b>\1</b>", message)
    st.markdown(f"<div class='scda-empty'>ℹ️ {html}</div>", unsafe_allow_html=True)


def source_footer(fonte: str = "Sofascore (dados públicos, API não-oficial)",
                  periodo: Optional[str] = None, atualizado: Optional[str] = None) -> None:
    parts = [f"Fonte: <b>{fonte}</b>"]
    if periodo:
        parts.append(f"Período: <b>{periodo}</b>")
    if atualizado:
        parts.append(f"Última atualização: <b>{atualizado}</b>")
    st.markdown("<div class='scda-source'>" + "".join(f"<span>{p}</span>" for p in parts) + "</div>",
               unsafe_allow_html=True)


def style_fig(fig: go.Figure, title: Optional[str] = None, height: Optional[int] = None) -> go.Figure:
    """Aplica o tema escuro padrão a uma figura Plotly.

    `title` só é aplicado quando passado explicitamente — do contrário o
    título já definido pela própria figura (ex.: `px.bar(..., title=...)`)
    é preservado.
    """
    has_title = bool(title) or bool(fig.layout.title.text)
    layout_kwargs = dict(
        template=theme.PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=theme.TEXT, size=12),
        colorway=theme.CHART_COLORWAY,
        margin=dict(l=10, r=10, t=48 if has_title else 16, b=10),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    if title:
        layout_kwargs["title"] = title
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(gridcolor=theme.BORDER, zerolinecolor=theme.BORDER)
    fig.update_yaxes(gridcolor=theme.BORDER, zerolinecolor=theme.BORDER)
    if height:
        fig.update_layout(height=height)
    return fig
