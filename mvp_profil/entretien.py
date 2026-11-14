"""Entretien conversationnel (oral ou écrit) : l'IA pose les questions de contexte et coche les critères au fil de l'eau.

Pour que la conversation soit fluide, l'utilisateur n'attend qu'UN appel court par tour : la RÉPLIQUE
(reprise brève + question suivante, ou répétition si on le lui demande). Le reste se fait EN ARRIÈRE-PLAN
pendant qu'il répond : le CLASSIFICATEUR range ses paroles dans les critères (liste fermée, citation exacte,
confiance), puis le CRITIQUE vérifie ; un critère n'est coché ✅ qu'après son accord (seuil 80 %).
Sinon il reste à couvrir et l'IA y revient.

Voix (services AWS) :
  - Amazon Transcribe en streaming (fr-CA) : la parole de l'utilisateur devient du texte.
  - Amazon Polly, voix neuronale « Gabrielle » (fr-CA) : l'IA lit sa question à voix haute.
Le micro du navigateur n'est disponible qu'en HTTPS (ou sur localhost) ; la saisie au clavier marche partout.
"""
from __future__ import annotations

import asyncio
import io
import wave

from pydantic import BaseModel

from agents import (REGION, AgentError, Backend, Classification, Proposition, _ask, classifier, critiquer,
                    evaluer, precontrole)
from criteres import CRITERES, describe

# Critères de contexte couverts par la conversation (les autres restent en QCM, quiz et mises en situation).
CRITERES_CONVERSATION = ["A3", "A2", "A9", "A10", "A4", "A5", "A6", "A12", "A8", "A7", "B3", "C2", "D3", "D5", "D6"]
MAX_TOURS = 10
OUVERTURE = ("Bonjour ! Je vais vous poser quelques questions pour mieux vous connaître ; répondez librement, "
             "comme dans une conversation. Pour commencer : à quoi servira l'argent que vous voulez placer, "
             "et dans combien de temps pensez-vous en avoir besoin ?")


class Replique(BaseModel):
    message: str          # ce que l'IA dit à voix haute : courte reprise + UNE question (ou conclusion)
    termine: bool


SYSTEM_REPLIQUE = """Tu es la voix d'un court entretien oral, en français, pour établir le profil d'un investisseur (simulation éducative, aucun conseil financier).
Ta réplique sera lue à voix haute : une ou deux phrases courtes, naturelles, sans liste ni jargon ni symbole.
- Reprends en quelques mots ce que l'utilisateur vient de dire, puis pose UNE seule question simple sur un ou deux sujets
  encore à couvrir (les plus importants d'abord : objectif, horizon, retraits, épargne, situation).
- Ne redemande jamais ce que l'utilisateur a déjà dit dans la conversation, même si le sujet figure encore dans la liste.
- Si l'utilisateur demande de répéter, n'a pas compris ou dit « pardon ? », répète ta dernière question en la reformulant plus simplement.
- Si sa réponse est floue, reformule avec un exemple concret (des montants, une durée).
- S'il pose une question hors sujet ou demande un conseil, réponds en une phrase que tu ne donnes pas de conseil, puis reviens à l'entretien.
termine = true seulement quand tous les sujets à couvrir ont été abordés ; message annonce alors qu'il reste quelques questions à choix."""


def replique(backend: Backend, echanges: list[tuple[str, str]], restants: list[str]) -> Replique:
    """Appel court et rapide : uniquement ce que l'IA va dire. Le classement se fait à part, en arrière-plan."""
    conv = "\n".join(f"IA : {q}\nUtilisateur : {r}" for q, r in echanges)
    sujets = "\n".join(f"- {CRITERES[c]['nom']}" for c in restants) or "(aucun)"
    return _ask(backend, SYSTEM_REPLIQUE, f"Sujets encore à couvrir :\n{sujets}\n\nConversation :\n{conv}", Replique)


def analyser(backend: Backend, echanges, a_couvrir: list[str], seuil: float) -> dict:
    """En arrière-plan : le classificateur range la conversation dans les critères, puis le critique vérifie."""
    if not a_couvrir:
        return {}
    classif = classifier(backend, echanges, a_couvrir)
    return verifier(backend, echanges, [p for p in classif.propositions if p.critere_id in a_couvrir], seuil)


def verifier(backend: Backend, echanges, propositions: list[Proposition], seuil: float) -> dict:
    """Vérification par le critique (lancée en arrière-plan). Renvoie {critère: Resultat}."""
    props = {p.critere_id: p for p in propositions if p.critere_id in CRITERES}
    resultats, sures = {}, []
    for cid, p in props.items():
        r = precontrole(cid, p, echanges, seuil)
        if r is None:
            sures.append(cid)
        else:
            resultats[cid] = r
    if sures:
        crit = critiquer(backend, echanges, sures, Classification(propositions=[props[c] for c in sures]))
        avis = {a.critere_id: a for a in crit.avis}
        for cid in sures:
            resultats[cid] = evaluer(cid, props[cid], avis.get(cid), echanges, seuil)
    return resultats


# ---------- Voix ----------
def synthese_vocale(texte: str) -> bytes:
    """Amazon Polly, voix neuronale Gabrielle (français canadien). Renvoie un MP3."""
    import boto3
    r = boto3.client("polly", region_name=REGION).synthesize_speech(
        Text=texte, VoiceId="Gabrielle", Engine="neural", LanguageCode="fr-CA", OutputFormat="mp3")
    return r["AudioStream"].read()


def pcm_depuis_wav(donnees: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(donnees)) as w:
        if w.getsampwidth() != 2:
            raise AgentError("Format audio inattendu (16 bits attendus).")
        pcm, taux, canaux = w.readframes(w.getnframes()), w.getframerate(), w.getnchannels()
    if canaux == 2:  # stéréo -> mono (on garde le canal gauche)
        pcm = b"".join(pcm[i:i + 2] for i in range(0, len(pcm), 4))
    return pcm, taux


async def _transcrire(pcm: bytes, taux: int, langue: str) -> str:
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler

    client = TranscribeStreamingClient(region=REGION)
    flux = await client.start_stream_transcription(language_code=langue, media_sample_rate_hz=taux, media_encoding="pcm")

    class Collecteur(TranscriptResultStreamHandler):
        def __init__(self, sortie):
            super().__init__(sortie)
            self.morceaux: list[str] = []

        async def handle_transcript_event(self, evenement):
            for res in evenement.transcript.results:
                if not res.is_partial and res.alternatives:
                    self.morceaux.append(res.alternatives[0].transcript)

    collecteur = Collecteur(flux.output_stream)

    async def envoyer():
        pas = taux * 2 // 4  # morceaux de 0,25 s (16 bits = 2 octets par échantillon)
        for i in range(0, len(pcm), pas):
            await flux.input_stream.send_audio_event(audio_chunk=pcm[i:i + pas])
        await flux.input_stream.end_stream()

    await asyncio.gather(envoyer(), collecteur.handle_events())
    return " ".join(collecteur.morceaux).strip()


def transcrire(donnees_wav: bytes, langue: str = "fr-CA") -> str:
    """Amazon Transcribe en streaming : WAV 16 bits -> texte."""
    pcm, taux = pcm_depuis_wav(donnees_wav)
    try:
        return asyncio.run(_transcrire(pcm, taux, langue))
    except Exception as e:  # noqa: BLE001
        raise AgentError(f"Transcription impossible : {e}") from e
