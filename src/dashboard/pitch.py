"""Desenho do campo + mapa de calor (Plotly). Sem dependências extras."""
from __future__ import annotations

import plotly.graph_objects as go

# Sofascore: x,y ~ 0..100 (x = comprimento no sentido do ataque, y = largura)
_LEN, _WID = 100.0, 100.0


def _pitch_shapes() -> list[dict]:
    line = dict(color="rgba(255,255,255,0.55)", width=1.5)
    S = []
    S.append(dict(type="rect", x0=0, y0=0, x1=_LEN, y1=_WID, line=line))
    S.append(dict(type="line", x0=_LEN / 2, y0=0, x1=_LEN / 2, y1=_WID, line=line))
    S.append(dict(type="circle", x0=_LEN / 2 - 9.15, y0=_WID / 2 - 9.15,
                  x1=_LEN / 2 + 9.15, y1=_WID / 2 + 9.15, line=line))
    # áreas
    for x0, x1 in ((0, 16.5), (_LEN - 16.5, _LEN)):
        S.append(dict(type="rect", x0=x0, y0=_WID / 2 - 20.15, x1=x1, y1=_WID / 2 + 20.15, line=line))
    for x0, x1 in ((0, 5.5), (_LEN - 5.5, _LEN)):
        S.append(dict(type="rect", x0=x0, y0=_WID / 2 - 9.16, x1=x1, y1=_WID / 2 + 9.16, line=line))
    return S


def heatmap_figure(points: list[dict], title: str = "") -> go.Figure:
    """Densidade 2D dos pontos sobre o campo. Ataque para a direita."""
    fig = go.Figure()
    if points:
        xs = [p.get("x") for p in points if p.get("x") is not None]
        ys = [p.get("y") for p in points if p.get("y") is not None]
        fig.add_trace(
            go.Histogram2dContour(
                x=xs, y=ys, colorscale="YlOrRd", showscale=False,
                ncontours=14, line=dict(width=0),
                xaxis="x", yaxis="y", opacity=0.9,
                hovertemplate="x=%{x:.0f} y=%{y:.0f}<extra></extra>",
            )
        )
        # marcador branco (não preto): a mancha de calor vai do amarelo ao
        # vermelho no centro, e preto encostando no vermelho é a única regra
        # de cor proibida na identidade visual do produto.
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers",
                                 marker=dict(size=3, color="rgba(255,255,255,0.55)"),
                                 hoverinfo="skip", showlegend=False))
    fig.update_layout(
        shapes=_pitch_shapes(),
        title=title,
        plot_bgcolor="#1b7a3d", paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[-2, _LEN + 2], visible=False, fixedrange=True),
        yaxis=dict(range=[-2, _WID + 2], visible=False, scaleanchor="x", scaleratio=0.62, fixedrange=True),
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        height=430,
    )
    fig.add_annotation(x=_LEN - 6, y=-1, text="ataque →", showarrow=False,
                       font=dict(color="rgba(255,255,255,0.8)", size=11))
    return fig
