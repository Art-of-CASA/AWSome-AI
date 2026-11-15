"""Enveloppe Python du composant de conversation vocale mains libres (composant_voix/index.html)."""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_composant = components.declare_component("conversation_vocale", path=str(Path(__file__).parent / "composant_voix"))


def conversation_vocale(*, audio_b64: str, n: int, ack: int, fin: bool, voix: bool, key: str, veille: bool = False):
    """Affiche le composant et renvoie le dernier message du navigateur :
    {"kind": "audio", "n": ..., "wav": base64} quand l'utilisateur a fini une phrase,
    {"kind": "termine", "n": ...} quand la réplique de conclusion a fini d'être lue.

    audio_b64 : MP3 de la dernière réplique de l'IA ; n : son numéro (le composant la joue si elle est nouvelle) ;
    ack : numéro du dernier énoncé traité par Python (le composant réécoute si rien de nouveau n'est à dire).
    veille : micro coupé sans fermer le composant (pendant les QCM) ; il reprend dès que veille repasse à False.
    """
    return _composant(audio=audio_b64, n=n, ack=ack, fin=fin, voix=voix, veille=veille, key=key, default=None)
