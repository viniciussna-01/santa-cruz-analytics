"""Identidade visual — Santa Cruz Data Analytics.

Paleta estrita do escudo do Santa Cruz: **preto, branco e vermelho** — só
essas 3 cores (mais tons neutros derivados de preto/branco, que não contam
como uma 4ª cor). Nenhum verde/azul/âmbar em lugar nenhum da UI.

Regra única, não-negociável: **o preto nunca encosta no vermelho**. No
escudo, o branco sempre separa as duas metades (preto e vermelho). Aqui isso
é garantido estruturalmente: o fundo é branco (não preto), preto é usado só
para texto/traços finos, vermelho é o único destaque vívido — e todo
elemento vermelho tem respiro (padding/gap) antes de qualquer área preta,
nunca uma borda preta encostando numa borda/preenchimento vermelho.

Exceção deliberada: o gramado do mapa de calor continua verde — é a
representação literal de um campo de futebol (convenção universal de
visualização esportiva), não uma cor de marca.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# tokens — só preto / branco / vermelho (+ tons neutros preto-branco)
# ---------------------------------------------------------------------------
BG = "#ffffff"
SURFACE = "#f7f7f8"        # cinza quase-branco — para cards
SURFACE_2 = "#eeeeef"      # um tom abaixo, para hover/gradiente
BORDER = "#e3e3e5"         # borda sutil (tom de preto bem diluído), não preto puro
INK = "#111111"            # preto de marca — texto forte, traços, "derrota"
TEXT = "#141414"           # texto principal
TEXT_MUTED = "#6b6b70"     # cinza médio (tom de preto) — texto secundário
RED = "#e30613"            # vermelho do escudo — único destaque vívido
RED_SOFT = "rgba(227,6,19,0.08)"
GRAY = "#8a8a8f"           # cinza neutro (tom de preto) — "empate"
GRAY_LIGHT = "#c7c7ca"

# aliases mantidos por compatibilidade com código existente — não são mais
# verde/âmbar, apontam para a paleta preto/branco/vermelho
GREEN = INK
AMBER = TEXT_MUTED

RESULT_COLORS = {"V": RED, "E": GRAY, "D": INK}
POSITION_COLORS = {"G": INK, "D": "#48484c", "M": GRAY, "F": RED}

PLOTLY_TEMPLATE = "plotly_white"
CHART_COLORWAY = [RED, INK, GRAY, GRAY_LIGHT]


def _css() -> str:
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, sans-serif;
    }}

    .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1320px; }}

    /* ---- cabeçalho de marca ---- */
    .scda-brand {{
        display: flex; align-items: baseline; gap: .6rem; margin-bottom: 0;
    }}
    .scda-brand .mark {{
        font-family: 'Space Grotesk', 'Inter', sans-serif;
        font-weight: 700; font-size: 1.9rem; letter-spacing: -0.02em; color: {INK};
    }}
    /* "DATA" em vermelho: cercado de espaço em branco dos dois lados, nunca
       encostando no preto do resto do título (gap de letra + folga própria) */
    .scda-brand .mark span {{ color: {RED}; padding: 0 .12em; }}
    .scda-sub {{ color: {TEXT_MUTED}; font-size: .95rem; margin-top: -4px; margin-bottom: 1.1rem; }}

    /* ---- cards de KPI ---- */
    .scda-kpi {{
        background: {SURFACE};
        border: 1px solid {BORDER}; border-radius: 12px;
        padding: 14px 16px; height: 100%;
    }}
    .scda-kpi .label {{
        color: {TEXT_MUTED}; font-size: .74rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px;
    }}
    .scda-kpi .value {{
        font-family: 'Space Grotesk', sans-serif; font-size: 1.9rem; font-weight: 700;
        color: {INK}; line-height: 1.1;
    }}
    .scda-kpi .delta {{ font-size: .8rem; margin-top: 4px; font-weight: 600; }}
    .scda-kpi .delta.up {{ color: {INK}; }}
    .scda-kpi .delta.down {{ color: {RED}; }}
    .scda-kpi .delta.flat {{ color: {TEXT_MUTED}; }}
    /* card em destaque: preenchimento branco entre a borda vermelha e o
       conteúdo preto — o padding do .scda-kpi já garante essa folga */
    .scda-kpi.accent {{ background: #fff; border: 1.5px solid {RED}; box-shadow: 0 0 0 3px {RED_SOFT}; }}

    /* ---- badges ---- */
    .scda-badge {{
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: .74rem; font-weight: 700; letter-spacing: .02em;
        color: #fff; margin-right: 6px; margin-bottom: 4px;
    }}
    .scda-pill {{
        display: inline-block; padding: 3px 11px; border-radius: 999px;
        font-size: .78rem; font-weight: 600; color: {TEXT_MUTED};
        background: {SURFACE_2}; border: 1px solid {BORDER}; margin-right: 6px;
    }}

    /* ---- seções ---- */
    .scda-section-title {{
        font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 1.25rem;
        color: {INK}; margin-bottom: 2px; margin-top: .4rem;
    }}
    .scda-section-sub {{ color: {TEXT_MUTED}; font-size: .85rem; margin-bottom: .8rem; }}

    /* ---- fonte / rodapé de proveniência ---- */
    .scda-source {{
        border-top: 1px solid {BORDER}; margin-top: 1.6rem; padding-top: .7rem;
        color: {TEXT_MUTED}; font-size: .78rem; display: flex; gap: 1.4rem; flex-wrap: wrap;
    }}
    .scda-source b {{ color: {INK}; }}

    /* ---- estado vazio ---- */
    .scda-empty {{
        border: 1px dashed {BORDER}; border-radius: 12px; padding: 1.1rem 1.3rem;
        color: {TEXT_MUTED}; background: {SURFACE}; font-size: .9rem;
    }}
    .scda-empty b {{ color: {INK}; }}

    /* ---- barra de progresso simples ---- */
    .scda-bar-track {{ background: {SURFACE_2}; border-radius: 6px; height: 8px; overflow: hidden; }}
    .scda-bar-fill {{ background: {RED}; height: 100%; border-radius: 6px; }}

    /* ---- tabelas ---- */
    [data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 10px; overflow: hidden; }}

    /* ---- sidebar: mantida clara (nunca preta) para o botão vermelho nunca
       encostar direto num fundo preto ---- */
    section[data-testid="stSidebar"] {{ border-right: 1px solid {BORDER}; background: {SURFACE}; }}
    </style>
    """


def inject(title: str | None = None) -> None:
    st.markdown(_css(), unsafe_allow_html=True)
    if title:
        st.markdown(
            f"<div class='scda-section-title'>{title}</div>",
            unsafe_allow_html=True,
        )


def brand_header() -> None:
    st.markdown(
        "<div class='scda-brand'><span class='mark'>SANTA CRUZ <span>DATA</span> ANALYTICS</span></div>"
        "<div class='scda-sub'>Análise de desempenho baseada em dados · Santa Cruz Futebol Clube (PE)</div>",
        unsafe_allow_html=True,
    )
