"""« Parler au conseiller » : la personne dit ce qu'elle aimerait ajouter, le portefeuille s'ajuste si c'est cohérent.

Le partage des rôles ne change pas :
  - le modèle COMPREND la demande (quel actif, quelle part, quelle envie) et choisit un outil ; il rédige la réponse ;
  - le code DÉCIDE : ajout appliqué, part réduite proposée, ou refus avec des alternatives plus cohérentes ;
  - quand rien n'est compatible, le code dit quelle réponse du profil il faudrait revoir, et ne l'applique qu'après
    une confirmation explicite de la personne. Ce qui a été MESURÉ (replay, fourchettes, quiz) ne se change pas ici.
Sans modèle, un interprète à règles comprend les demandes simples : la conversation fonctionne quand même.

Les mises à jour confirmées sont gardées à part du profil d'origine (elles s'annulent d'un clic) ; les propositions
sont recalculées sur le profil ainsi mis à jour.
"""
from __future__ import annotations

import copy
import re

from . import agents, fidelite, gouvernance
from .analyse import Analyse
from .appariement import pct
from .chargement import sans_accents

from criteres import CRITERES  # noqa: E402  (profil, lecture seule)

BIENVENUE = ("Dites-moi ce que vous aimeriez voir dans votre portefeuille fictif : un titre précis, un thème, une région. "
             "Je l'ajoute si c'est cohérent avec votre profil ; sinon je vous propose ce qui s'en rapproche le plus.")


def etat_initial() -> dict:
    return {"messages": [{"role": "assistant", "texte": BIENVENUE}], "ajouts": {}, "maj": {}, "en_attente": None}


def humaniser(texte: str) -> str:
    """Retire les détails techniques d'une raison (noms de colonnes, identifiants) pour l'affichage courant."""
    t = re.sub(r"\s*\((?:[a-z_0-9]+ = [^()]*)\)", "", str(texte))
    t = re.sub(r"\s*\[[^\]]*:[^\]]*\]", "", t)
    return re.sub(r"\s{2,}", " ", t).replace(" .", ".").strip().rstrip(".")


def _suite(texte: str) -> str:
    """Raison insérée après deux-points : sans majuscule initiale, avec un seul point final."""
    t = humaniser(texte)
    return (t[:1].lower() + t[1:] if t[:2] != t[:2].upper() else t) + "."


def profil_effectif(profil: dict, maj: dict) -> dict:
    """Le profil de la session, avec les réponses que la personne a confirmé vouloir mettre à jour. Copie : l'original reste intact."""
    if not maj:
        return profil
    p = copy.deepcopy(profil)
    for cid, m in maj.items():
        p[cid] = {**p.get(cid, {}), "valeurs": list(m["valeurs"]), "statut": "validé", "confiance": 1.0,
                  "source": "mise à jour confirmée dans la conversation", "citation": m.get("citation", ""),
                  "motif": "Réponse revue par la personne pendant l'ajustement du portefeuille"}
        if cid == "B1" and "declare" in p[cid]:
            p[cid]["declare"] = m["valeurs"][0]
    return p


class Contexte:
    """Ce dont la conversation a besoin : le profil d'origine, l'état, et de quoi recalculer l'analyse après un changement."""

    def __init__(self, profil: dict, dynamiques: list, etat: dict, montant: float | None = None, nom: str | None = None, journal=None):
        self.profil, self.dynamiques, self.etat, self.montant, self.nom, self.journal = profil, dynamiques, etat, montant, nom, journal
        self._analyse = None

    @property
    def analyse(self) -> Analyse:
        if self._analyse is None:
            self._analyse = Analyse(profil_effectif(self.profil, self.etat["maj"]), self.dynamiques, self.montant, nom=self.nom,
                                    ajouts=self.etat["ajouts"])
        return self._analyse

    def recalculer(self):
        self._analyse = None

    def noter(self, type_: str, **donnees):
        if self.journal is not None:
            self.journal.noter(type_, **donnees)


def _resume_portefeuille(a: Analyse) -> dict:
    pf = a.portefeuille
    if "erreur" in pf:
        return {"erreur": pf["erreur"], "reponses_qui_excluent_le_plus": pf.get("diagnostic", [])}
    return {"positions": [{"ticker": l["ticker"], "nom": l["nom"], "poids_pct": l["poids_pct"], "a_votre_demande": l["demande"]} for l in pf["lignes"]],
            "encaisse_pct": pf["encaisse_pct"], "perte_stress_pct": pf["perte_stress_pct"], "budget_perte_pct": pf["budget_perte_pct"],
            "tension": pf["etat_tension"].replace("_", " "), "limite_par": pf["limite_par"], "ajouts": pf["ajouts"]}


