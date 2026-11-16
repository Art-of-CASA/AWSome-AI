"""Enveloppe Python du composant de conversation vocale mains libres (composant_voix/index.html)."""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_composant = components.declare_component("conversation_vocale", path=str(Path(__file__).parent / "composant_voix"))


def conversation_vocale(*, audio_b64: str, n: int, ack: int, fin: bool, voix: bool, key: str,
                         question_id: str, session_id: str, question_text: str = "",
                         veille: bool = False, attente: bool = False, termine: bool = False,
                         echec_transcription: int = 0, attendre_reprise_explicite: bool = False):
    """Affiche le composant puis renvoie audio, fin ou demande de nouvelle synthèse.

    Chaque message porte question_id, playback_id, session_id et instance_id :
    le serveur peut refuser un audio destiné à une ancienne question avant transcription.

    audio_b64 : MP3 de la dernière réplique de l'IA ; n : son numéro (le composant la joue si elle est nouvelle) ;
    ack déduplique les événements ; une écoute exige d'abord la fin de la lecture courante.
    veille/attente désactivent le micro sans retirer le composant ; termine libère ses ressources.
    echec_transcription est un ticket croissant : dans les étapes qui demandent une reprise explicite, le navigateur
    affiche un bouton au lieu de rouvrir le micro automatiquement.
    """
    return _composant(audio=audio_b64, n=n, playback_id=n, ack=ack, fin=fin, voix=voix, veille=veille,
                      attente=attente, termine=termine, question_id=question_id, session_id=session_id,
                      question_text=question_text, echec_transcription=echec_transcription,
                      attendre_reprise_explicite=attendre_reprise_explicite, key=key, default=None)
