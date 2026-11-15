"""Lecture déterministe des réponses explicites, avant tout appel à un modèle.

Ce module ne comprend volontairement que quelques faits vérifiables : la durée
de placement A2, la réserve hors placement A5 et le oui/non à une question simple
sur les dettes coûteuses A7. Une absence de résultat laisse la main au parcours
normal ; elle ne signifie ni « non » ni « information absente ».

Bornes sans chevauchement : A2 [0,3), [3,5), [5,10), [10,15], (15,+inf) ans ;
A5 zéro, (0,3), [3,6], (6,+inf) mois. Quinze ans et six mois sont donc des réponses
complètes, sans demande de précision à une frontière. Les nombres et citations
originaux sont conservés. Confiance 1 signifie règle satisfaite, pas fiabilité de
la transcription : le texte peut toujours être corrigé par l'utilisateur.
"""
from __future__ import annotations

import re
import unicodedata


SUPPORTES = ("A2", "A5", "A7")
VERSION_REGLES = "reponses_explicites_v1"


def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte.casefold().replace("’", "'"))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.replace("–", "-").replace("—", "-").split())


def _nombres_francais() -> dict[str, int]:
    petits = ("zero", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
              "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize")
    nombres = {v: i for i, v in enumerate(petits)}
    nombres["une"] = 1
    for i in range(17, 20):
        nombres["dix " + petits[i - 10]] = i
    for dizaine, mot in ((20, "vingt"), (30, "trente"), (40, "quarante"), (50, "cinquante"), (60, "soixante")):
        nombres[mot] = dizaine
        for unite in range(1, 10):
            nombres[mot + (" et " if unite == 1 else " ") + petits[unite]] = dizaine + unite
    inverses = {v: k for k, v in nombres.items()}
    inverses[1] = "un"
    for n in range(70, 80):
        nombres["soixante " + ("et " if n == 71 else "") + inverses[n - 60]] = n
    nombres.update({"quatre vingt": 80, "quatre vingts": 80, "cent": 100})
    for n in range(81, 100):
        nombres["quatre vingt " + inverses[n - 80]] = n
    return nombres


_NOMBRES = _nombres_francais()
_MOTS_NOMBRES = "|".join(re.escape(m).replace(r"\ ", r"[ -]+")
                         for m in sorted(_NOMBRES, key=len, reverse=True))
# La séparation souple autorise aussi « 15ans » et « sixmois », sans reconnaître un morceau de mot.
_NOMBRE = rf"(?:\d+(?:[,.]\d+)?|{_MOTS_NOMBRES})"
_DUREE = re.compile(rf"(?<!\w)(?<!\d[.,])(?P<n>{_NOMBRE})\s*(?P<u>annees?|ans?|mois)\b(?P<demi>\s+et\s+demi(?:e)?)?")
_INTERVALLE = re.compile(rf"(?<!\w)(?<!\d[.,])(?P<entre>entre\s+)?(?P<a>{_NOMBRE})\s+(?P<sep>a|et)\s+(?P<b>{_NOMBRE})\s*(?P<u>annees?|ans?|mois)\b")
_INCERTAIN = re.compile(r"\b(?:peut[- ]etre|pas sur|pas certain|je ne sais|j'hesite|je crois|je pense|probablement|sans doute|normalement|vers|autour de|presque|voire|idealement|ca depend|selon|environ|a peu pres|une quinzaine)\b")
_BORNE = re.compile(r"\b(?:au moins|au plus|plus de|moins de|pas avant|minimum|maximum|jusqu'a|d'ici|avant|au[ -]dela|au pire|au plus tard|ou plus)\b")
_BORNE_INF = re.compile(r"\b(?:au moins|plus de|pas avant|minimum|au minimum)\b")
_NEGATION = re.compile(r"\b(?:pas|jamais|ni|sans)\b|\bn[' ]")
_PASSE = re.compile(r"\b(?:depuis|il y a|cela fait|ca fait|j'avais|j'ai eu)\b|j'ai(?: deja)? (?:investi|place|garde|laisse)\b")
_RESERVE = re.compile(r"\b(?:fonds d'urgence|fonds d urgence|fonds de reserve|coussin|de cote|disponible ailleurs|hors (?:de ce |du |mon )?placement)\b|\b(?:ma|une|la|votre|notre|cette|sa|ta) reserve\b|^reserve\s*:|sans (?:toucher|recourir).{0,15}placement")
_HORIZON = re.compile(r"\bhorizon\b|(?:argent|capital|placement).{0,35}(?:besoin|recuper|garder|placer)|(?:besoin|garder|placer|investir|laisser|recuperer).{0,45}(?:argent|capital|placement)|\b(?:placer|investir)\b")
_ARGENT_PLACE = re.compile(r"(?:mon|ce|le) placement.{0,25}(?:couvre|represente|equivaut|permet)|(?:avec|grace a|en vendant|en retirant).{0,15}(?:placement|portefeuille|capital investi)")