# ---------- Actions : la seule façon de modifier quoi que ce soit ----------

def ajouter(ctx: Contexte, actif: str, part_pct: float | None = None) -> dict:
    part = float(part_pct) if part_pct is not None else None
    if part is not None and part <= 0:
        return {"decision": "impossible", "part_demandee_pct": part,
                "message": "La part demandée doit être strictement positive. Aucun ajout n'est appliqué."}
    d = ctx.analyse.proposer_ajout(str(actif), part)
    ctx.etat["en_attente"] = None
    if d.get("empreinte"):
        ctx.noter("verdict_fige", ticker=d["ticker"], part_pct=d.get("part_demandee_pct") or d.get("part_pct"), verdict=d["verdict"], empreinte=d["empreinte"])
    if d["decision"] == "applicable":
        ctx.etat["ajouts"][d["ticker"]] = d["part_pct"]
        ctx.recalculer()
        d["portefeuille"] = _resume_portefeuille(ctx.analyse)
        ctx.noter("ajout_applique", ticker=d["ticker"], part_pct=d["part_pct"])
    elif d["decision"] == "reduit":
        ctx.etat["en_attente"] = {"type": "reduit", "ticker": d["ticker"], "nom": d["nom"], "part_pct": d["part_pct"],
                                  "question": f"Ajouter {d['nom']} pour {d['part_pct']:.0f} % ?"}
    elif d["decision"] == "refuse" and (d.get("mises_a_jour") or {}).get("possible"):
        ch = d["mises_a_jour"]["changements"]
        ctx.etat["en_attente"] = {"type": "maj", "changements": ch, "puis": {"ticker": d["ticker"], "part_pct": part_pct},
                                  "question": "Mettre à jour " + " et ".join(f"« {c['nom']} »" for c in ch) + " ?"}
    return d


def retirer(ctx: Contexte, actif: str) -> dict:
    tk = ctx.analyse.trouver(str(actif))
    if tk not in ctx.etat["ajouts"]:
        return {"decision": "rien", "message": "Cet actif n'a pas été ajouté à votre demande : je ne retire que ce que vous avez ajouté."}
    ctx.etat["ajouts"].pop(tk)
    ctx.recalculer()
    ctx.noter("ajout_retire", ticker=tk)
    return {"decision": "retire", "ticker": tk, "portefeuille": _resume_portefeuille(ctx.analyse)}


def proposer_mise_a_jour(ctx: Contexte, critere: str, valeur: str) -> dict:
    """Une réponse DÉCLARÉE peut être revue par la personne, après confirmation. Une réponse mesurée, non."""
    cid = str(critere).strip().upper()
    if cid in Analyse.MESURES:
        return {"decision": "impossible", "message": f"« {CRITERES[cid]['nom']} » vient de {Analyse.MESURES[cid]} : cela se mesure, cela ne se déclare pas."}
    if cid not in CRITERES or str(valeur) not in CRITERES[cid]["valeurs"]:
        return {"decision": "impossible", "message": "Réponse inconnue ou valeur hors de la liste prévue.",
                "valeurs_possibles": CRITERES.get(cid, {}).get("valeurs")}
    e = ctx.analyse.et_si(cid, str(valeur))
    avant = list((ctx.analyse.profil.get(cid) or {}).get("valeurs") or [])
    from .contraintes import _libelle
    ch = [{"critere": cid, "nom": CRITERES[cid]["nom"], "avant": avant, "avant_libelle": ", ".join(_libelle(cid, v) for v in avant) or "non renseigné",
           "apres": [str(valeur)], "apres_libelle": _libelle(cid, str(valeur))}]
    ctx.etat["en_attente"] = {"type": "maj", "changements": ch, "puis": None, "question": f"Mettre à jour « {CRITERES[cid]['nom']} » ?"}
    return {"decision": "a_confirmer", "changements": ch, "ce_qui_changerait": {"contraintes": e.get("contraintes"),
            "actifs_qui_changent_de_verdict": e.get("nb_changements_de_bande"), "portefeuille_avant": e.get("portefeuille_avant"),
            "portefeuille_apres": e.get("portefeuille_apres")}}


