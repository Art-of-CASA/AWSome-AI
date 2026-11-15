"""Chargement des données et de la configuration, en lecture seule.

L'univers n'est JAMAIS codé en dur : tout vient de donnees/actifs.csv (copie de data_extended/asset_criteria.csv),
relu au démarrage. Ajouter ou retirer une ligne puis relancer scripts/build_donnees_recommandation.py suffit ;
aucun ticker ni nombre d'actifs n'apparaît dans le code.
Le profil (mvp_profil/) est importé en lecture : rien n'y est écrit.
"""
from __future__ import annotations

import csv
import json
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path

PAQUET = Path(__file__).resolve().parent          # mvp_profil/recommandation (ou app/recommandation une fois déployé)
PROFIL = PAQUET.parent                             # modules du profil, lus sans les modifier
DONNEES = PAQUET / "donnees"                       # préparées par scripts/build_donnees_recommandation.py

if str(PROFIL) not in sys.path:  # les modules du profil s'importent entre eux sans préfixe
    sys.path.insert(0, str(PROFIL))

# Colonnes sans lesquelles un actif ne peut pas être évalué.
COLONNES_REQUISES = ("ticker", "name", "asset_class", "role", "vol_cad", "max_drawdown", "stress_loss",
                     "speculative", "complexity", "access_canada", "kw_exclusions", "kw_risque_pays",
                     "max_severity", "fossil_categorie", "last_date")
VIDES = ("", "nan", "NaN", "None")
NON_APPLICABLE = ("non_applicable", "non applicable")


def _json(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def hypotheses() -> dict:
    return _json(DONNEES / "hypotheses_recommandation.json")


@lru_cache(maxsize=1)
def correspondances() -> dict:
    return _json(DONNEES / "correspondances.json")


@lru_cache(maxsize=1)
def regles() -> dict:
    return _json(DONNEES / "regles_appariement.json")


@lru_cache(maxsize=1)
def sources_colonnes() -> dict:
    return _json(DONNEES / "sources_colonnes.json")


def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(texte).casefold()) if not unicodedata.combining(c))


def nombre(valeur) -> float | None:
    """Nombre, ou None si la cellule est vide : une donnée manquante n'est jamais remplacée par zéro."""
    if valeur is None or str(valeur).strip() in VIDES:
        return None
    try:
        x = float(valeur)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def etiquettes(valeur) -> list[str]:
    """Colonnes à plusieurs étiquettes, séparées par « ; »."""
    return [v.strip() for v in str(valeur or "").split(";") if v.strip()]


def vrai(valeur) -> bool:
    return str(valeur).strip().lower() == "true"


class Univers:
    """Les actifs tels que le fichier les décrit, plus ce qui manque pour chacun."""

    def __init__(self, chemin: Path | None = None):
        self.chemin = Path(chemin or DONNEES / "actifs.csv")
        with self.chemin.open(encoding="utf-8", newline="") as f:
            lecteur = csv.DictReader(f)
            self.colonnes = list(lecteur.fieldnames or [])
            lignes = list(lecteur)
        absentes = [c for c in COLONNES_REQUISES if c not in self.colonnes]
        if absentes:
            raise ValueError(f"Colonnes requises absentes de {self.chemin.name} : {', '.join(absentes)}")
        self.actifs: dict[str, dict] = {}
        self.incomplets: dict[str, list[str]] = {}
        for ligne in lignes:
            tk = (ligne.get("ticker") or "").strip()
            if not tk:
                continue
            self.actifs[tk] = ligne
            manque = [c for c in COLONNES_REQUISES if str(ligne.get(c, "")).strip() in VIDES]
            if manque:
                self.incomplets[tk] = manque

    def __len__(self) -> int:
        return len(self.actifs)

    def __contains__(self, ticker: str) -> bool:
        return ticker in self.actifs

    def __getitem__(self, ticker: str) -> dict:
        return self.actifs[ticker]

    def tickers(self) -> list[str]:
        return list(self.actifs)

    def date_donnees(self) -> str:
        return max((a.get("last_date") or "" for a in self.actifs.values()), default="")


@lru_cache(maxsize=4)
def univers(chemin: str | None = None) -> Univers:
    return Univers(Path(chemin) if chemin else None)


# ---------- Prix en CAD (pour mesurer un portefeuille) ----------

@lru_cache(maxsize=1)
def prix_cad():
    """Tableau date × ticker des prix ajustés en CAD, précalculé par scripts/build_donnees_recommandation.py."""
    import pandas as pd

    return pd.read_csv(DONNEES / "prix_cad.csv", index_col=0, parse_dates=True)


@lru_cache(maxsize=1)
def rendements():
    return prix_cad().pct_change(fill_method=None)


# ---------- Transparence des FNB ----------

@lru_cache(maxsize=1)
def _fnb() -> dict:
    return _json(DONNEES / "fnb.json")


def positions_fnb() -> dict[str, dict[str, float]]:
    """FNB -> {ticker de l'univers: poids}. Seules les principales positions sont connues (exposition minimale)."""
    return _fnb()["positions"]


def secteurs_fnb() -> dict[str, dict[str, float]]:
    """FNB -> {secteur GICS: poids}."""
    return _fnb()["secteurs"]


# ---------- Profils ----------

def personas_disponibles() -> list[str]:
    return sorted(p.stem for p in (PROFIL / "personas").glob("*.json"))


def charger_persona(nom: str) -> dict:
    """Persona fictif de démonstration : {nom, description, profil}. Lecture seule."""
    return _json(PROFIL / "personas" / f"{nom}.json")


def profil_depuis_export(export: dict) -> tuple[dict, list[dict]]:
    """Accepte l'export JSON du site (clés profil et criteres_dynamiques) ou un persona."""
    return export.get("profil") or {}, list(export.get("criteres_dynamiques") or [])
