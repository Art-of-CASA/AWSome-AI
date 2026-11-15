"""Vérificateur de fidélité (code, pas un agent) : chaque chiffre du texte final doit exister dans une sortie d'outil.

Un texte qui contient un nombre sans origine est REJETÉ : il n'atteint pas l'écran. Le vérificateur ne juge pas
le sens de la phrase ; il garantit seulement qu'aucun chiffre n'a été inventé ou recalculé par le modèle.
"""
from __future__ import annotations

import re

_NOMBRE = re.compile(r"(?<![\w.,:/\-])[-−]?\d+(?:[   ]\d{3})*(?:[.,]\d+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:.+\-Z]+)?")
_ID_CRITERE = re.compile(r"\b(?:[A-H]\d{1,2}[A-Z]?|X\d+)\b")
TOUJOURS_ADMIS = {100.0}  # « sur 100 », « 100 % »


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
