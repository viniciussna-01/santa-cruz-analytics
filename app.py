"""⚽ SANTA CRUZ DATA ANALYTICS — ponto de entrada (navegação multipágina).

Executar:  streamlit run app.py
Pré-requisito: rodar a coleta ao menos uma vez (python -m src.collectors.run
ou o botão "Atualizar dados" na barra lateral de qualquer página).

Cada página vive em views/*.py e é auto-contida (importa o que precisa de
src/analytics e src/dashboard). Este arquivo só declara a navegação.
"""
import streamlit as st

st.set_page_config(page_title="Santa Cruz Data Analytics", page_icon="⚽", layout="wide")

pg = st.navigation(
    {
        "Visão geral": [
            st.Page("views/home.py", title="Home", icon="🏠", default=True),
        ],
        "Desempenho": [
            st.Page("views/desempenho.py", title="Desempenho", icon="📈"),
            st.Page("views/tatica.py", title="Análise tática", icon="🧭"),
        ],
        "Jogadores": [
            st.Page("views/jogadores.py", title="Ranking", icon="👥"),
            st.Page("views/scouting.py", title="Scouting", icon="🔎"),
            st.Page("views/comparar.py", title="Comparar jogadores", icon="⚖️"),
        ],
        "Jogo a jogo": [
            st.Page("views/artilharia.py", title="Artilharia", icon="🎯"),
            st.Page("views/mapa_calor.py", title="Mapa de calor", icon="🔥"),
            st.Page("views/partidas.py", title="Partidas", icon="📅"),
        ],
        "Inteligência": [
            st.Page("views/insights.py", title="Insights & LinkedIn", icon="💡"),
            st.Page("views/cenarios.py", title="Cenários", icon="🎲"),
            st.Page("views/qualidade.py", title="Qualidade dos dados", icon="✅"),
        ],
    }
)
pg.run()