def confirmer(ctx: Contexte, citation: str = "") -> dict:
    att = ctx.etat.get("en_attente")
    if not att:
        return {"decision": "rien", "message": "Il n'y a rien à confirmer pour l'instant."}
    ctx.etat["en_attente"] = None
    if att["type"] == "reduit":
        return ajouter(ctx, att["ticker"], att["part_pct"])
    for c in att["changements"]:
        ctx.etat["maj"][c["critere"]] = {"valeurs": c["apres"], "avant": c["avant"], "nom": c["nom"], "avant_libelle": c["avant_libelle"],
                                         "apres_libelle": c["apres_libelle"], "citation": citation}
    ctx.recalculer()
    ctx.noter("profil_mis_a_jour", criteres=[c["critere"] for c in att["changements"]], confirme_par="la personne")
    sortie = {"decision": "mis_a_jour", "changements": att["changements"], "portefeuille": _resume_portefeuille(ctx.analyse)}
    if att.get("puis"):
        sortie["ajout"] = ajouter(ctx, att["puis"]["ticker"], att["puis"].get("part_pct"))
    return sortie


def refuser(ctx: Contexte) -> dict:
    avait = ctx.etat.get("en_attente")
    ctx.etat["en_attente"] = None
    return {"decision": "annule" if avait else "rien", "message": "Entendu, rien n'est modifié."}


def annuler_mises_a_jour(ctx: Contexte) -> dict:
    n = len(ctx.etat["maj"])
    ctx.etat["maj"].clear()
    ctx.recalculer()
    ctx.etat["ajouts"] = {t: p for t, p in ctx.etat["ajouts"].items()
                          if ctx.analyse.resultats[t]["verdict"] != "exclu" and p <= (ctx.analyse.resultats[t]["poids_max_pct"] or 0) + 0.1}
    ctx.recalculer()
    return {"decision": "profil_d_origine", "nb_reponses_retablies": n, "portefeuille": _resume_portefeuille(ctx.analyse)}


def chercher_envie(ctx: Contexte, envie: str) -> dict:
    return ctx.analyse.trouver_par_envie(str(envie))


def voir_portefeuille(ctx: Contexte) -> dict:
    return _resume_portefeuille(ctx.analyse)


def consulter_actif(ctx: Contexte, actif: str) -> dict:
    """Lire un verdict et ses explications n'ajoute rien et ne clôt pas une proposition en attente."""
    return ctx.analyse.rechercher(str(actif))


ACTIONS = {
    "ajouter_au_portefeuille": (lambda c, e: ajouter(c, e.get("actif", ""), e.get("part_pct")),
        "Demande d'ajouter un actif (ticker ou nom) au portefeuille fictif, pour une part en % si la personne en donne une. Le code "
        "décide : « applicable » (c'est fait), « reduit » (une part plus petite est proposée, à confirmer), « refuse » (avec des "
        "alternatives et, si c'est possible, les réponses du profil à revoir), ou « absent ».",
        {"actif": {"type": "string"}, "part_pct": {"type": "number", "description": "Part demandée en %, seulement si la personne la donne"}}, ["actif"]),
    "chercher_par_envie": (lambda c, e: chercher_envie(c, e.get("envie", "")),
        "La personne exprime une envie sans nommer d'actif (« plus de technologie », « de l'or », « des dividendes canadiens ») : "
        "renvoie les actifs de l'univers qui y répondent, avec leur verdict pour ce profil.",
        {"envie": {"type": "string"}}, ["envie"]),
    "consulter_actif": (lambda c, e: consulter_actif(c, e.get("actif", "")),
        "Consulte le verdict, les risques et l'explication d'un actif, sans modifier le portefeuille ni le profil. "
        "À utiliser pour une question d'information ou une demande d'explication.",
        {"actif": {"type": "string"}}, ["actif"]),
    "retirer_du_portefeuille": (lambda c, e: retirer(c, e.get("actif", "")),
        "Retire un actif que la personne avait fait ajouter.", {"actif": {"type": "string"}}, ["actif"]),
    "proposer_mise_a_jour_du_profil": (lambda c, e: proposer_mise_a_jour(c, e.get("critere", ""), e.get("valeur", "")),
        "La personne veut revoir une réponse DÉCLARÉE de son profil (identifiant du critère et nouvelle valeur de sa liste fermée). "
        "Rien n'est appliqué : une confirmation explicite sera demandée. À n'utiliser que si la personne le demande.",
        {"critere": {"type": "string"}, "valeur": {"type": "string"}}, ["critere", "valeur"]),
    "confirmer": (lambda c, e: confirmer(c, e.get("mots_de_la_personne", "")),
        "La personne accepte clairement la proposition en attente (part réduite, ou mise à jour d'une réponse).",
        {"mots_de_la_personne": {"type": "string"}}, []),
    "refuser": (lambda c, e: refuser(c), "La personne décline la proposition en attente.", {}, []),
    "annuler_les_mises_a_jour": (lambda c, e: annuler_mises_a_jour(c),
        "Revient aux réponses d'origine du profil.", {}, []),
    "voir_le_portefeuille": (lambda c, e: voir_portefeuille(c), "État actuel du portefeuille fictif.", {}, []),
    "sans_modification": (lambda c, e: {"decision": "rien", "message": "Entendu, aucun changement n'est appliqué."},
        "Accuse réception d'une demande de ne rien changer, sans modifier le profil ni le portefeuille.", {}, []),
    "preciser_confirmation": (lambda c, e: {"decision": "a_preciser", "message":
        "La proposition reste en attente. Répondez « oui » pour l'appliquer ou « non » pour l'annuler."},
        "Une réponse ambiguë ne vaut pas accord : conserve la proposition en attente et demande une réponse explicite.", {}, []),
}

