"""Composant local du replay continu : aucun service distant ni arrêt imposé."""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_replay = components.declare_component("replay_marche", path=str(Path(__file__).parent / "composant_replay"))


def replay_marche(*, session_id: str, values: list[float], month_positions: list[float], state: dict,
                  ack: int, finished: bool = False, key: str):
    """Anime dans le navigateur ; le serveur valide chaque journal cumulatif reçu.

    values ne contient que la période de mise en situation, jamais la suite révélée à la fin.
    Le numéro de session et l'accusé de réception protègent contre les anciens événements.
    """
    return _replay(session_id=session_id, values=values, month_positions=month_positions, state=state,
                   ack=ack, finished=finished, duration_ms=55000, key=key, default=None)
