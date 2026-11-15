"""Contrat fermé de restitution et contrôle de provenance numérique (code, pas un agent).

Le modèle sélectionne des identifiants de fragments rédigés par le code ; il ne fournit aucune prose financière
affichable. Le contrôle numérique reste un diagnostic de provenance, pas une vérification du sens des phrases.
"""
from __future__ import annotations

import json
import re

_NOMBRE = re.compile(r"(?<![\w.,:/\-])[-−]?\d+(?:[   ]\d{3})*(?:[.,]\d+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:.+\-Z]+)?")
_ID_CRITERE = re.compile(r"\b(?:[A-H]\d{1,2}[A-Z]?|X\d+)\b")
TOUJOURS_ADMIS = {100.0}  # « sur 100 », « 100 % »


def selection_restitution(texte: str, details: list[dict]) -> dict:
    """N'accepte que {"details": [identifiants connus]}, sans champ libre ni identifiant répété.

    Les verdicts et avertissements obligatoires ne figurent pas dans cette sélection : le code les impose
    même si le modèle ne choisit aucun détail. Aucun essai de compréhension sémantique d'une prose libre.
    """
    def sans_doublons(paires):
        objet = {}
        for cle, valeur in paires:
            if cle in objet:
                raise ValueError("Champ JSON répété.")
            objet[cle] = valeur
        return objet

    try:
        obj = json.loads(texte, object_pairs_hook=sans_doublons)
    except (ValueError, TypeError):
        return {"valide": False, "details": [], "motif": "La restitution doit être un objet JSON, sans prose libre."}
    if not isinstance(obj, dict) or set(obj) != {"details"}:
        return {"valide": False, "details": [], "motif": "Seul le champ « details » est autorisé."}
    ids = obj["details"]
    connus = {d["id"] for d in details}
    if (not isinstance(ids, list) or len(ids) > 6 or any(not isinstance(i, str) for i in ids)
            or len(ids) != len(set(ids)) or any(i not in connus for i in ids)):
        return {"valide": False, "details": [], "motif": "Choisir au plus six identifiants distincts du catalogue courant."}
    return {"valide": True, "details": ids, "motif": None}


def _nettoyer(texte: str, tickers=()) -> str:
    t = re.sub(r"\[[^\]]*\]", " ", texte)            # identifiants de preuve cités entre crochets
    t = _DATE.sub(lambda m: " " + m.group(0)[:4] + " ", t)  # une date citée compte pour son année
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"(?m)^\s*\d+[.)]\s", " ", t)          # numérotation de liste
    for tk in sorted(tickers, key=len, reverse=True):  # un ticker peut contenir des chiffres (005930.KS)
        t = t.replace(tk, " ")
    return _ID_CRITERE.sub(" ", t)


def _lire(brut: str) -> tuple[float, int]:
    s = brut.replace("−", "-").replace(" ", "").replace(" ", "").replace(" ", "")
    decimales = len(s.split(",")[1]) if "," in s else len(s.split(".")[1]) if "." in s else 0
    return abs(float(s.replace(",", "."))), decimales


def nombres_du_texte(texte: str, tickers=()) -> list[tuple[str, float, int]]:
    return [(m.group(0), *_lire(m.group(0))) for m in _NOMBRE.finditer(_nettoyer(texte, tickers))]


def nombres_admis(*sorties) -> set[float]:
    """Tous les nombres présents dans les sorties d'outils : valeurs numériques et nombres écrits dans les textes."""
    admis: set[float] = set(TOUJOURS_ADMIS)

    def parcourir(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            admis.add(abs(float(x)))
        elif isinstance(x, str):
            for d in _DATE.findall(x):                    # une date n'admet que son année, pas « 11 » ni « 12 »
                admis.add(float(d[:4]))
            x = _DATE.sub(" ", x)
            for m in _NOMBRE.finditer(x):
                admis.add(_lire(m.group(0))[0])
            for m in re.finditer(r"\d+(?:\.\d+)?", x):   # dates, identifiants, décimales à l'anglaise
                admis.add(float(m.group(0)))
        elif isinstance(x, dict):
            for k, v in x.items():
                if k in ("lignes", "positions") and isinstance(v, list):
                    # Le texte du code annonce le nombre de positions de la sortie compacte.
                    admis.add(float(len(v)))
                parcourir(k)
                parcourir(v)
        elif isinstance(x, (list, tuple, set)):
            for v in x:
                parcourir(v)

    for s in sorties:
        parcourir(s)
    return admis


def verifier(texte: str, sorties: list, question: str = "", tickers=()) -> dict:
    """Renvoie {fidele, nombres_verifies, sans_origine}. Un nombre est admis s'il égale une valeur d'outil à la
    précision où il est écrit (67,2 admet 67.23 ; 67 admet 67.4), ou s'il figure dans la question posée."""
    admis = nombres_admis(*sorties, question)
    sans_origine, verifies = [], 0
    for brut, valeur, decimales in nombres_du_texte(texte, tickers):
        tolerance = 0.5 * 10 ** (-decimales) + 1e-9
        if any(abs(round(a, decimales) - valeur) <= 1e-9 or abs(a - valeur) <= tolerance for a in admis):
            verifies += 1
        else:
            sans_origine.append(brut.strip())
    return {"fidele": not sans_origine, "nombres_verifies": verifies, "sans_origine": sans_origine}