SYSTEME = """Tu es le CONSEILLER d'AlphaForge, dans une conversation où la personne ajuste son mini-portefeuille FICTIF (simulation éducative).
Ton rôle : comprendre ce qu'elle veut, appeler l'outil qui convient, puis répondre en deux à quatre phrases simples.
- Pour toute demande d'ajout, appelle ajouter_au_portefeuille. Sa décision est définitive : tu ne la contestes pas et tu ne l'adoucis pas.
- Si c'est refusé, présente les alternatives renvoyées par l'outil. Si l'outil indique des réponses du profil à revoir, demande à la personne si elle veut les mettre à jour ; n'appelle confirmer que si elle dit clairement oui.
- Une question d'information appelle consulter_actif, jamais ajouter_au_portefeuille. Une négation ou une réponse ambiguë n'autorise aucune modification.
- Tu ne modifies jamais le profil de ta propre initiative, et tu n'encourages pas à relever une limite de risque.
- Tutoiement interdit : vouvoie. Pas de titre, pas de liste longue, pas de jargon technique, pas d'identifiant de critère.
""" + agents.REGLES_COMMUNES.replace("- Cite les preuves entre crochets avec leur identifiant exact, par exemple [actif:NVDA:max_drawdown] ou [profil:D12].\n", "") \
    .replace("en moins de 180 mots", "en moins de 90 mots")


def specifications() -> list[dict]:
    return [{"toolSpec": {"name": nom, "description": desc, "inputSchema": {"json": {"type": "object", "properties": props, "required": requis}}}}
            for nom, (_, desc, props, requis) in ACTIONS.items()]


def executer(ctx: Contexte, nom: str, entree: dict | None) -> dict:
    if nom not in ACTIONS:
        return {"erreur": f"Outil inconnu : {nom}"}
    if nom not in ("confirmer", "refuser", "consulter_actif", "chercher_par_envie", "voir_le_portefeuille",
                   "sans_modification", "preciser_confirmation"):
        ctx.etat["en_attente"] = None   # une nouvelle demande remplace la proposition restée sans réponse
    try:
        return ACTIONS[nom][0](ctx, entree or {})
    except (ValueError, TypeError, KeyError) as e:
        return {"erreur": f"Entrée invalide pour {nom} : {e}"}


# ---------- Interprète à règles (sans modèle) ----------
_OUI = re.compile(r"^\s*(oui|ok|okay|d'accord|dac|parfait|vas-y|allez-y|allons-y|je confirme|confirme|ca marche|c'est bon|faites-le|fais-le)\b")
_NON = re.compile(r"^\s*(non|pas maintenant|laisse|laissez|annule|annulez|finalement non|je prefere pas)\b")
_REFUS = re.compile(r"\b(?:non|pas maintenant|finalement non|ne (?:modifiez|changez|faites|fais|change|modifie) rien|"
                    r"n'(?:ajoutez|ajoute|appliquez|applique) pas|annule|annulez|je (?:ne )?(?:veux|souhaite) pas)\b")
