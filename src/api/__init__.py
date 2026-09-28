"""Camada de acesso a fontes de dados."""
from .sofascore import SofascoreClient, SofascoreError

__all__ = ["SofascoreClient", "SofascoreError"]
