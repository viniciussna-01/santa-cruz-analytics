"""Camada de análise — funções puras sobre o banco (retornam dicts/DataFrames)."""
from . import insights, loaders, players, ratings, scorers, team

__all__ = ["loaders", "team", "players", "scorers", "ratings", "insights"]
