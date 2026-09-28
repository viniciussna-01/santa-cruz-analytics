"""One-pager para compartilhar no LinkedIn — PNG único, pronto para postar.

Composição via Pillow (layout/tipografia/logo) + Plotly/kaleido (gráficos)
+ `src/dashboard/pitch.py` (mapa de calor). Mesma regra de cor do resto do
produto: só preto/branco/vermelho, preto nunca encosta no vermelho — ver
`src/dashboard/theme.py`.

Uso:
    from src.dashboard.onepager import build
    png_bytes = build(db, season_year=2026, last_n=10)
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFont

from src.analytics import insights, loaders, ratings, scorers, team
from src.dashboard import theme
from src.dashboard.pitch import heatmap_figure
from src.database import Database

ASSETS = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS / "santacruz_logo.png"

W = 1200
MARGIN = 70
CONTENT_W = W - 2 * MARGIN

RED = theme.RED
INK = theme.INK
GRAY = theme.GRAY
GRAY_LIGHT = theme.GRAY_LIGHT
BORDER = "#e3e3e5"
SURFACE = "#f7f7f8"
WHITE = "#ffffff"

_FONT_DIR = Path(r"C:\Windows\Fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(_FONT_DIR / name), size)
    except OSError:
        return ImageFont.load_default()


F_TITLE = lambda s: _font("arialbd.ttf", s)  # noqa: E731
F_BODY = lambda s: _font("arial.ttf", s)  # noqa: E731


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _rounded_tile(draw: ImageDraw.ImageDraw, box, fill, outline, width=1, radius=14):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _kpi_tile(draw: ImageDraw.ImageDraw, x0: int, y0: int, w: int, h: int,
             label: str, value: str, accent: bool = False) -> None:
    box = (x0, y0, x0 + w, y0 + h)
    if accent:
        _rounded_tile(draw, box, fill=WHITE, outline=RED, width=2)
    else:
        _rounded_tile(draw, box, fill=SURFACE, outline=BORDER, width=1)
    vf = F_TITLE(34)
    lf = F_BODY(13)
    vw = _text_w(draw, value, vf)
    draw.text((x0 + w / 2 - vw / 2, y0 + h * 0.30), value, font=vf, fill=INK)
    lw = _text_w(draw, label.upper(), lf)
    draw.text((x0 + w / 2 - lw / 2, y0 + h * 0.68), label.upper(), font=lf, fill=GRAY)


def _badge(draw: ImageDraw.ImageDraw, x: int, y: int, letter: str, d: int = 40) -> int:
    """Desenha um badge circular V/E/D e devolve a próxima posição x."""
    color = {"V": RED, "E": GRAY, "D": INK}.get(letter, GRAY)
    draw.ellipse((x, y, x + d, y + d), fill=color)
    f = F_TITLE(16)
    tw = _text_w(draw, letter, f)
    draw.text((x + d / 2 - tw / 2, y + d / 2 - 10), letter, font=f, fill=WHITE)
    return x + d + 10


def _plotly_png(fig: go.Figure, width: int, height: int, scale: int = 3) -> Image.Image:
    """Renderiza em alta resolução (scale=3, para ficar nítido no LinkedIn)
    e redimensiona de volta ao tamanho declarado (width,height) — sem isso
    a imagem pastada ficaria `scale`x maior que o espaço reservado no layout."""
    fig.update_layout(width=width, height=height)
    png = fig.to_image(format="png", width=width, height=height, scale=scale)
    img = Image.open(io.BytesIO(png)).convert("RGBA")
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    return img


def _points_chart(mbm, width: int, height: int) -> Image.Image:
    colors = [theme.RESULT_COLORS.get(r, GRAY) for r in mbm["santacruz_result"]]
    labels = [f"{d}<br>{op}" for d, op in zip(mbm["date"].astype(str), mbm["opponent_name"].fillna("?"))]
    fig = go.Figure(go.Bar(x=list(range(len(mbm))), y=mbm["pontos"], marker_color=colors,
                           text=mbm["santacruz_result"], textposition="outside", textfont=dict(size=12)))
    fig.update_layout(
        template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial", color=INK, size=13),
        margin=dict(l=10, r=10, t=10, b=60),
        yaxis=dict(range=[0, 3.6], showticklabels=False, showgrid=False, zeroline=False),
        xaxis=dict(tickmode="array", tickvals=list(range(len(mbm))), ticktext=labels, tickfont=dict(size=10)),
    )
    return _plotly_png(fig, width, height)


def _scorers_chart(sc, width: int, height: int) -> Image.Image:
    sc = sc.sort_values("gols")
    fig = go.Figure(go.Bar(
        x=sc["gols"], y=sc["jogador"], orientation="h", marker_color=RED,
        text=sc["gols"].astype(int).astype(str), textposition="outside", textfont=dict(color=INK, size=14),
    ))
    fig.update_layout(
        template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Arial", color=INK, size=14),
        margin=dict(l=10, r=30, t=10, b=10),
        xaxis=dict(visible=False), yaxis=dict(ticksuffix="  "),
    )
    return _plotly_png(fig, width, height)


def _heatmap_img(points: list[dict], width: int, height: int) -> Image.Image:
    fig = heatmap_figure(points, title="")
    fig.update_layout(margin=dict(l=4, r=4, t=4, b=4))
    return _plotly_png(fig, width, height)


def _paste(canvas: Image.Image, img: Image.Image, x: int, y: int) -> None:
    canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)


def build(db: Database, season_year: Optional[str | int] = 2026, last_n: int = 10,
         competition_id: Optional[int] = None) -> bytes:
    FILT = {"season_year": season_year, "competition_id": competition_id}
    s = team.summary(db, last_n=last_n, **FILT)
    sc = scorers.scorers_table(db, **FILT).head(5)
    ri = ratings.rating_and_index(db, min_matches=3, **FILT)
    frases = insights.momentum(db, window=last_n, season_year=season_year)
    h = loaders.data_health(db)
    mbm = team.match_by_match(db, last_n=last_n, **FILT)

    # jogador em destaque para o mapa de calor: o artilheiro, se ele tiver
    # cobertura de heatmap no recorte; senão, quem tiver mais cobertura.
    comp_filter_sql = ""
    comp_params: list = []
    if season_year is not None:
        comp_filter_sql += " AND c.season_year = ?"
        comp_params.append(str(season_year))
    if competition_id is not None:
        comp_filter_sql += " AND m.competition_id = ?"
        comp_params.append(competition_id)
    hm_rank = db.query_df(
        f"""
        SELECT p.id, p.name, COUNT(*) n FROM player_heatmap ph
        JOIN players p ON p.id = ph.player_id
        JOIN player_match_stats s ON s.match_id=ph.match_id AND s.player_id=ph.player_id
        JOIN matches m ON m.id = ph.match_id
        LEFT JOIN competitions c ON c.id = m.competition_id
        WHERE s.is_santacruz = 1 {comp_filter_sql}
        GROUP BY p.id ORDER BY n DESC
        """,
        comp_params,
    )

    def _heat_points_for(pid: int) -> list[dict]:
        ids = [r[0] for r in db.execute(
            "SELECT match_id FROM player_heatmap WHERE player_id=? ORDER BY match_id DESC LIMIT 5", (pid,)
        ).fetchall()]
        return ids, loaders.heatmap_points_multi(db, pid, ids)

    heat_player = None
    heat_points: list[dict] = []
    heat_n_games = 0
    if not hm_rank.empty:
        top_scorer_id = None
        if not sc.empty:
            row = db.execute("SELECT id FROM players WHERE name = ?", (sc.iloc[0]["jogador"],)).fetchone()
            top_scorer_id = row[0] if row else None
        chosen = hm_rank[hm_rank["id"] == top_scorer_id] if top_scorer_id is not None else hm_rank.iloc[0:0]
        chosen_row = chosen.iloc[0] if not chosen.empty else hm_rank.iloc[0]
        pid = int(chosen_row["id"])
        heat_player = chosen_row["name"]
        ids, heat_points = _heat_points_for(pid)
        heat_n_games = len(ids)
    hp_row = ri[ri["jogador"] == heat_player] if heat_player and not ri.empty else None
    hp_stats = None
    if hp_row is not None and not hp_row.empty:
        hp_stats = hp_row.iloc[0]

    # ------------------------------------------------------------------
    canvas = Image.new("RGB", (W, 2200), WHITE)
    draw = ImageDraw.Draw(canvas)
    y = MARGIN

    # header -----------------------------------------------------------
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo.thumbnail((140, 140))
        canvas.paste(logo, (MARGIN, y), logo)
    tx = MARGIN + 160
    f_brand = F_TITLE(38)
    parts = [("SANTA CRUZ ", INK), ("DATA", RED), (" ANALYTICS", INK)]
    cx = tx
    for txt, color in parts:
        draw.text((cx, y + 6), txt, font=f_brand, fill=color)
        cx += _text_w(draw, txt, f_brand)
    draw.text((tx, y + 56), "Análise de desempenho baseada em dados · Santa Cruz Futebol Clube (PE)",
              font=F_BODY(17), fill=GRAY)
    season_label = f"Temporada {season_year}" if season_year else "Todas as temporadas"
    f_pill = F_BODY(14)
    pw = _text_w(draw, season_label, f_pill)
    draw.rounded_rectangle((W - MARGIN - pw - 28, y + 6, W - MARGIN, y + 36), radius=14, outline=BORDER, width=1)
    draw.text((W - MARGIN - pw - 14, y + 12), season_label, font=f_pill, fill=GRAY)
    y += 150
    draw.line((MARGIN, y, W - MARGIN, y), fill=BORDER, width=2)
    y += 30

    # KPIs ---------------------------------------------------------------
    draw.text((MARGIN, y), f"DESEMPENHO — ÚLTIMOS {s['jogos']} JOGOS", font=F_TITLE(20), fill=INK)
    y += 40
    tiles_row1 = [("Jogos", str(s["jogos"]), False), ("Vitórias", str(s["vitorias"]), True),
                 ("Empates", str(s["empates"]), False), ("Derrotas", str(s["derrotas"]), False)]
    tiles_row2 = [("Gols marcados", str(s["gols_marcados"]), False),
                 ("Gols sofridos", str(s["gols_sofridos"]), False),
                 ("Saldo", f"{s['saldo']:+d}", False),
                 ("Aproveitamento", f"{s['aproveitamento']:.0f}%" if s["aproveitamento"] is not None else "—", True)]
    gap = 20
    tw = (CONTENT_W - 3 * gap) / 4
    th = 110
    for row in (tiles_row1, tiles_row2):
        x = MARGIN
        for label, value, accent in row:
            _kpi_tile(draw, int(x), y, int(tw), th, label, value, accent)
            x += tw + gap
        y += th + gap

    # forma ---------------------------------------------------------------
    y += 10
    draw.text((MARGIN, y), "FORMA RECENTE", font=F_TITLE(18), fill=INK)
    draw.text((MARGIN, y + 26), "sequência do mais antigo (esquerda) ao mais recente (direita)",
              font=F_BODY(13), fill=GRAY)
    y += 60
    bx = MARGIN
    for letter in s["forma"]:
        bx = _badge(draw, bx, y, letter)
    y += 60

    # pontos por partida ---------------------------------------------------
    draw.text((MARGIN, y), "PONTOS CONQUISTADOS POR PARTIDA", font=F_TITLE(18), fill=INK)
    y += 34
    if not mbm.empty:
        chart_h = 260
        chart = _points_chart(mbm, CONTENT_W, chart_h)
        _paste(canvas, chart, MARGIN, y)
        y += chart_h + 20
    else:
        y += 20

    # artilharia -------------------------------------------------------
    draw.text((MARGIN, y), "ARTILHARIA — TEMPORADA", font=F_TITLE(18), fill=INK)
    y += 34
    if not sc.empty:
        chart_h = 210
        chart = _scorers_chart(sc, CONTENT_W, chart_h)
        _paste(canvas, chart, MARGIN, y)
        y += chart_h + 30
    else:
        y += 20

    # mapa de calor + painel do jogador --------------------------------
    draw.text((MARGIN, y), "MAPA DE CALOR", font=F_TITLE(18), fill=INK)
    y += 12
    y += 26
    if heat_points and heat_player:
        hm_w, hm_h = 620, 400
        hm_img = _heatmap_img(heat_points, hm_w, hm_h)
        _paste(canvas, hm_img, MARGIN, y)

        panel_x = MARGIN + hm_w + 30
        panel_w = CONTENT_W - hm_w - 30
        py = y
        draw.text((panel_x, py), heat_player, font=F_TITLE(24), fill=INK)
        py += 34
        draw.text((panel_x, py), f"Agregado dos últimos {heat_n_games} jogo(s) com dado disponível",
                  font=F_BODY(13), fill=GRAY)
        py += 40
        if hp_stats is not None:
            stat_lines = [
                ("Jogos", str(int(hp_stats["jogos"]))),
                ("Minutos", str(int(hp_stats["minutos"]))),
                ("Gols", str(int(hp_stats["gols"]))),
                ("Assistências", str(int(hp_stats["assistencias"]))),
            ]
            if hp_stats["nota_media"] == hp_stats["nota_media"]:
                stat_lines.append(("Nota Sofascore", f"{hp_stats['nota_media']:.2f}"))
            for label, val in stat_lines:
                draw.text((panel_x, py), label.upper(), font=F_BODY(12), fill=GRAY)
                draw.text((panel_x, py + 16), val, font=F_TITLE(22), fill=INK)
                py += 52
        y += hm_h + 30
    else:
        draw.text((MARGIN, y), "Dados de localização de eventos não disponíveis nesta fonte para o recorte atual.",
                  font=F_BODY(14), fill=GRAY)
        y += 60

    # insights -----------------------------------------------------------
    if frases:
        draw.text((MARGIN, y), "ANÁLISE DO MOMENTO", font=F_TITLE(18), fill=INK)
        y += 34
        for frase in frases[:4]:
            draw.ellipse((MARGIN, y + 8, MARGIN + 8, y + 16), fill=RED)
            # quebra de linha simples para frases longas
            max_w = CONTENT_W - 26
            words = frase.split()
            line = ""
            ly = y
            for w_ in words:
                trial = (line + " " + w_).strip()
                if _text_w(draw, trial, F_BODY(16)) > max_w and line:
                    draw.text((MARGIN + 22, ly), line, font=F_BODY(16), fill=INK)
                    ly += 24
                    line = w_
                else:
                    line = trial
            if line:
                draw.text((MARGIN + 22, ly), line, font=F_BODY(16), fill=INK)
                ly += 24
            y = ly + 12
        y += 10

    # rodapé ---------------------------------------------------------------
    y += 10
    draw.line((MARGIN, y, W - MARGIN, y), fill=BORDER, width=2)
    y += 18
    draw.text((MARGIN, y), "SANTA CRUZ DATA ANALYTICS", font=F_TITLE(15), fill=RED)
    y += 24
    atualizado = h.get("last_collection") or "—"
    draw.text((MARGIN, y), f"Fonte: Sofascore (dados públicos, API não-oficial) · Período: {season_year or 'todas as temporadas'} "
                          f"· Atualizado em {atualizado}", font=F_BODY(12), fill=GRAY)
    y += 30

    canvas = canvas.crop((0, 0, W, y + MARGIN))
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()