_HESITATION = re.compile(r"\b(?:peut[- ]etre|pas sur|pas certain|hesite|je ne sais pas|je sais pas|a condition|seulement si)\b")
_NEGATION = re.compile(r"\b(?:ne|pas|jamais|rien|aucune?|sans|non|refus\w*|rejet\w*|evit\w*|exclu\w*)\b|\bn'")
_OUI_COMPLET = re.compile(
    r"(?:oui|ok|okay|d'accord|dac|parfait|vas-y|allez-y|allons-y|je confirme|confirme|ca marche|c'est bon|faites-le|fais-le)"
    r"(?:[\s,;!:.]+(?:merci|s'il vous plait|je confirme|allez-y|vas-y|faites-le|fais-le|c'est bon))*[\s,;!:.]*")
_QUESTION_INFO = re.compile(
    r"\b(?:pourquoi|comment|quel(?:le)?s?|combien|risqu[eé]?|risques|volatilite|rendement|avis|"
    r"explique\w*|renseigne\w*|informe\w*|savoir|comprendre|compare\w*)\b|"
    r"^(?:est-ce|qu'est-ce|c'est quoi|que pens|penses?[- ]|pensez[- ]|parle[- ]moi|parlez[- ]moi|dis[- ]moi|dites[- ]moi)")
_INFORMATION_EXPLICITE = re.compile(
    r"\b(?:pourquoi|comment|quel(?:le)?s?|combien|explique\w*|renseigne\w*|informe\w*|savoir|comprendre|compare\w*)\b|"
    r"(?:est-ce|qu'est-ce|c'est quoi|que pens|dois-je|devrais-je|faut-il|puis-je|penses?[- ]tu|pensez[- ]vous|parle[- ]moi|parlez[- ]moi|dis[- ]moi|dites[- ]moi)")
_AJOUT_EXPLICITE = re.compile(r"\b(?:ajout\w*|mets|mettez|mettre|inclu\w*|je veux|je voudrais|j'aimerais|je souhaite|prends|prenez)\b")


def _confirmation(texte: str) -> str | None:
    """Une approbation ne porte que sur une réponse entière, jamais sur son seul premier mot."""
    q = sans_accents(texte).replace("’", "'").strip()
    if _HESITATION.search(q):
        return "ambigu"
    if _REFUS.search(q) or _NON.search(q):
        return "non"
    if _OUI_COMPLET.fullmatch(q):
        return "oui"
    if _OUI.search(q):
        return "ambigu"
    return None


def _question_information(q: str) -> bool:
    """Une requête grammaticale comme « pouvez-vous ajouter ? » reste une demande d'action explicite."""
    elliptique = bool(re.match(r"^\s*et\s+(?:(?:du|de la|des|de l'|d')\s*)?", q))
    return bool(_INFORMATION_EXPLICITE.search(q) or
                (_QUESTION_INFO.search(q) and not _AJOUT_EXPLICITE.search(q)) or
                ("?" in q and not elliptique and not _AJOUT_EXPLICITE.search(q)))


def _demande_ajout(q: str, ctx: Contexte) -> bool:
    """Un nom seul ou « et du… » peut demander un ajout ; une simple mention dans une phrase ne le demande pas."""
    if _AJOUT_EXPLICITE.search(q):
        return True
    nom = q.strip(" \t?!.,;:")
    nom = re.sub(r"^et\s+", "", nom)
    nom = re.sub(r"^\d+(?:[.,]\d+)?\s*(?:%|pour\s*cent)\s*", "", nom)
    nom = re.sub(r"^(?:(?:du|de la|des|de)\s+|de l'|d')", "", nom)
    return ctx.analyse.trouver(nom) is not None


