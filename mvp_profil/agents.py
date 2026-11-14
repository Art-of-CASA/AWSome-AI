"""Deux agents Claude Haiku 5.5 (via Amazon Bedrock par défaut) qui classent les réponses de l'utilisateur.

- Le CLASSIFICATEUR propose, pour chaque critère, des valeurs de la liste fermée, la citation exacte
  de l'utilisateur qui les justifie et sa confiance (0 à 1).
- Le CRITIQUE vérifie chaque proposition : la citation la soutient-elle vraiment ? Une autre lecture
  est-elle possible ? Il donne son accord ou une objection, sa propre confiance, et une question de
  relance si l'information manque.
- Ils débattent (au plus MAX_TOURS tours) : le classificateur révise en tenant compte des objections.
- Un critère est VALIDÉ seulement si le critique est d'accord ET si les deux confiances >= seuil
  (80 % par défaut). Sinon, on repose une question ciblée à l'utilisateur.

Rapidité : pas de raisonnement étendu (classification simple), réponses courtes, 2 tours au plus, et le
critique n'est appelé que sur les critères où le classificateur est déjà sûr de lui ; un critère incertain
pour le classificateur part directement en question de précision.

Tout ce qui décide (validation, seuil, valeurs autorisées) est du code ; les modèles ne font que classer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic
from pydantic import BaseModel

from criteres import CRITERES, describe

MAX_TOURS = 2
REGION = os.environ.get("AWS_REGION", "us-east-1")
# Même modèle (Claude Haiku 5.5) des deux côtés ; sur Bedrock, il s'appelle par son profil d'inférence.
MODELES = {"bedrock": "us.anthropic.claude-haiku-5-5", "anthropic": "claude-haiku-5-5"}


@dataclass
class Backend:
    """Client Claude + identifiant du modèle. Par défaut : Amazon Bedrock, compte AWS du datathon."""
    client: anthropic.Anthropic | anthropic.AnthropicBedrock
    model: str
    nom: str


def backend_bedrock(region: str = REGION) -> Backend:
    # Identifiants AWS lus par la chaîne standard (variables AWS_*, ~/.aws, rôle de l'instance si hébergé sur AWS).
    return Backend(anthropic.AnthropicBedrock(aws_region=region), MODELES["bedrock"], f"Amazon Bedrock ({region})")


def backend_anthropic(api_key: str) -> Backend:
    return Backend(anthropic.Anthropic(api_key=api_key), MODELES["anthropic"], "API Anthropic")


def aws_identifiants_presents() -> bool:
    import boto3
    return boto3.Session().get_credentials() is not None


# ---------- Formats de sortie imposés aux agents (sorties structurées) ----------
class Proposition(BaseModel):
    critere_id: str
    valeurs: list[str]
    citation: str        # mots exacts de l'utilisateur ; vide si rien ne permet de conclure
    confiance: float     # 0 à 1
    justification: str


class Classification(BaseModel):
    propositions: list[Proposition]


class Avis(BaseModel):
    critere_id: str
    accord: bool
    confiance: float     # confiance du critique que la classification finale est la bonne
    objection: str       # vide si accord
    valeurs_suggerees: list[str]


class Critique(BaseModel):
    avis: list[Avis]
    question_relance: str  # question à poser à l'utilisateur si un critère reste incertain ; vide sinon


class AgentError(RuntimeError):
    pass


# ---------- Consignes ----------
SYSTEM_CLASSIFIEUR = """Tu es l'agent CLASSIFICATEUR d'un outil de profil d'investisseur (simulation éducative, aucun conseil financier).
Tu reçois la conversation entre l'outil et l'utilisateur, et une liste de critères avec leurs valeurs autorisées.
Pour CHAQUE critère demandé, renvoie une proposition :
- valeurs : uniquement des valeurs de la liste autorisée, copiées exactement. Liste vide si la réponse ne permet pas de conclure.
- citation : les mots exacts de l'utilisateur qui justifient le choix (copie fidèle, pas de paraphrase). Vide si aucune.
- confiance : entre 0 et 1. Au-dessus de 0,8 seulement si la citation dit clairement la chose. Si tu dois deviner ou extrapoler, reste sous 0,5.
- justification : une phrase courte.
Règles : ne t'appuie que sur ce que l'utilisateur a écrit ; n'invente rien ; une réponse vague ou hors sujet donne une confiance basse.
Si le critique a formulé des objections, réexamine chaque critère : corrige si l'objection est fondée, sinon maintiens et explique pourquoi dans la justification."""

