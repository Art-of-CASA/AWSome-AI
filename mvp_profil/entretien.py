"""Entretien conversationnel (oral ou écrit) : l'IA pose les questions de contexte et coche les critères au fil de l'eau.

Pour que la conversation soit fluide, l'utilisateur n'attend qu'UN appel court par tour : la RÉPLIQUE
(reprise brève + question suivante, ou répétition si on le lui demande). Le reste se fait EN ARRIÈRE-PLAN
pendant qu'il répond : le CLASSIFICATEUR range ses paroles dans les critères (liste fermée, citation exacte,
confiance), puis le CRITIQUE vérifie ; un critère n'est coché ✅ qu'après son accord (seuil 80 %).
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
                    evaluer, precontrole)
from criteres import CRITERES, describe

# Critères de contexte couverts par la conversation (les autres restent en QCM, quiz et mises en situation).
CRITERES_CONVERSATION = ["A3", "A2", "A9", "A10", "A1", "A4", "A5", "A6", "A12", "A8", "A7", "B3", "C2", "D3", "D5", "D6"]
MAX_TOURS = 10
OUVERTURE = ("Bonjour ! Je vais vous poser quelques questions pour mieux vous connaître ; répondez librement, "
             "comme dans une conversation. Pour commencer : à quoi servira l'argent que vous voulez placer, "
             "et dans combien d'années devrez-vous en récupérer la majeure partie ?")


class Replique(BaseModel):
    message: str          # ce que l'IA dit à voix haute : courte reprise + UNE question (ou conclusion)
    termine: bool


SYSTEM_REPLIQUE = """Tu es la voix d'un court entretien oral, en français, pour établir le profil d'un investisseur (simulation éducative, aucun conseil financier).
Ta réplique sera lue à voix haute : une ou deux phrases courtes, naturelles, sans liste ni jargon ni symbole.
- Reprends en quelques mots ce que l'utilisateur vient de dire, puis pose UNE seule question simple sur un ou deux sujets
  encore à couvrir. L'ordre fourni est calculé par le code : respecte cette priorité, sauf si la conversation y a déjà répondu.
- Ordre : projet/horizon, retraits du capital et revenu nécessaire, réserve et dettes, capacité/risque, contraintes, préférences.
  Groupe seulement deux sujets naturellement liés (objectif + horizon, expérience + produits, thèmes + refus).
  Pose séparément réserve de sécurité et part de l'épargne : leurs dénominateurs diffèrent. Pose séparément retrait de
  capital et besoin de revenu : l'absence de retrait ne dit rien sur les dividendes/intérêts nécessaires pour vivre.
- Pour une information numérique, donne le référent : part du placement ENTIER dans l'épargne, mois de dépenses couverts
  SANS toucher au placement. Une réponse courte et précise est préférable à plusieurs questions ambiguës.
- Un simple oui/non à deux sujets ne les résout pas automatiquement. Précise uniquement le sujet resté sans réponse.
- Ne redemande jamais ce que l'utilisateur a déjà dit dans la conversation, même si le sujet figure encore dans la liste.
- S'il y a des sujets « à reformuler » : l'utilisateur en a parlé, mais pas assez clairement. Commence par eux, UNE fois,
  avec une formulation différente de la précédente et un exemple concret (montant, durée, choix entre deux options).
  Si une PISTE est indiquée (ce que l'outil a cru comprendre), demande simplement de la confirmer, en une question courte et
  naturelle qui reprend les mots de l'utilisateur : « Si je comprends bien, votre fils est encore à votre charge ? ». Ne lis
  jamais la piste telle quelle : ce sont des codes internes (1_2, moins_3_ans…), à ne jamais prononcer.
- Si l'utilisateur demande de répéter, n'a pas compris ou dit « pardon ? », répète ta dernière question en la reformulant plus simplement.
- Si sa réponse est floue, reformule avec un exemple concret (des montants, une durée).
- S'il pose une question hors sujet ou demande un conseil, réponds en une phrase que tu ne donnes pas de conseil, puis reviens à l'entretien.
termine = true seulement quand tous les sujets à couvrir ont été abordés ; message annonce alors qu'il reste quelques questions à choix."""


def replique(backend: Backend, echanges: list[tuple[str, str]], restants: list[str],
             a_reformuler: list[str] = (), pistes: dict | None = None) -> Replique:
    """pistes : {critère: (valeurs, citation)} déjà entrevues pour les sujets à reformuler -> l'IA demande confirmation."""
    """Appel court et rapide : uniquement ce que l'IA va dire. Le classement se fait à part, en arrière-plan."""
    conv = "\n".join(f"IA : {q}\nUtilisateur : {r}" for q, r in echanges)
    sujets = "\n".join(f"{i + 1}. {CRITERES[c]['nom']} — {CRITERES[c]['relance']}" for i, c in enumerate(restants)) or "(aucun)"
    prompt = f"Sujets encore à couvrir, par ordre d'utilité (formulations de référence, à adapter naturellement) :\n{sujets}\n\nConversation :\n{conv}"
    if a_reformuler:
        prompt = ("Sujets à reformuler (abordés, mais pas assez clairement) :\n"
                  + "\n".join(f"- {CRITERES[c]['nom']}" + (f" (piste : {', '.join(pistes[c][0])}, d'après « {pistes[c][1]} »)"
                                                            if pistes and c in pistes else "") for c in a_reformuler)
                  + "\n\n" + prompt)
    return _ask(backend, SYSTEM_REPLIQUE, prompt, Replique)


def analyser(backend: Backend, echanges, a_couvrir: list[str], seuil: float | dict, facultatifs=()) -> dict:
    """En arrière-plan : le classificateur range la conversation dans les critères, puis le critique vérifie.

    facultatifs : autres critères encore inconnus (hors conversation) ; renvoyés seulement s'ils sont validés.
    """
    if not a_couvrir and not facultatifs:
        return {}
    classif = classifier(backend, echanges, a_couvrir, facultatifs=facultatifs)
    voulus = set(a_couvrir) | set(facultatifs)
    res = verifier(backend, echanges, [p for p in classif.propositions if p.critere_id in voulus and
                                       (p.critere_id in a_couvrir or p.valeurs)], seuil)
    return {c: r for c, r in res.items() if c in a_couvrir or r.valide}


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