def interpreter(texte: str, ctx: Contexte) -> list[tuple[str, dict]]:
    """Comprend les demandes simples sans modèle. Renvoie la liste des actions à exécuter (souvent une seule)."""
    q = sans_accents(texte).replace("’", "'")
    if ctx.etat.get("en_attente"):
        confirmation = _confirmation(texte)
        if confirmation == "oui":
            return [("confirmer", {"mots_de_la_personne": texte})]
        if confirmation == "non":
            return [("refuser", {})]
        if confirmation == "ambigu":
            return [("preciser_confirmation", {})]
    negatif = bool(_NEGATION.search(q))
    if not negatif and re.search(r"\b(reviens|revenir|retablis|retablir|annule\w*)\b.*\b(profil|reponses|criteres|mises a jour)\b", q):
        return [("annuler_les_mises_a_jour", {})]
    part = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|pour\s*cent)", q)
    part_pct = float(part.group(1).replace(",", ".")) if part else None
    # La ponctuation de fin de phrase ne fait pas partie d'un symbole ; les points internes de RY.TO restent.
    mots = [m.rstrip(".-&'") for m in re.findall(r"[a-z0-9][a-z0-9.\-&']*", q)]
    trouves: list[str] = []
    for n in (3, 2, 1):
        for i in range(len(mots) - n + 1):
            groupe = " ".join(mots[i:i + n])
            if n == 1 and (len(groupe) < 3 or groupe in _MOTS_COURANTS):
                continue
            tk = ctx.analyse.trouver(groupe)
            if tk and tk not in trouves:
                trouves.append(tk)
    question_info = _question_information(q)
    if negatif:
        return [("consulter_actif", {"actif": t}) for t in trouves[:2]] if question_info and trouves else [("sans_modification", {})]
    if question_info:
        return [("consulter_actif", {"actif": t}) for t in trouves[:2]] or [("consulter_actif", {"actif": texte.strip(" ?!.")})]
    if trouves and re.search(r"\b(retire|retirer|enleve|enlever|supprime|supprimer|sors|sortir)\b", q):
        return [("retirer_du_portefeuille", {"actif": trouves[0]})]
    if trouves:
        if _demande_ajout(q, ctx):
            return [("ajouter_au_portefeuille", {"actif": t, **({"part_pct": part_pct} if part_pct is not None else {})}) for t in trouves[:2]]
        return [("consulter_actif", {"actif": t}) for t in trouves[:2]]
    if ctx.analyse.trouver_par_envie(texte).get("envie"):
        return [("chercher_par_envie", {"envie": texte})]
    if re.search(r"\b(portefeuille|ou en est|recapitul|resume)\b", q):
        return [("voir_le_portefeuille", {})]
    if 0 < len(mots) <= 3 and not re.search(r"\b(bonjour|salut|bonsoir|merci|allo|hello|aide)\b", q):
        return [("ajouter_au_portefeuille", {"actif": texte.strip(" ?!.")})]   # sans doute un nom d'actif : le dire s'il est absent
    return []


_MOTS_COURANTS = {"les", "des", "une", "peu", "pour", "avec", "dans", "plus", "mon", "mes", "que", "qui", "veux", "voudrais", "aimerais",
                  "ajoute", "ajouter", "mettre", "mets", "bien", "aussi", "tout", "tres", "pas", "sur", "par", "est", "sont", "mais",
                  "cent", "part", "titre", "action", "actions", "fonds", "votre", "notre", "leur", "non", "oui", "merci", "bonjour",
                  "ajoutez", "mettez", "prendre", "avoir", "faire", "quelque", "chose", "comme", "vers", "entre", "sans", "sous", "the",
                  "and", "group", "bank", "banque", "energy", "gold", "etf", "inc", "total", "world", "core", "global", "real", "short",
                  "term", "bond", "index", "trust", "fund", "high", "low", "min", "vol", "one", "two", "new", "old", "big", "cash", "or"}


# ---------- Textes du code (sans modèle, ou si le texte du modèle est rejeté) ----------
def _phrase_portefeuille(d: dict) -> str:
    ap, av = d.get("apres") or {}, d.get("avant") or {}
    if ap.get("perte_stress_pct") is None:
        return ""
    return (f" La perte de stress du portefeuille passe de {pct(av.get('perte_stress_pct'))} à {pct(ap['perte_stress_pct'])}, "
            f"pour un budget de {pct(ap['budget_perte_pct'], 0)}.")


def _phrase_maj(m: dict) -> str:
    if not m:
        return ""
    if not m.get("possible"):
        return " " + m.get("raison", "")
    quoi = " ; ".join(f"« {c['nom']} » : {c['avant_libelle']} → {c['apres_libelle']}" for c in m["changements"])
    return (f" Pour l'inclure, il faudrait que vous mettiez à jour : {quoi}. " + (m.get("avertissement") or "") +
            " Souhaitez-vous le faire ?")