SYSTEM_CRITIQUE = """Tu es l'agent CRITIQUE d'un outil de profil d'investisseur (simulation éducative, aucun conseil financier).
Ton rôle est de contester les classifications trop rapides. Pour CHAQUE proposition du classificateur :
- Vérifie que la citation existe vraiment dans les mots de l'utilisateur et qu'elle soutient la valeur choisie.
- Cherche une autre lecture possible de la réponse ; vérifie que les valeurs sont dans la liste autorisée.
- accord = true seulement si tu es convaincu que la classification correspond à ce que l'utilisateur a dit.
- confiance : entre 0 et 1, ta propre certitude que la classification est correcte. Une réponse vague ne mérite pas plus de 0,6.
- objection : ce qui ne va pas (vide si accord). valeurs_suggerees : ta proposition si tu n'es pas d'accord (sinon liste vide).
Si au moins un critère reste incertain parce que l'utilisateur n'a pas donné l'information, rédige question_relance :
UNE question courte, bienveillante et concrète, en français, qui vise seulement les critères incertains (exemple chiffré ou mise en situation si utile).
Sinon, question_relance est vide."""


def _transcript(echanges: list[tuple[str, str]]) -> str:
    return "\n".join(f"Outil : {q}\nUtilisateur : {r}" for q, r in echanges)