def _nombre(texte: str) -> float:
    cle = " ".join(texte.replace("-", " ").split())
    return float(_NOMBRES[cle]) if cle in _NOMBRES else float(cle.replace(",", "."))


def _intervalle(texte: str) -> re.Match | None:
    trouve = _INTERVALLE.search(texte)
    # Le « et » d'un nombre composé (vingt et un) n'est pas une fourchette.
    return None if trouve and trouve["sep"] == "et" and not trouve["entre"] else trouve


def _cibles_question(question: str) -> set[str]:
    q = _normaliser(question)
    cibles = set()
    if re.search(r"\bhorizon\b|(?:combien|quand|moment|echeance).{0,80}(?:besoin|argent|capital|recuper)|(?:besoin|recuper).{0,60}(?:combien|quand|ans|annees)", q):
        cibles.add("A2")
    if _RESERVE.search(q) or re.search(r"combien de mois.{0,45}(?:depenses|imprevu|reserve)", q):
        cibles.add("A5")
        # « combien de temps ... sans toucher au placement » est une question de réserve.
        if "sans toucher" in q and not re.search(r"\bhorizon\b|majeure partie|recuperer", q):
            cibles.discard("A2")
    if re.search(r"dettes? a taux eleve|dettes? a plus de huit pour cent|credit a taux eleve|solde de carte|pret personnel a taux eleve", q):
        cibles.add("A7")
    return cibles


def _clauses(reponse: str) -> list[str]:
    return [x.strip() for x in re.split(r"[;\n]|\.(?=\s+[A-Za-zÀ-ÿ])|\bet\s+(?=(?:j['’]|je\b|nous\b|mon\b|ma\b|mes\b))", reponse, flags=re.I) if x.strip()]


def _court(texte: str, duree: re.Match | None, intervalle: re.Match | None, cid: str) -> bool:
    """Une réponse scalaire peut emprunter son référent à une question précise."""
    match = intervalle or duree
    reste = texte[:match.start()] + texte[match.end():] if match else texte
    if cid == "A2":
        # L'ouverture demande objectif ET horizon : cet objectif explicite ne rend pas la durée ambiguë.
        reste = re.sub(r"\b(?:ma|notre|la) retraite\b", "", reste)
    if cid == "A5":
        reste = re.sub(r"^(?:j'ai(?: de quoi)?|je (?:peux|pourrais|pourrai) (?:couvrir|payer|tenir|vivre)|j'en ai pour|je dispose de)\s*", "", reste)
    reste = re.sub(r"\b(?:c'est|c est|pour|dans|pendant|sur|exactement|euh|oui|de depenses|de depense|mois|ans|annees)\b", "", reste)
    return not re.sub(r"[\s,!.?:-]+", "", reste)


def _classe(cid: str, mois: float) -> str:
    if cid == "A2":
        ans = mois / 12
        return ("moins_3_ans" if ans < 3 else "3_5_ans" if ans < 5 else "5_10_ans" if ans < 10
                else "10_15_ans" if ans <= 15 else "plus_15_ans")
    return "aucun" if mois == 0 else "moins_3_mois" if mois < 3 else "3_6_mois" if mois <= 6 else "plus_6_mois"


def _classe_minimum(cid: str, mois: float, stricte: bool) -> str:
    if stricte and cid == "A2" and mois == 180:
        return "plus_15_ans"
    if stricte and cid == "A5" and mois == 6:
        return "plus_6_mois"
    if stricte and cid == "A5" and mois == 0:
        return "moins_3_mois"
    return _classe(cid, mois)


def _precision(cid: str, motif: str) -> dict:
    questions = {"A2": "Dans combien d'années devrez-vous récupérer la majeure partie de cet argent ?",
                 "A5": "Sans utiliser ce placement, combien de mois de dépenses votre argent disponible ailleurs couvre-t-il ?",
                 "A7": "Avez-vous une dette à taux élevé, comme un solde de carte de crédit ?"}
    return {"motif": motif, "question": questions[cid]}


def _resultat(cid: str, reponse: str, valeur: str, **mesure) -> dict:
    return {"valeurs": [valeur], "citation": reponse.strip(), "source": "réponse explicite (règle)",
            "statut": "validé", "confiance": 1.0, "regle": f"{VERSION_REGLES}:{cid}",
            "motif": "Réponse explicite dans le référent demandé ; bornes déterministes sans chevauchement.", **mesure}