def rediger(nom: str, d: dict) -> str:
    """Réponse courte, en clair, à partir de la sortie d'une action. Tous les chiffres viennent de cette sortie."""
    if "erreur" in d:
        return d["erreur"]
    if d.get("decision") in ("rien", "impossible", "a_preciser") and d.get("message"):
        return d["message"]
    dec = d.get("decision")
    if nom == "ajouter_au_portefeuille":
        if dec == "absent":
            sugg = ", ".join(x["nom"] for x in d.get("suggestions", []))
            return d["message"] + (f" Vouliez-vous dire : {sugg} ?" if sugg else " Je ne peux rien en dire sans données.")
        if dec == "applicable":
            reserve = (" À surveiller : " + _suite(d["raisons"][0])) if d.get("a_surveiller") and d.get("raisons") else ""
            return f"C'est fait : {d['nom']} entre dans votre portefeuille fictif pour {pct(d['part_pct'], 0)}.{_phrase_portefeuille(d)}{reserve}"
        if dec == "reduit":
            return (f"{pct(d['part_demandee_pct'], 0)} de {d['nom']}, c'est plus que ce que votre profil permet : {_suite(d['raisons'][0])} "
                    f"Je peux l'ajouter pour {pct(d['part_pct'], 0)}, ce qui reste cohérent. Voulez-vous que je le fasse ?")
        texte = f"{d['nom']} n'est pas compatible avec votre profil : {_suite(d['raisons'][0]) if d.get('raisons') else 'il dépasse vos limites.'}"
        if d.get("alternatives"):
            texte += " Plus proche de vos critères : " + " ; ".join(f"{x['nom']} ({x['lien']})" for x in d["alternatives"]) + "."
        return texte + _phrase_maj(d.get("mises_a_jour"))
    if nom == "chercher_par_envie":
        if not d.get("envie"):
            return ("Je n'ai pas reconnu de titre, de thème ou de région dans votre message. Donnez-moi un nom d'entreprise ou de fonds, "
                    "ou une envie comme « plus de technologie » ou « de l'or ».")
        if not d["nb_compatibles"]:
            return (f"{d['nb_actifs']} actifs de l'univers correspondent à cette envie, mais aucun n'est compatible avec votre profil tel "
                    "qu'il est. Nommez-en un et je vous dirai quelle réponse il faudrait revoir.")
        compat = [x for x in d["actifs"] if x["verdict"] == "compatible"]
        k = d["nb_compatibles"]
        return ((f"{k} actifs compatibles avec votre profil correspondent à cette envie. Les plus proches : " if k > 1 else
                 "Un actif compatible avec votre profil correspond à cette envie : ")
                + " ; ".join(f"{x['nom']} ({x['ticker']})" for x in compat[:4]) + (". Lequel voulez-vous ajouter ?" if k > 1 else ". Voulez-vous l'ajouter ?"))
    if nom == "consulter_actif":
        if d.get("verdict") == "absent":
            return d["message"]
        exp = d.get("explication") or {}
        raisons = exp.get("retient") or exp.get("soutient") or []
        resume = exp.get("resume") or d.get("message") or d.get("libelle_verdict", "")
        return f"{d.get('nom') or d['ticker']} : {resume}" + (" " + _suite(raisons[0]) if raisons else "")
    if nom == "retirer_du_portefeuille":
        return d.get("message") or f"{d['ticker']} est retiré ; le portefeuille est recalculé."
    if nom == "proposer_mise_a_jour_du_profil":
        if dec != "a_confirmer":
            return d["message"]
        c = d["changements"][0]
        n = d["ce_qui_changerait"].get("actifs_qui_changent_de_verdict")
        return (f"Vous voulez revoir « {c['nom']} » : {c['avant_libelle']} → {c['apres_libelle']}. "
                + (f"{n} actifs changeraient de verdict. " if n is not None else "") + "Confirmez-vous cette mise à jour ?")
    if nom == "confirmer":
        if dec == "mis_a_jour":
            quoi = " ; ".join(f"« {c['nom']} » : {c['apres_libelle']}" for c in d["changements"])
            suite = (" " + rediger("ajouter_au_portefeuille", d["ajout"])) if d.get("ajout") else " Le portefeuille est recalculé."
            return f"Votre profil est mis à jour ({quoi}).{suite}"
        if dec in ("applicable", "reduit", "refuse", "absent"):
            return rediger("ajouter_au_portefeuille", d)
        return d.get("message", "")
    if nom == "annuler_les_mises_a_jour":
        return f"Vos {d['nb_reponses_retablies']} réponses d'origine sont rétablies ; le portefeuille est recalculé."
    if nom == "voir_le_portefeuille":
        if "erreur" in d:
            return d["erreur"]
        return (f"Votre portefeuille fictif compte {len(d['positions'])} positions. Perte de stress : {pct(d['perte_stress_pct'])} pour un budget "
                f"de {pct(d['budget_perte_pct'], 0)}." + (f" Ajouté à votre demande : {', '.join(d['ajouts'])}." if d["ajouts"] else ""))
    return d.get("message", "")