def _ask(backend: Backend, system: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
    import botocore.exceptions as bx
    try:
        resp = backend.client.messages.parse(
            model=backend.model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            thinking={"type": "disabled"},    # classification simple : pas de raisonnement étendu (plus rapide)
            output_config={"effort": "low"},  # accepté avec thinking désactivé sur Haiku 5.5 (effort <= high)
        )
    except (bx.NoCredentialsError, bx.PartialCredentialsError) as e:
        raise AgentError("Aucun identifiant AWS trouvé sur cette machine.") from e
    except bx.BotoCoreError as e:
        raise AgentError(f"Erreur AWS : {e}") from e
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
        raise AgentError(f"Accès refusé par {backend.nom} : identifiants absents, expirés ou sans droit sur le modèle.") from e
    except anthropic.RateLimitError as e:
        raise AgentError("Limite de débit atteinte : réessayez dans quelques secondes.") from e
    except anthropic.APIStatusError as e:
        raise AgentError(f"Erreur de l'API ({e.status_code}) : {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AgentError("Impossible de joindre l'API Anthropic.") from e
    if resp.stop_reason == "refusal":
        raise AgentError("Le modèle a refusé de répondre à cette demande.")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise AgentError("Réponse du modèle incomplète.")
    return resp.parsed_output


def classifier(backend: Backend, echanges, criteres_ids, critique: Critique | None = None,
               precedente: Classification | None = None) -> Classification:
    prompt = (f"Critères à classer :\n{describe(criteres_ids)}\n\n"
              f"Conversation :\n{_transcript(echanges)}")
    if critique and precedente:
        prompt += ("\n\nTa classification précédente :\n" + precedente.model_dump_json(indent=1)
                   + "\n\nObjections du critique :\n" + critique.model_dump_json(indent=1)
                   + "\n\nRévise ta classification.")
    return _ask(backend, SYSTEM_CLASSIFIEUR, prompt, Classification)


def critiquer(backend: Backend, echanges, criteres_ids, classification: Classification) -> Critique:
    prompt = (f"Critères :\n{describe(criteres_ids)}\n\n"
              f"Conversation :\n{_transcript(echanges)}\n\n"
              f"Classification proposée :\n{classification.model_dump_json(indent=1)}")
    return _ask(backend, SYSTEM_CRITIQUE, prompt, Critique)


# ---------- Contrôles déterministes ----------
def _valides(cid: str, valeurs: list[str]) -> list[str]:
    autorisees = CRITERES[cid]["valeurs"]
    vals = [v for v in valeurs if v in autorisees]
    return vals if CRITERES[cid]["multiple"] else vals[:1]


def _citation_presente(citation: str, echanges) -> bool:
    """La citation doit venir des mots de l'utilisateur (comparaison souple : casse et espaces)."""
    norm = lambda s: " ".join(s.lower().replace("’", "'").split())  # noqa: E731
    texte = norm(" ".join(r for _, r in echanges))
    # Une citation peut être coupée par des points de suspension : chaque morceau doit être présent.
    morceaux = [norm(m).strip(" .,;:!?«»\"'") for m in citation.replace("…", "...").split("...")]
    morceaux = [m for m in morceaux if m]
    return bool(morceaux) and all(m in texte for m in morceaux)


@dataclass
class Resultat:
    critere_id: str
    valeurs: list[str]
    citation: str
    confiance: float          # min(confiance classificateur, confiance critique)
    valide: bool
    motif: str                # pourquoi non validé, ou justification


@dataclass
class Debat:
    resultats: dict[str, Resultat]
    tours: list[dict] = field(default_factory=list)   # trace complète, affichée à l'utilisateur
    question_relance: str = ""

    @property
    def non_valides(self) -> list[str]:
        return [c for c, r in self.resultats.items() if not r.valide]


def evaluer(cid, prop: Proposition | None, avis: Avis | None, echanges, seuil: float) -> Resultat:
    if prop is None:
        return Resultat(cid, [], "", 0.0, False, "Aucune proposition du classificateur")
    vals = _valides(cid, prop.valeurs)
    c_cls = max(0.0, min(1.0, prop.confiance))
    c_cri = max(0.0, min(1.0, avis.confiance)) if avis else 0.0
    conf = min(c_cls, c_cri)
    if not vals:
        motif = "Information absente ou valeurs hors liste"
    elif not _citation_presente(prop.citation, echanges):
        motif, conf = "Citation introuvable dans la réponse de l'utilisateur", min(conf, 0.5)
    elif avis is None or not avis.accord:
        motif = f"Désaccord du critique : {avis.objection if avis else 'pas d avis'}"
    elif conf < seuil:
        motif = f"Confiance {conf:.0%} sous le seuil de {seuil:.0%}"
    else:
        return Resultat(cid, vals, prop.citation, conf, True, prop.justification)
    return Resultat(cid, vals, prop.citation, conf, False, motif)


def precontrole(cid, prop: Proposition | None, echanges, seuil: float) -> Resultat | None:
    """Contrôle côté classificateur, avant d'appeler le critique. None = le critère mérite le critique."""
    if prop is None:
        return Resultat(cid, [], "", 0.0, False, "Aucune proposition du classificateur")
    vals, conf = _valides(cid, prop.valeurs), max(0.0, min(1.0, prop.confiance))
    if not vals:
        return Resultat(cid, [], prop.citation, conf, False, "Information absente ou valeurs hors liste")
    if not _citation_presente(prop.citation, echanges):
        return Resultat(cid, vals, prop.citation, min(conf, 0.5), False, "Citation introuvable dans la réponse de l'utilisateur")
    if conf < seuil:
        return Resultat(cid, vals, prop.citation, conf, False, f"Classificateur peu sûr ({conf:.0%})")
    return None


def debattre(backend: Backend, echanges: list[tuple[str, str]], criteres_ids: list[str],
             seuil: float = 0.8, max_tours: int = MAX_TOURS) -> Debat:
    """Fait débattre les deux agents jusqu'à accord (ou max_tours) sur les critères demandés.

    Tour : le classificateur propose ; les critères où il est sûr (et dont la citation existe) passent au
    critique ; les autres partent directement en précision. Les critères contestés sont rejoués au tour suivant.
    """
    tours, resultats = [], {}
    a_traiter, classif, crit = list(criteres_ids), None, None
    for t in range(1, max_tours + 1):
        classif = classifier(backend, echanges, a_traiter, crit, classif)
        props = {p.critere_id: p for p in classif.propositions}
        sures = []
        for cid in a_traiter:
            r = precontrole(cid, props.get(cid), echanges, seuil)
            if r is None:
                sures.append(cid)
            else:
                resultats[cid] = r
        trace = {"tour": t, "classificateur": classif.model_dump(), "critique": None, "valides": []}
        if not sures:  # rien de solide à faire vérifier : seul l'utilisateur peut compléter
            tours.append(trace)
            break
        soumis = Classification(propositions=[props[c] for c in sures])
        crit = critiquer(backend, echanges, sures, soumis)
        avis = {a.critere_id: a for a in crit.avis}
        contestes = []
        for cid in sures:
            resultats[cid] = evaluer(cid, props[cid], avis.get(cid), echanges, seuil)
            if not resultats[cid].valide:
                contestes.append(cid)
        trace.update(critique=crit.model_dump(), valides=[c for c in sures if resultats[c].valide])
        tours.append(trace)
        if not contestes:
            break
        a_traiter, classif = contestes, soumis
    restants = [c for c, r in resultats.items() if not r.valide]
    question = crit.question_relance.strip() if (crit and restants) else ""
    return Debat(resultats, tours, question)
