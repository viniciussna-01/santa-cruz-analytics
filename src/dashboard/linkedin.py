"""Geração de cards/slides de imagem para compartilhar no LinkedIn.

Todo número que entra num card vem de `src/analytics/*` — este módulo só
desenha. Formato 1080x1350 (retrato 4:5, bom para feed do LinkedIn).

Paleta estrita do escudo (preto/branco/vermelho) com a mesma regra do resto
do app: fundo branco, preto só para texto/traços, vermelho como destaque —
e o vermelho nunca fica encostado numa área preta (por isso o texto de valor
das barras fica FORA do preenchimento vermelho, nunca sobreposto a ele).
"""
from __future__ import annotations

from typing import Optional, Sequence

import plotly.graph_objects as go

W, H = 1080, 1350
BG = "#ffffff"
SURFACE = "#f7f7f8"
RED = "#e30613"
INK = "#111111"
TEXT = "#141414"
MUTED = "#6b6b70"
BORDER = "#dcdcdf"
TRACK = "#ececee"


def _canvas() -> go.Figure:
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[0, 1], fixedrange=True)
    fig.update_yaxes(visible=False, range=[0, 1], fixedrange=True, scaleanchor="x", scaleratio=H / W)
    fig.update_layout(
        width=W, height=H, plot_bgcolor=BG, paper_bgcolor=BG,
        margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
    )
    return fig


def _brand_footer(fig: go.Figure, fonte: str, periodo: str) -> None:
    fig.add_shape(type="line", x0=0.07, x1=0.93, y0=0.085, y1=0.085, line=dict(color=BORDER, width=1))
    fig.add_annotation(x=0.07, y=0.055, xanchor="left", showarrow=False, align="left",
                       text="<b>SANTA CRUZ DATA ANALYTICS</b>", font=dict(color=RED, size=15, family="Arial Black"))
    fig.add_annotation(x=0.07, y=0.03, xanchor="left", showarrow=False, align="left",
                       text=f"Fonte: {fonte} · Período: {periodo}", font=dict(color=MUTED, size=12))


def _title_block(fig: go.Figure, kicker: str, title: str) -> None:
    fig.add_annotation(x=0.07, y=0.93, xanchor="left", showarrow=False, align="left",
                       text=kicker.upper(), font=dict(color=RED, size=15, family="Arial Black"))
    fig.add_annotation(x=0.07, y=0.87, xanchor="left", showarrow=False, align="left",
                       text=f"<b>{title}</b>", font=dict(color=INK, size=34, family="Arial"))


def numbers_card(kicker: str, title: str, kpis: Sequence[tuple[str, str]],
                 fonte: str, periodo: str) -> bytes:
    """Card de KPIs grandes (grade 2 colunas)."""
    fig = _canvas()
    _title_block(fig, kicker, title)

    cols, rows = 2, (len(kpis) + 1) // 2
    x0, x1 = 0.07, 0.93
    y0, y1 = 0.16, 0.78
    cw = (x1 - x0) / cols
    rh = (y1 - y0) / rows
    for i, (label, value) in enumerate(kpis):
        r, c = divmod(i, cols)
        cx0 = x0 + c * cw + 0.015
        cx1 = x0 + (c + 1) * cw - 0.015
        cy0 = y1 - (r + 1) * rh + 0.02
        cy1 = y1 - r * rh - 0.02
        fig.add_shape(type="rect", x0=cx0, x1=cx1, y0=cy0, y1=cy1, line=dict(color=BORDER, width=1),
                     fillcolor=SURFACE)
        fig.add_annotation(x=(cx0 + cx1) / 2, y=cy0 + (cy1 - cy0) * 0.62, showarrow=False,
                           text=f"<b>{value}</b>", font=dict(color=INK, size=40, family="Arial"))
        fig.add_annotation(x=(cx0 + cx1) / 2, y=cy0 + (cy1 - cy0) * 0.22, showarrow=False,
                           text=label.upper(), font=dict(color=MUTED, size=13, family="Arial"))
    _brand_footer(fig, fonte, periodo)
    return fig.to_image(format="png", width=W, height=H, scale=1)


def bar_card(kicker: str, title: str, categories: Sequence[str], values: Sequence[float],
            fonte: str, periodo: str, value_fmt: str = "{:.0f}") -> bytes:
    fig = _canvas()
    _title_block(fig, kicker, title)
    n = len(categories)
    x0, x1 = 0.07, 0.80          # trilha termina antes de 0.93 — sobra espaço
    x_value = 0.83                # ...para o valor ficar SEMPRE fora do preenchimento vermelho
    y0, y1 = 0.16, 0.78
    bar_h = (y1 - y0) / max(1, n) * 0.62
    gap = (y1 - y0) / max(1, n)
    maxv = max(values) if values else 1
    for i, (cat, val) in enumerate(zip(categories, values)):
        cy = y1 - i * gap - gap / 2
        frac = 0 if maxv == 0 else val / maxv
        fig.add_annotation(x=x0, y=cy + bar_h * 0.55, xanchor="left", showarrow=False,
                           text=cat, font=dict(color=INK, size=16))
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=cy - bar_h / 2, y1=cy, line=dict(width=0),
                     fillcolor=TRACK)
        fig.add_shape(type="rect", x0=x0, x1=x0 + (x1 - x0) * frac, y0=cy - bar_h / 2, y1=cy,
                     line=dict(width=0), fillcolor=RED)
        fig.add_annotation(x=x_value, y=cy - bar_h * 0.25, xanchor="left", showarrow=False,
                           text=f"<b>{value_fmt.format(val)}</b>", font=dict(color=INK, size=17))
    _brand_footer(fig, fonte, periodo)
    return fig.to_image(format="png", width=W, height=H, scale=1)


def text_card(kicker: str, title: str, bullets: Sequence[str], fonte: str, periodo: str) -> bytes:
    fig = _canvas()
    _title_block(fig, kicker, title)
    y = 0.76
    for b in bullets:
        fig.add_shape(type="circle", x0=0.065, x1=0.078, y0=y - 0.006, y1=y + 0.006,
                     line=dict(width=0), fillcolor=RED)
        fig.add_annotation(x=0.10, y=y, xanchor="left", yanchor="middle", showarrow=False, align="left",
                           text=b, font=dict(color=INK, size=17), width=int(W * 0.8))
        y -= 0.10
    _brand_footer(fig, fonte, periodo)
    return fig.to_image(format="png", width=W, height=H, scale=1)
