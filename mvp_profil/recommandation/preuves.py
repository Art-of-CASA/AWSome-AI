"""Registre de preuves : chaque conclusion renvoie à une donnée datée, une réponse ou une hypothèse écrite.

Les identifiants sont lisibles et stables : « actif:NVDA:vol_cad », « profil:D12 », « hypothese:tension »,
« calcul:portefeuille:perte_stress ». Deux exécutions sur les mêmes données donnent les mêmes identifiants.
On dit « traçable » : la preuve montre d'où vient un chiffre, elle ne prouve pas que la règle est la bonne.
"""
from __future__ import annotations

from .chargement import NON_APPLICABLE, VIDES, hypotheses, sources_colonnes


def _famille(colonne: str) -> dict:
    src = sources_colonnes()
    for f in src["familles"]:
        if colonne in f["colonnes"]:
            return f
    return src["defaut"]


class Registre:
    def __init__(self):
        self.fiches: dict[str, dict] = {}

    def actif(self, actif: dict, colonne: str) -> str:
        """Preuve côté actif : colonne, valeur, date, fichier, source, conditions d'utilisation."""
        tk = actif["ticker"]
        ident = f"actif:{tk}:{colonne}"
        if ident not in self.fiches:
            f = _famille(colonne)
            brut = str(actif.get(colonne, "")).strip()
            etat = "DONNÉE_MANQUANTE" if brut in VIDES else "NON_APPLICABLE" if brut in NON_APPLICABLE else "CONNU"
            self.fiches[ident] = {
                "id": ident, "type": "actif", "ticker": tk, "colonne": colonne, "valeur": brut or None, "etat": etat,
                "date": actif.get("last_date") if f["date"] == "last_date" else f["date"],
                "fichier": f["fichier"], "source": f["source"], "conditions": f["conditions"], "nature": f["nature"]}
        return ident

    def profil(self, critere: str, entree: dict) -> str:
        """Preuve côté profil : la réponse, sa source, la citation exacte et son statut."""
        ident = f"profil:{critere}"
        self.fiches.setdefault(ident, {
            "id": ident, "type": "profil", "critere": critere, "valeur": entree.get("valeur"),
            "etat": entree.get("etat"), "source": entree.get("source"), "citation": entree.get("citation") or None,
            "statut": entree.get("statut"), "nature": entree.get("nature", "réponse de la personne")})
        return ident

    def hypothese(self, cle: str) -> str:
        """Preuve d'un seuil : sa valeur et la note qui l'explique, dans config/hypotheses_recommandation.json."""
        ident = f"hypothese:{cle}"
        if ident not in self.fiches:
            h = hypotheses()
            self.fiches[ident] = {"id": ident, "type": "hypothese", "cle": cle, "valeur": h.get(cle),
                                  "explication": h.get("_" + cle), "fichier": "config/hypotheses_recommandation.json",
                                  "nature": "hypothèse d'équipe, ajustable"}
        return ident

    def calcul(self, nom: str, valeur, methode: str, periode: str | None = None) -> str:
        ident = f"calcul:{nom}"
        self.fiches[ident] = {"id": ident, "type": "calcul", "valeur": valeur, "methode": methode,
                              "periode": periode, "nature": "calcul sur données historiques, pas une prévision"}
        return ident

    def lire(self, ident: str) -> dict | None:
        return self.fiches.get(ident)

    def extrait(self, idents) -> list[dict]:
        return [self.fiches[i] for i in dict.fromkeys(idents) if i in self.fiches]
