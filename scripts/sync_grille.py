"""Aligne la grille config/criteres_appariement.csv sur mvp_profil/criteres.py (SOURCE DE VÉRITÉ des valeurs du profil).

- La colonne valeurs_profil de chaque critère présent dans criteres.py est réécrite avec ses valeurs exactes.
- La colonne « demande » dit si le critère est posé à l'utilisateur (oui), mesuré (mesure), calculé (calcule), ou
  seulement prévu par la grille (non).
- Les critères du code absents de la grille (B1R, D8O) y sont ajoutés ; D13 (ancien nom de D8O) est renommé.
Lancer après toute modification de criteres.py : python scripts/sync_grille.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mvp_profil"))
from criteres import CRITERES, MESURES  # noqa: E402

CSV = ROOT / "config" / "criteres_appariement.csv"
NIVEAU = "Vérifié sur le PORTEFEUILLE (pas actif par actif)"
# Règles réécrites : elles citaient des valeurs d'actif disparues ou s'appliquaient actif par actif.
REGLES = {
    "A2": f"{NIVEAU} : l'horizon fixe le plafond de capacité (hypotheses_profil.json), donc le budget de perte ; horizon_min_years reste une information par actif",
    "A3": "coussin_securite : rôle liquidites seulement ; projet_date : liquidites et obligations_amortisseur près de l'échéance ; revenu : préférence satellite_revenu ; croissance : tous les rôles dans les plafonds",
    "A5": "Moins de 3 mois : un cran de capacité en moins ; aucun : alerte et niveau plafonné à 2 (niveau du portefeuille)",
    "A9": "Montant à retirer dans moins de 3 ans : poche réservée de rôle liquidites ou obligations_amortisseur",
    "B1": f"{NIVEAU} : tension = perte de stress du portefeuille ÷ budget de perte (synthese.py) : <0,8 cohérent ; 0,8-1 à surveiller ; >1 en tension",
    "B5": f"{NIVEAU} : volatilité du portefeuille <= plafond de la classe acceptée (8, 15, 25 %)",
    "B7": f"{NIVEAU} : durée sous l'eau du portefeuille <= durée supportable ; kw_recuperation (du sommet au retour) reste une information par actif ; baisse_en_cours et jamais_recupere sont signalés",
    "C1": "complexity de l'actif <= score du quiz + 1 (score 0 : complexité 1 seulement) ; le score est gardé avec le niveau",
    "F2": "Voir config/correspondances.json (F2) : exclure_emergents exclut marche_emergent et exposition_chine, plafonne marche_emergent_partiel",
    "E1": "Voir config/correspondances.json (E1) : exclusion par fossil_categorie ; les FNB exposés (energie_fossile_via_fonds) sont plafonnés, pas exclus",
}
NOUVEAUX = {
    "B1R": ["Tolérance au risque", "Réaction déclarée à une baisse de 20 %", "Vos 10 000 $ deviennent 8 000 $ en trois mois : que faites-vous ?",
            "(profil seulement)", "vendre_tout : la tolérance déclarée est plafonnée à −20 % ; contradiction avec B1 : question de clarification (R1, R1b)",
            "calcul_capacite", "Tous", "profil seulement"],
}

with CSV.open(encoding="utf-8", newline="") as f:
    lignes = list(csv.DictReader(f))
champs = [c for c in lignes[0].keys() if c != "demande"]
for l in lignes:
    if l["id"] == "D13":
        l["id"] = "D8O"
        l["critere_profil"] = "Attrait observé pour un titre médiatisé (test)"
ids = [l["id"] for l in lignes]
for cid, (bloc, nom, question, actif, regle, typ, personas, donnees) in NOUVEAUX.items():
    if cid not in ids:
        pos = ids.index("B1")
        lignes.insert(pos, dict(id=cid, bloc=bloc, critere_profil=nom, question_exemple=question, valeurs_profil="",
                                critere_actif=actif, regle_appariement=regle, type_regle=typ, personas=personas, donnees=donnees))
        ids.insert(pos, cid)
for l in lignes:
    cid = l["id"]
    if cid in CRITERES:
        l["valeurs_profil"] = ", ".join(CRITERES[cid]["valeurs"])
        l["demande"] = "mesure" if cid in MESURES else "oui"
    else:
        l["demande"] = "calcule" if cid in ("H2", "H3") else "non"
    if cid in REGLES:
        l["regle_appariement"] = REGLES[cid]
manquants = [c for c in CRITERES if c not in ids]
assert not manquants, f"Critères du code absents de la grille : {manquants}"
with CSV.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=champs[:5] + ["demande"] + champs[5:], lineterminator="\n")
    w.writeheader()
    w.writerows(lignes)
print(f"{CSV.relative_to(ROOT)} : {len(lignes)} critères, dont {sum(l['demande'] in ('oui', 'mesure') for l in lignes)} "
      f"dans le profil ; non demandés : {', '.join(l['id'] for l in lignes if l['demande'] == 'non')}")
