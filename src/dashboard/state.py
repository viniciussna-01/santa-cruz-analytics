"""Estado compartilhado entre as páginas: conexão com o banco e filtros globais.

Streamlit multipágina roda um script novo a cada navegação, mas `st.session_state`
persiste durante a sessão — por isso os filtros (temporada/competição/janela)
ficam guardados lá e cada página só precisa chamar `render_global_filters()`.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from src import config
from src.analytics import loaders
from src.database import Database


@st.cache_resource
def get_database() -> Database:
    return Database(check_same_thread=False)


def run_update(pages: int) -> dict:
    from src.collectors.collector import Collector

    return Collector(db=get_database()).run(max_pages=pages)


def run_update_safe(pages: int) -> tuple[Optional[dict], Optional[str]]:
    """Roda a coleta sem deixar uma falha de rede/API derrubar a página.

    Retorna (resultado, None) em sucesso, ou (None, mensagem_amigável) se a
    fonte estiver indisponível — nunca deixa a exceção subir para o Streamlit.
    """
    from src.api import SofascoreError

    try:
        return run_update(pages), None
    except SofascoreError as exc:
        return None, (
            "Não consegui falar com o Sofascore agora (fonte indisponível ou bloqueando "
            f"as requisições). Os dados já coletados continuam disponíveis. Detalhe técnico: {exc}"
        )
    except Exception as exc:  # noqa: BLE001 — nunca quebrar o dashboard por causa da coleta
        return None, f"Falha inesperada na coleta: {exc}"


def _competitions_df(db: Database) -> pd.DataFrame:
    return db.query_df(
        "SELECT DISTINCT c.id, c.name, c.season_year "
        "FROM competitions c JOIN matches m ON m.competition_id=c.id "
        "WHERE m.status_type='finished' ORDER BY c.season_year DESC, c.name"
    )


def render_global_filters(db: Database) -> dict:
    """Desenha temporada / competição / janela na sidebar e devolve o filtro ativo.

    Chame no topo de cada página. Os widgets usam `key=` fixo para que o valor
    persista ao navegar entre páginas.
    """
    with st.sidebar:
        st.markdown("#### Filtros")
        comp_df = _competitions_df(db)
        seasons = sorted(comp_df["season_year"].dropna().unique(), reverse=True) if not comp_df.empty else []
        default_season = str(config.SEASON_YEAR) if str(config.SEASON_YEAR) in seasons else (seasons[0] if seasons else None)

        season_sel = st.selectbox(
            "Temporada", options=["Todas"] + list(seasons), key="flt_season",
            index=(1 + list(seasons).index(default_season)) if default_season and "flt_season" not in st.session_state else 0,
        )
        season_year = None if season_sel == "Todas" else season_sel

        comp_options = comp_df if season_year is None else comp_df[comp_df["season_year"] == season_year]
        comp_map = {"Todas as competições": None}
        for _, r in comp_options.iterrows():
            comp_map[f"{r['name']} ({r['season_year']})"] = int(r["id"])
        comp_label = st.selectbox("Competição", options=list(comp_map.keys()), key="flt_competition")
        competition_id = comp_map.get(comp_label)

        window = st.radio("Janela de jogos", [5, 10, 15, "Todos"], horizontal=True, index=1, key="flt_window")
        last_n = None if window == "Todos" else int(window)

        st.divider()
        _render_update_box(db)
        st.divider()
        _render_health_caption(db)

    return {"season_year": season_year, "competition_id": competition_id, "last_n": last_n,
            "season_label": season_sel, "competition_label": comp_label}


def _render_update_box(db: Database) -> None:
    pages = st.number_input("Páginas de histórico p/ coletar", 1, 15, config.COLLECT_MAX_PAGES, key="flt_pages")
    if st.button("🔄 Atualizar dados", use_container_width=True, type="primary"):
        with st.spinner("Coletando do Sofascore..."):
            res, err = run_update_safe(int(pages))
        if err:
            st.error(f"⚠️ {err}")
        else:
            st.success(f"Coleta ok: {res['processed']} processadas, {res['skipped']} já atualizadas, "
                       f"{res['failed']} com erro.")
            st.cache_data.clear()
            st.rerun()

    if "did_autoupdate" not in st.session_state:
        st.session_state.did_autoupdate = False
    auto = st.checkbox("Atualizar ao iniciar o app", value=False, key="flt_autoupdate",
                       help="Roda a coleta automaticamente na primeira abertura da sessão.")
    if auto and not st.session_state.did_autoupdate:
        st.session_state.did_autoupdate = True
        with st.spinner("Atualização automática..."):
            _, err = run_update_safe(int(pages))
        if err:
            st.warning(f"Atualização automática não concluída: {err}")
        else:
            st.cache_data.clear()
            st.rerun()


def _render_health_caption(db: Database) -> None:
    h = loaders.data_health(db)
    st.caption(
        f"Partidas finalizadas: **{h['matches_finished']}**  \n"
        f"Com estatística de jogador: **{h['matches_with_player_stats']}**  \n"
        f"Com mapa de calor: **{h['matches_with_heatmap']}**  \n"
        f"Última coleta (UTC): **{h['last_collection'] or '—'}**"
    )
    st.caption("Fonte: Sofascore (dados públicos). Uso educacional.")


def require_data(db: Database) -> bool:
    """Mostra aviso e devolve False se o banco ainda está vazio."""
    h = loaders.data_health(db)
    if h["matches_finished"] > 0:
        return True
    st.warning(
        "Banco vazio. Rode a coleta primeiro:\n\n"
        "```bash\npython -m src.collectors.run\n```\n\n"
        "ou clique em **🔄 Atualizar dados** na barra lateral."
    )
    return False
