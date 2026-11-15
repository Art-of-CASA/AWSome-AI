"""Outils communs des tests de la recommandation (hors ligne, sans AWS, sans modèle réel)."""
import os
import sys
from pathlib import Path

import tempfile

SITE = Path(__file__).resolve().parent            # mvp_profil
RACINE = SITE.parent
sys.path.insert(0, str(SITE))
os.environ.setdefault("ALPHAFORGE_SANS_MODELE", "1")
os.environ.setdefault("ALPHAFORGE_TRACES_LOCALES", "1")     # jamais de DynamoDB pendant les tests
os.environ.setdefault("ALPHAFORGE_DOSSIER_TRACES", tempfile.mkdtemp(prefix="alphaforge_traces_"))

from recommandation import chargement as ch  # noqa: E402
from recommandation.analyse import Analyse  # noqa: E402

_cache = {}


def analyse(nom: str) -> Analyse:
    if nom not in _cache:
        _cache[nom] = Analyse(ch.charger_persona(nom)["profil"], nom=nom.capitalize())
    return _cache[nom]


def verifier(condition, message):
    if not condition:
        raise AssertionError(message)
