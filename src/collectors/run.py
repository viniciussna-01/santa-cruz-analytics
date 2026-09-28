"""CLI da coleta.

Uso:
    python -m src.collectors.run                # coleta incremental
    python -m src.collectors.run --pages 5      # busca mais histórico
    python -m src.collectors.run --force        # re-baixa detalhes de tudo
"""
from __future__ import annotations

import argparse

from src import config
from src.collectors.collector import run_collection
from src.utils.logging_utils import get_logger

log = get_logger("santacruz.collector")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coletor Santa Cruz Analytics (Sofascore)")
    parser.add_argument("--pages", type=int, default=config.COLLECT_MAX_PAGES,
                        help="páginas de histórico a buscar (30 jogos/página)")
    parser.add_argument("--force", action="store_true",
                        help="re-baixar detalhes mesmo de partidas já completas")
    args = parser.parse_args()

    result = run_collection(max_pages=args.pages, force=args.force)
    log.info("Resultado: %s", result)


if __name__ == "__main__":
    main()