def tour(ctx: Contexte, texte: str, modele=None) -> dict:
    """Un tour de conversation. Renvoie le message de l'assistant ; l'état (ajouts, mises à jour, attente) est modifié en place."""
    etat = ctx.etat
    historique = [m for m in etat["messages"][-8:]]
    etat["messages"].append({"role": "user", "texte": texte})
    ctx.noter("message", longueur=len(texte))
    appels: list[dict] = []
    source = "code"

    def executer_tour(nom, entree):
        # L'accord vient de la phrase réellement reçue, jamais d'une citation proposée par le modèle.
        if nom == "confirmer":
            accord = _confirmation(texte)
            if accord == "non":
                return executer(ctx, "refuser", {})
            if accord != "oui" and ctx.etat.get("en_attente"):
                return executer(ctx, "preciser_confirmation", {})
            entree = {"mots_de_la_personne": texte}
        q = sans_accents(texte).replace("’", "'")
        if nom == "ajouter_au_portefeuille":
            part_dite = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|pour\s*cent)", q)
            if part_dite and float(part_dite.group(1).replace(",", ".")) == 0:
                return ajouter(ctx, (entree or {}).get("actif", ""), 0)
        if nom in ("ajouter_au_portefeuille", "retirer_du_portefeuille", "proposer_mise_a_jour_du_profil", "annuler_les_mises_a_jour"):
            if _NEGATION.search(q) or _question_information(q):
                if nom == "ajouter_au_portefeuille" and _question_information(q):
                    fiche = consulter_actif(ctx, (entree or {}).get("actif", ""))
                    return {"decision": "rien", "message": rediger("consulter_actif", fiche), "fiche": fiche}
                return executer(ctx, "sans_modification", {})
        return executer(ctx, nom, entree)

    if modele is not None:
        attente = etat.get("en_attente")
        invite = texte + (f"\n\n[Proposition en attente de réponse : {attente['question']}]" if attente else "")
        rep = agents.dialoguer("conseiller", invite, ctx.analyse, ctx.journal, modele, systeme=SYSTEME, specs=specifications(),
                               executer=executer_tour, historique=historique, mention=False,
                               texte_secours=lambda aps: "\n\n".join(rediger(a["outil"], a["sortie"]) for a in aps) or "")
        appels = rep["appels"]
        reponse, source = rep["texte"], rep["source"]
        if not reponse.strip():
            appels = []
    if not appels and (modele is None or not reponse.strip()):
        actions = interpreter(texte, ctx)
        appels = [{"outil": nom, "entree": e, "sortie": executer(ctx, nom, e), "par": "code"} for nom, e in actions]
        reponse = "\n\n".join(rediger(a["outil"], a["sortie"]) for a in appels) or \
            (BIENVENUE if re.search(r"\b(bonjour|salut|bonsoir|allo|hello|aide)\b", sans_accents(texte)) else rediger("chercher_par_envie", {"envie": None}))
        source = "code"
    fid = fidelite.verifier(reponse, [a["sortie"] for a in appels] + [m["texte"] for m in historique], texte, ctx.analyse.uni.tickers())
    cartes = {}
    for a in appels:
        s = a["sortie"]
        if s.get("alternatives"):
            cartes["alternatives"] = s["alternatives"]
        if a["outil"] == "chercher_par_envie" and s.get("actifs"):
            cartes["alternatives"] = [{"ticker": x["ticker"], "nom": x["nom"], "score": x["score"], "poids_max_pct": x["poids_max_pct"],
                                       "lien": x["libelle_verdict"].lower()} for x in s["actifs"] if x["verdict"] == "compatible"][:4]
    message = {"role": "assistant", "texte": reponse, "cartes": cartes, "source": source, "appels": appels, "fidelite": fid,
               "gouvernance": gouvernance.controler_texte(reponse)}
    etat["messages"].append(message)
    return message