def _question_a7_autorisee(question: str, criteres_question=None) -> bool:
    """Une question identifiée par le code, ou l'une de ses deux formulations de référence."""
    from criteres import CRITERES
    from questions_conversation import QUESTIONS

    def normaliser_ponctuation(t):
        return " ".join(re.sub(r"[^\w' ]", " ", _normaliser(t)).split())

    q = normaliser_ponctuation(question)
    if criteres_question is not None:
        if set(criteres_question) != {"A7"}:
            return False
        autres_sujets = r"\b(?:reserve|personnes|enfants|revenus|secteur|horizon|actions|fnb|emploi)\b"
        return _cibles_question(question) == {"A7"} and not re.search(autres_sujets, q)
    return q in {normaliser_ponctuation(CRITERES["A7"]["relance"]), normaliser_ponctuation(QUESTIONS["A7"])}


def analyser_reponses(question: str, reponse: str, criteres_ids=(), *, criteres_question=None) -> dict:
    """Retourne réponses vérifiées et ambiguïtés ciblées, sans appel réseau ni mutation.

    ``criteres_ids`` restreint les critères à examiner ; sa présence ne prouve pas
    le contexte d'une réponse. Une ambiguïté n'est jamais une valeur de profil.
    """
    autorises = set(criteres_ids) if criteres_ids else set(SUPPORTES)
    autorises &= set(SUPPORTES)
    if not reponse.strip():
        return {"reponses": {}, "a_preciser": {}}
    # Une demande de manipuler les règles n'est pas une déclaration de situation.
    if re.search(r"\b(?:ignore\w*|consigne\w*|prompt\w*)\b|\b(?:classe|valide)\s+(?:mon|ma|le|ce)\b", _normaliser(reponse)):
        return {"reponses": {}, "a_preciser": {}}
    q_cibles = _cibles_question(question)
    options: dict[str, list[dict]] = {}
    ambiguites: dict[str, dict] = {}
    for morceau in _clauses(reponse):
        t = _normaliser(morceau)
        intervalle = _intervalle(t)
        durees = list(_DUREE.finditer(t))
        # Une unité peut être omise seulement après une question donnant elle-même cette unité.
        nu = re.fullmatch(rf"(?:exactement\s+)?(?P<n>{_NOMBRE})[.! ]*", t)
        mesures = None
        if intervalle:
            mesures = [_nombre(intervalle["a"]), _nombre(intervalle["b"])]
            unite = "mois" if intervalle["u"] == "mois" else "ans"
        elif len(durees) == 1:
            d = durees[0]
            mesures = [_nombre(d["n"]) + (0.5 if d["demi"] else 0)]
            unite = "mois" if d["u"] == "mois" else "ans"
        elif nu and len(q_cibles & {"A2", "A5"}) == 1:
            cid_unique = next(iter(q_cibles & {"A2", "A5"}))
            q = _normaliser(question)
            if cid_unique == "A5" and "mois" in q:
                mesures, unite = [_nombre(nu["n"])], "mois"
            elif cid_unique == "A2" and re.search(r"\b(?:ans|annees)\b", q):
                mesures, unite = [_nombre(nu["n"])], "ans"
        for cid in ("A2", "A5"):
            if cid not in autorises:
                continue
            explicite = bool((_HORIZON if cid == "A2" else _RESERVE).search(t))
            contexte_question = q_cibles & {"A2", "A5"} == {cid}
            candidat = explicite or contexte_question or (cid == "A5" and "depenses" in t and bool(durees))
            if not candidat:
                continue
            if not explicite and not contexte_question:
                ambiguites[cid] = _precision(cid, "La quantité n'est pas rattachée à une réserve hors placement par la réponse ou sa question.")
                continue
            if mesures is None:
                if durees:
                    ambiguites[cid] = _precision(cid, "Plusieurs durées sans attribution unique à ce critère.")
                continue
            if re.search(rf"(?<!\w)-\s*{_NOMBRE}", t) or re.search(r"\b(?:mais|sauf|cependant|pourtant|bloque|indisponible)\b", t):
                ambiguites[cid] = _precision(cid, "Quantité négative ou réserve explicite : le contexte doit être interprété.")
                continue
            if cid == "A5" and (_ARGENT_PLACE.search(t) or re.search(r"\b(?:salaire|revenus?)\b", t) and not _RESERVE.search(t)):
                ambiguites[cid] = _precision(cid, "La réserve hors placement n'est pas distinguée du placement ou du revenu.")
                continue
            if cid == "A2" and _RESERVE.search(t) and not _HORIZON.search(t):
                continue  # une réserve n'est pas l'échéance du placement
            if cid == "A5" and _HORIZON.search(t) and not _RESERVE.search(t):
                continue
            borne_inf = (bool(_BORNE_INF.search(t)) and len(mesures) == 1
                         and not re.search(r"\b(?:au plus|moins de|maximum|jusqu'a)\b", t))
            stricte = bool(re.search(r"\bplus de\b", t))
            negation = _NEGATION.search(t)
            # Le référent « sans toucher au placement » n'est pas une négation de la quantité.
            sans_reference = re.sub(r"sans (?:toucher|recourir).{0,20}placement", "", t)
            if borne_inf:
                sans_reference = _BORNE_INF.sub("", sans_reference)
            if _INCERTAIN.search(t):
                continue  # le modèle peut interpréter cette nuance sans faire répéter l'utilisateur
            if (_BORNE.search(t) and not borne_inf) or _PASSE.search(t) or (negation and _NEGATION.search(sans_reference)):
                ambiguites[cid] = _precision(cid, "Durée hésitante, bornée, passée ou niée : aucune valeur imposée.")
                continue
            reste_quantites = (_INTERVALLE.sub("", t) if intervalle else _DUREE.sub("", t))
            autres_nombres = [m[0] for m in re.finditer(rf"(?<!\w)(?<!\d[.,]){_NOMBRE}(?!\w)(?![.,]\d)", reste_quantites)
                              if not (_nombre(m[0]) == 1 and re.match(r"\s+(?:fonds|reserve|placement|coussin|horizon|capital|portefeuille|projet)\b",
                                                                   reste_quantites[m.end():]))] if durees else []
            if autres_nombres:
                ambiguites[cid] = _precision(cid, "Plusieurs nombres sans attribution unique au critère demandé.")
                continue
            court = _BORNE_INF.sub("", t) if borne_inf else t
            court_durees = list(_DUREE.finditer(court))
            if not explicite and not (_court(court, court_durees[0] if len(court_durees) == 1 else None,
                                             _intervalle(court), cid) or nu):
                ambiguites[cid] = _precision(cid, "Le nombre ne désigne pas explicitement la quantité demandée.")
                continue
            if not 0 <= min(mesures) <= max(mesures) <= 1200:
                ambiguites[cid] = _precision(cid, "Quantité hors des bornes de lecture du parseur.")
                continue
            if len(mesures) == 2 and mesures[0] > mesures[1]:
                ambiguites[cid] = _precision(cid, "Les bornes de la fourchette sont inversées.")
                continue
            mois = [x * (12 if unite == "ans" else 1) for x in mesures]
            classes = {_classe_minimum(cid, x, stricte) if borne_inf else _classe(cid, x) for x in mois}
            if len(classes) != 1:
                ambiguites[cid] = _precision(cid, "La fourchette traverse plusieurs classes ; seule cette frontière doit être précisée.")
                continue
            options.setdefault(cid, []).append(_resultat(cid, reponse, classes.pop(),
                nombre=mesures[0] if len(mesures) == 1 and not borne_inf else None, unite=unite,
                duree_mois=mois[0] if len(mois) == 1 and not borne_inf else None,
                **({"nombre_min": mesures[0], "duree_min_mois": mois[0], "borne_incluse": not stricte,
                    "nature": "borne inférieure", "motif": "Borne inférieure explicite conservée ; classe minimale confirmée, sans inventer de durée exacte."}
                   if borne_inf else {}),
                **({"intervalle": mesures, "intervalle_mois": mois} if len(mesures) == 2 else {})))
    if "A7" in autorises:
        r = " ".join(re.sub(r"[^\w' ]", " ", _normaliser(reponse)).split())
        if _question_a7_autorisee(question, criteres_question):
            oui = {"oui", "oui effectivement", "oui j'en ai"}
            non = {"non", "non aucune", "non aucune dette", "aucune dette a taux eleve", "je n'ai aucune dette a taux eleve"}
            if r in oui | non:
                options["A7"] = [_resultat("A7", reponse, "oui" if r in oui else "non")]
    reponses = {}
    for cid, candidats in options.items():
        signatures = {(tuple(x["valeurs"]), x.get("duree_mois"), x.get("duree_min_mois"),
                       x.get("borne_incluse"), tuple(x.get("intervalle_mois", []))) for x in candidats}
        if len(signatures) == 1 and cid not in ambiguites:
            reponses[cid] = candidats[0]
        else:
            ambiguites[cid] = _precision(cid, "Plusieurs quantités ou interprétations pour le même critère.")
    return {"reponses": reponses, "a_preciser": {c: a for c, a in ambiguites.items() if c not in reponses}}


def extraire_reponses(question: str, reponse: str, criteres_ids=(), *, criteres_question=None) -> dict[str, dict]:
    """Seulement les réponses immédiatement utilisables ; consulter analyser_reponses pour les ambiguïtés."""
    return analyser_reponses(question, reponse, criteres_ids, criteres_question=criteres_question)["reponses"]
