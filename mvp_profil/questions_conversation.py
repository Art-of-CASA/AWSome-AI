"""Questions conversationnelles choisies par le code, avec un budget explicite.

Une réponse renseignée ou en cours de vérification n'est jamais une nouvelle
question. Un sujet déjà demandé ne revient qu'en clarification explicitement
justifiée, au plus une fois. Les inconnues restantes restent des inconnues : le
pilote les signale pour un choix fermé, sans inventer une réponse pour raccourcir
le parcours. La priorité réutilise l'heuristique de pilotage.py ; elle n'est pas un
optimum statistique mesuré.

Le résultat de choisir_question est pur. Appeler enregistrer_question seulement
quand cette question a effectivement été affichée/lue, jamais lors d'un calcul
de prévisualisation ou d'une tâche en arrière-plan.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from criteres import CRITERES, MESURES, SECTIONS
from pilotage import prioriser_criteres


MAX_CLARIFICATIONS = 1
STATUTS_CLAIRS = {"validé", "retenu", "confirmé"}
STATUTS_EN_ATTENTE = {"analyse en cours", "en analyse", "en cours", "provisoire", "à vérifier"}

# Une seule réponse peut donner deux informations lorsque les référents sont les
# mêmes. Réserve/part d'épargne et retrait/revenu restent des questions séparées.
GROUPES = {
    frozenset(("A3", "A2")): (
        ("A3", "A2"),
        "Parlons de cette somme précise : à quoi servira-t-elle, et dans combien d'années devrez-vous en récupérer la majeure partie ?"),
    frozenset(("D5", "D6")): (
        ("D6", "D5"),
        "Quels secteurs voulez-vous exclure, et quels domaines vous intéressent particulièrement ?"),
}

QUESTIONS = {
    "A1": "Êtes-vous aux études, en début ou milieu de carrière, proche de la retraite ou déjà à la retraite ?",
    "A2": "Dans combien d'années aurez-vous besoin de la majeure partie de cet argent ?",
    "A3": "À quoi servira principalement cet argent ?",
    "A4": "Ce placement représente-t-il moins du quart de votre épargne totale, entre un quart et 60 %, ou plus de 60 % ?",
    "A5": "En dehors de ce placement et sans emprunter, combien de mois de dépenses essentielles votre argent disponible pourrait-il couvrir ?",
    "A6": "Vos revenus sont-ils stables, variables, ou actuellement incertains ?",
    "A7": "Avez-vous des dettes à plus de huit pour cent d'intérêt, comme une carte de crédit non remboursée ?",
    "A8": "Combien de personnes dépendent financièrement de vous ?",
    "A9": "Avant cette échéance, prévoyez-vous de retirer du capital : jamais, une fois, ou régulièrement ?",
    "A10": "Les revenus de ce placement sont-ils indispensables pour vivre, simplement souhaités, ou n'en avez-vous pas besoin ?",
    "A12": "Dans quel domaine travaillez-vous, ou travailliez-vous ?",
    "B3": "Lors d'une forte baisse passée de vos placements, avez-vous gardé, vendu, renforcé, ou jamais vécu cette situation ?",
    "C2": "Quels produits avez-vous déjà détenus : fonds, FNB, actions, obligations, crypto, ou aucun ?",
    "D3": "Dans quelles régions souhaitez-vous investir ? Vous pouvez aussi dire partout dans le monde.",
    "D5": "Quels thèmes ou secteurs vous attirent ? Vous pouvez dire que vous n'avez pas de préférence.",
    "D6": "Quels secteurs refusez-vous ? Vous pouvez dire que vous n'en excluez aucun.",
}

CLARIFICATIONS = {
    "A2": "Pour ce placement précis, quel est le délai le plus tôt auquel vous pourriez avoir besoin de la majeure partie de l'argent ?",
    "A5": "La réserve évoquée reste-t-elle disponible sans vendre ce placement ?",
    "A4": "Parlons du placement entier : quelle part de votre épargne totale représente-t-il ?",
    "A9": "Parlez-vous d'un retrait du capital avant l'échéance, ou seulement des intérêts et dividendes versés ?",
    "A10": "Avez-vous besoin des revenus de ce placement pour payer vos dépenses courantes, même sans retirer le capital ?",
}


def _compteurs(questions_posees: Mapping, cid: str) -> tuple[int, int]:
    """Les anciens compteurs entiers restent acceptés : 1 initiale, puis clarification."""
    donnees = questions_posees.get(cid, {})
    if isinstance(donnees, int):
        return min(max(donnees, 0), 1), max(donnees - 1, 0)
    if not isinstance(donnees, Mapping):
        return 0, 0
    return max(0, int(donnees.get("initiales", 0))), max(0, int(donnees.get("clarifications", 0)))


def _clairs(profil: dict) -> set[str]:
    return {cid for cid, entree in profil.items()
            if entree.get("statut") in STATUTS_CLAIRS and entree.get("valeurs")}


def _a_clarifier(a_clarifier: Iterable | Mapping) -> set[str]:
    if isinstance(a_clarifier, Mapping):
        # Une entrée vide ne constitue pas un motif d'ambiguïté.
        return {cid for cid, motif in a_clarifier.items() if motif}
    return set(a_clarifier)


def _question_initiale(cid: str) -> str:
    if cid in QUESTIONS:
        return QUESTIONS[cid]
    if CRITERES[cid]["relance"]:
        return CRITERES[cid]["relance"]
    for section in SECTIONS:
        for item in section["items"]:
            if item.get("critere") == cid:
                return item["texte"]
    raise ValueError(f"Aucune question déclarative disponible pour {cid}")


def choisir_question(profil: dict, restants: Iterable[str], questions_posees: Mapping,
                     en_analyse: Iterable[str] = (), a_clarifier: Iterable | Mapping = (),
                     pistes: Mapping | None = None) -> dict:
    """Retourne une seule question, une attente, ou la fin de la conversation.

    ``a_clarifier`` est un signal explicite de l'orchestrateur : une ambiguïté
    réelle a été identifiée. Le simple temps d'analyse ou une confiance brute
    du modèle ne doit pas servir de signal de clarification. ``pistes`` reste
    compatible avec l'appel historique mais ne permet pas à du texte libre de
    contourner les formulations/cibles contrôlées.

    ``a_completer`` contient les sujets déjà demandés qui devront rester visibles
    et, si nécessaire, être précisés par choix fermé. ``attendre`` interdit de
    lancer des compléments pour des sujets dont le contrôle n'est pas terminé.
    Aucun profil, compteur ou critère n'est modifié par cette fonction.
    """
    del pistes  # aucune confirmation suggestive ou question libre non contrôlée
    candidats = list(dict.fromkeys(restants))
    inconnus = set(candidats) - set(CRITERES)
    if inconnus:
        raise ValueError("Critères inconnus : " + ", ".join(sorted(inconnus)))
    clairs = _clairs(profil)
    attente = set(en_analyse) | {
        cid for cid, entree in profil.items() if entree.get("statut") in STATUTS_EN_ATTENTE}
    ambigu = _a_clarifier(a_clarifier)
    abordes = {cid for cid, entree in profil.items() if entree.get("valeurs") and cid not in clairs}
    a_completer, nouveaux, clarifications = [], [], []
    for cid in candidats:
        if cid in clairs or cid in attente:
            continue
        initiales, precisees = _compteurs(questions_posees, cid)
        if cid in MESURES:
            a_completer.append(cid)  # le quiz/replay reste mesuré par son propre parcours
        elif cid in ambigu and precisees < MAX_CLARIFICATIONS:
            clarifications.append(cid)
        elif initiales or precisees or cid in abordes:
            a_completer.append(cid)
        else:
            nouveaux.append(cid)

    etats = {}
    for cid in candidats:
        initiales, precisees = _compteurs(questions_posees, cid)
        etat = ("clair" if cid in clairs else "en_analyse" if cid in attente else
                "a_clarifier" if cid in clarifications else "aborde" if cid in a_completer else "inconnu")
        etats[cid] = {"etat": etat, "questions_initiales": initiales, "clarifications": precisees}
    commun = {"message": "", "criteres": [], "clarification": False, "termine": False,
              "attendre": False, "a_completer": a_completer,
              "etats": etats,
              "en_attente": [cid for cid in candidats if cid not in clairs and cid in attente]}
    if clarifications:
        cid = prioriser_criteres(profil, clarifications)[0]
        return {**commun, "message": CLARIFICATIONS.get(cid, _question_initiale(cid)),
                "criteres": [cid], "clarification": True,
                "raison": "Une ambiguïté identifiée reçoit son unique clarification."}
    if nouveaux:
        ordre = prioriser_criteres(profil, nouveaux)
        premier = ordre[0]
        for ensemble, (ids, message) in GROUPES.items():
            if premier in ensemble and ensemble <= set(nouveaux):
                return {**commun, "message": message, "criteres": list(ids),
                        "raison": "Deux informations liées, encore inconnues et jamais demandées."}
        return {**commun, "message": _question_initiale(premier), "criteres": [premier],
                "raison": "Information utile encore inconnue et jamais demandée."}
    if commun["en_attente"]:
        return {**commun, "message": "Je termine la vérification de vos réponses.", "attendre": True,
                "raison": "Une analyse en cours ne justifie aucune nouvelle question à l'utilisateur."}
    return {**commun, "message": "Merci, les informations recueillies sont conservées. Passons à la suite.",
            "termine": True, "raison": "Les inconnues restantes restent à compléter, sans boucle conversationnelle."}


def enregistrer_question(questions_posees: dict, question: dict, tour: int | None = None) -> None:
    """Comptabilise uniquement les sujets effectivement affichés par une question.

    ``tour`` rend l'appel idempotent pendant les rafraîchissements Streamlit.
    L'orchestrateur doit réutiliser le même numéro pour le même affichage.
    """
    if question.get("attendre") or question.get("termine"):
        return
    clarification = bool(question.get("clarification"))
    for cid in question.get("criteres", []):
        initiales, precisees = _compteurs(questions_posees, cid)
        ancien = questions_posees.get(cid)
        if isinstance(ancien, Mapping) and tour is not None and ancien.get("dernier_tour") == tour:
            continue
        if clarification and precisees >= MAX_CLARIFICATIONS:
            raise ValueError(f"Le budget de clarification de {cid} est déjà consommé.")
        if not clarification and initiales:
            raise ValueError(f"La question initiale de {cid} a déjà été posée.")
        questions_posees[cid] = {"initiales": initiales + (not clarification),
                                "clarifications": precisees + clarification,
                                "dernier_tour": tour}
