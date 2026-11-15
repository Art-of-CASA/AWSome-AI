"""Entretien conversationnel (oral ou écrit) : l'IA pose les questions de contexte et coche les critères au fil de l'eau.

Le choix de la question appartient au code ; aucune génération libre de question n'est nécessaire.
En arrière-plan, le CLASSIFICATEUR range les paroles dans les critères (liste fermée, citation exacte,
confiance), puis le CRITIQUE vérifie. Leur désaccord dispose de deux tours internes pour être résolu sans
faire répéter l'utilisateur ; une clarification exige un manque ou une ambiguïté explicitement identifié.
Un sujet abordé mais pas assez clair est reformulé UNE seule fois (seuil abaissé à 65 %) ; ensuite on retient
une réponse vérifiée avec accord (plancher 50 %) ; un désaccord reste incertain. Un sujet jamais abordé reste à couvrir.

Voix (services AWS) :
  - Amazon Transcribe en streaming (fr-CA) : la parole de l'utilisateur devient du texte.
  - Amazon Polly, voix neuronale « Gabrielle » (fr-CA) : l'IA lit sa question à voix haute.
Le micro du navigateur n'est disponible qu'en HTTPS (ou sur localhost) ; la saisie au clavier marche partout.
"""
from __future__ import annotations

import asyncio
import io
import re
import wave

from pydantic import BaseModel

from agents import (REGION, AgentError, Backend, Classification, Proposition, _ask, classifier, critiquer,
                    evaluer, precontrole, debattre)
from criteres import CRITERES, describe

MAX_AUDIO_S = 30
MAX_WAV_OCTETS = MAX_AUDIO_S * 48_000 * 2 * 2 + 4096
DELAI_TRANSCRIPTION_S = 40

# Critères de contexte couverts par la conversation (les autres restent en QCM, quiz et mises en situation).
CRITERES_CONVERSATION = ["A3", "A2", "A9", "A10", "A1", "A4", "A5", "A6", "A12", "A8", "A7", "B3", "C2", "D3", "D5", "D6"]
MAX_TOURS = 10
OUVERTURE = ("Bonjour ! Je vais vous poser quelques questions pour mieux vous connaître ; répondez librement, "
             "comme dans une conversation. Parlons de cette somme précise : à quoi servira l'argent que vous voulez placer, "
             "et dans combien d'années devrez-vous en récupérer la majeure partie ?")


def analyser(backend: Backend, echanges, a_couvrir: list[str], seuil: float | dict, facultatifs=()) -> dict:
    """En arrière-plan : le classificateur range la conversation dans les critères, puis le critique vérifie.

    facultatifs : autres critères encore inconnus (hors conversation) ; renvoyés seulement s'ils sont validés.
    """
    if not a_couvrir and not facultatifs:
        return {}
    return debattre(backend, echanges, a_couvrir, seuil=seuil, max_tours=2,
                    facultatifs=facultatifs).resultats


def verifier(backend: Backend, echanges, propositions: list[Proposition], seuil: float | dict) -> dict:
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


# ---------- Précisions et question ouverte à la voix ----------
_REPETER = re.compile(r"\b(r[ée]p[ée]t|pardon|redi[rst]|reformul|pas compris|pas entendu|pas saisi)\w*")


def demande_correction(texte: str) -> bool:
    """Déclenche une relecture, jamais une modification automatique du profil."""
    return bool(re.search(r"\b(en fait|je me corrige|correction|je voulais dire|finalement|rectifi\w*)\b", texte.lower()))


def demande_repetition(texte: str) -> bool:
    """« Pouvez-vous répéter ? », « pardon ? », « je n'ai pas compris » : réponse courte, sans chiffre, qui demande
    de redire (« pardon, c'est 3 mois » est une vraie réponse)."""
    t = texte.lower().replace("’", "'")
    return len(t.split()) <= 8 and not any(ch.isdigit() for ch in t) and bool(_REPETER.search(t))


class Choix(BaseModel):
    option: int          # numéro de la possibilité choisie (1, 2…), 0 si la réponse ne permet pas de choisir


SYSTEM_CHOIX = """Tu aides un outil de profil d'investisseur (simulation éducative). On a lu à l'utilisateur une question et des
possibilités numérotées ; il a répondu à l'oral (transcription automatique, parfois imparfaite). Renvoie le numéro de la
possibilité qu'il choisit (« la première », « la deuxième », ou une reformulation de son contenu). Renvoie 0 s'il hésite, ne
choisit pas, ou si sa réponse ne correspond à aucune possibilité."""


def choisir_option(backend: Backend, question: str, options: list[str], reponse: str) -> int:
    """Réponse orale -> indice (0, 1…) de la possibilité choisie, ou -1 si on ne peut pas trancher."""
    liste = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(options))
    c = _ask(backend, SYSTEM_CHOIX, f"Question : {question}\nPossibilités :\n{liste}\nRéponse : {reponse}", Choix, 200)
    return c.option - 1 if 1 <= c.option <= len(options) else -1


# ---------- Voix ----------
def synthese_vocale(texte: str) -> bytes:
    """Amazon Polly, voix neuronale Gabrielle (français canadien). Renvoie un MP3."""
    import boto3
    from botocore.config import Config
    try:
        client = boto3.client("polly", region_name=REGION,
                              config=Config(connect_timeout=5, read_timeout=15,
                                            retries={"total_max_attempts": 1, "mode": "standard"}))
        r = client.synthesize_speech(Text=texte, VoiceId="Gabrielle", Engine="neural",
                                     LanguageCode="fr-CA", OutputFormat="mp3")
        with r["AudioStream"] as audio:
            return audio.read()
    except Exception as exc:
        raise AgentError("La lecture vocale est indisponible. Vous pouvez la réessayer.") from exc


def pcm_depuis_wav(donnees: bytes) -> tuple[bytes, int]:
    if not donnees or len(donnees) > MAX_WAV_OCTETS:
        raise AgentError("Enregistrement vide ou trop volumineux (30 secondes maximum).")
    try:
        with wave.open(io.BytesIO(donnees)) as w:
            taux, canaux = w.getframerate(), w.getnchannels()
            if w.getsampwidth() != 2 or canaux not in (1, 2) or taux not in (8000, 16000, 22050, 24000, 32000, 44100, 48000):
                raise AgentError("Format audio inattendu (WAV PCM 16 bits, mono ou stéréo attendu).")
            if w.getnframes() > taux * MAX_AUDIO_S:
                raise AgentError("Réponse trop longue (30 secondes maximum).")
            pcm = w.readframes(w.getnframes())
            if len(pcm) != w.getnframes() * canaux * 2:
                raise AgentError("Enregistrement incomplet. Veuillez réessayer.")
    except (wave.Error, EOFError, OSError, ValueError) as exc:
        raise AgentError("Enregistrement audio invalide. Veuillez réessayer.") from exc
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
    try:
        pcm, taux = pcm_depuis_wav(donnees_wav)
        async def bornee():
            return await asyncio.wait_for(_transcrire(pcm, taux, langue), timeout=DELAI_TRANSCRIPTION_S)
        return asyncio.run(bornee())
    except AgentError:
        raise
    except TimeoutError as exc:
        raise AgentError("La transcription a dépassé son délai. Vous pouvez réessayer.") from exc
    except Exception as e:  # noqa: BLE001
        raise AgentError(f"Transcription impossible : {e}") from e
