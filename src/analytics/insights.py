"""Análise automática ("Análise do momento") — baseada em regras estatísticas.

Sem IA. Cada frase é derivada diretamente de números do banco. Se faltam
dados para uma frase, ela simplesmente não é gerada.
"""
from __future__ import annotations

from typing import Optional

from src.analytics import loaders, ratings, scorers, team
from src.database import Database


def momentum(
    db: Database,
    window: int = 5,
    season_year: Optional[str | int] = None,
) -> list[str]:
    kw = {"season_year": season_year}
    frases: list[str] = []

    s = team.summary(db, last_n=window, **kw)
    if s["jogos"] == 0:
        return ["Ainda não há partidas finalizadas no recorte selecionado para gerar análise."]

    n = s["jogos"]
    frases.append(
        f"Nos últimos {n} jogos: {s['vitorias']}V {s['empates']}E {s['derrotas']}D "
        f"({s['aproveitamento']:.0f}% de aproveitamento)."
        if s["aproveitamento"] is not None
        else f"Nos últimos {n} jogos: {s['vitorias']}V {s['empates']}E {s['derrotas']}D."
    )
    frases.append(
        f"O ataque marcou {s['gols_marcados']} gols (média de {s['media_gols']:.2f} por jogo) "
        f"e a defesa sofreu {s['gols_sofridos']} (média de {s['media_gols_sofridos']:.2f})."
    )
    if s["forma"]:
        frases.append("Sequência (antigo → recente): " + " ".join(s["forma"]) + ".")
    if s["clean_sheets"]:
        frases.append(f"Foram {s['clean_sheets']} jogo(s) sem sofrer gols nesse período.")

    # tendência: últimos 5 vs 5 anteriores
    ev = team.evolution(db, windows=(window, window * 2), **kw)
    if len(ev) == 2 and ev.iloc[0]["jogos"] == window and ev.iloc[1]["jogos"] >= window:
        apr_recente = ev.iloc[0]["aproveitamento"]
        apr_amplo = ev.iloc[1]["aproveitamento"]
        if apr_recente is not None and apr_amplo is not None:
            if apr_recente > apr_amplo + 8:
                frases.append(f"Tendência de melhora: {apr_recente:.0f}% nos últimos {window} contra "
                              f"{apr_amplo:.0f}% nos últimos {window*2}.")
            elif apr_recente < apr_amplo - 8:
                frases.append(f"Tendência de queda: {apr_recente:.0f}% nos últimos {window} contra "
                              f"{apr_amplo:.0f}% nos últimos {window*2}.")

    # mandante x visitante
    ha = team.home_away_split(db, **kw)
    hm, aw = ha["mandante"], ha["visitante"]
    if hm["jogos"] and aw["jogos"] and hm["aproveitamento"] is not None and aw["aproveitamento"] is not None:
        if abs(hm["aproveitamento"] - aw["aproveitamento"]) >= 15:
            melhor = "como mandante" if hm["aproveitamento"] > aw["aproveitamento"] else "como visitante"
            frases.append(
                f"O time rende bem mais {melhor} "
                f"({hm['aproveitamento']:.0f}% em casa x {aw['aproveitamento']:.0f}% fora)."
            )

    # artilharia / garçom
    gi = scorers.goal_involvement_summary(db, last_n_matches=None, season_year=season_year)
    if gi["artilheiro"] and gi["artilheiro"]["gols"] > 0:
        frases.append(f"{gi['artilheiro']['jogador']} lidera a artilharia com {gi['artilheiro']['gols']} gols.")
    if gi["garcom"] and gi["garcom"]["assistencias"] > 0:
        frases.append(f"{gi['garcom']['jogador']} lidera as assistências ({gi['garcom']['assistencias']}).")

    # melhor nota média no período (com min. de jogos)
    ri = ratings.rating_and_index(db, season_year=season_year, min_matches=3)
    rated = ri[ri["nota_media"].notna()] if not ri.empty else ri
    if not rated.empty:
        best = rated.sort_values("nota_media", ascending=False).iloc[0]
        frases.append(
            f"{best['jogador']} tem a melhor nota média Sofascore no período ({best['nota_media']:.2f}, "
            f"{int(best['jogos'])} jogos)."
        )
        top_ips = ri[ri["ips"].notna()].sort_values("ips", ascending=False)
        if not top_ips.empty and top_ips.iloc[0]["jogador"] != best["jogador"]:
            ti = top_ips.iloc[0]
            frases.append(f"Pelo Índice de Performance Santa Cruz, o destaque é {ti['jogador']} (IPS {ti['ips']:.2f}).")

    return frases


def data_notes(db: Database) -> list[str]:
    """Avisos de transparência sobre cobertura de dados."""
    h = loaders.data_health(db)
    notes = []
    if h["matches_finished"]:
        notes.append(
            f"{h['matches_with_player_stats']}/{h['matches_finished']} partidas finalizadas têm "
            f"estatísticas individuais (nota Sofascore); "
            f"{h['matches_with_heatmap']}/{h['matches_finished']} têm mapa de calor."
        )
    faltam = h["matches_finished"] - h["matches_with_player_stats"]
    if faltam > 0:
        notes.append(
            f"{faltam} partida(s) sem estatística individual na fonte "
            "(competições/edições que o Sofascore não detalha) — entram nas contas de "
            "resultado/gols, mas não nas médias de jogador."
        )
    if h["last_collection"]:
        notes.append(f"Última coleta: {h['last_collection']} (UTC).")
    return notes
