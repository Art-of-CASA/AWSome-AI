"""Tableau REPRODUCTIBLE des résultats par persona (remplace les anciens tableaux sans script).

    python scripts/tableau_personas.py            écrit docs/resultats_personas.md
"""
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "mvp_profil"))

from recommandation import chargement as ch  # noqa: E402
from recommandation.analyse import Analyse  # noqa: E402
from recommandation.appariement import pct  # noqa: E402

uni = ch.univers()
L = ["# Résultats par persona (générés)", "",
     f"Produit par `python scripts/tableau_personas.py` sur {len(uni)} actifs, données au {uni.date_donnees()}. "
     "Personas fictifs de l'énoncé, complétés par des réponses simulées (voir `mvp_profil/personas/`). "
     "Simulation éducative : aucun conseil financier. Les mesures décrivent le passé, elles ne prédisent rien.", "",
     "## Verdicts par actif", "", "| Persona | Budget de perte | Compatibles | À examiner | Peu adaptés | Exclus | Données insuffisantes |", "|---|---|---|---|---|---|---|"]
analyses = {n: Analyse(ch.charger_persona(n)["profil"], nom=n.capitalize()) for n in ch.personas_disponibles()}
for n, a in analyses.items():
    d = a.synthese()["decompte"]
    L.append(f"| {a.nom} | {pct(a.contraintes['budget_perte_pct'], 0)} | {d['compatible']} | {d['a_examiner']} | {d['peu_adapte']} | {d['exclu']} | {d['donnees_insuffisantes']} |")
L += ["", "## Mini-portefeuille fictif", "", "| Persona | Positions | Poche de croissance | Volatilité | Perte de stress | Tension | Scénario fictif de krach |", "|---|---|---|---|---|---|---|"]
for a in analyses.values():
    pf = a.portefeuille
    L.append(f"| {a.nom} | {pf['nb_positions']} | {pct(pf['part_croissance_pct'])} | {pct(pf['mesures']['volatilite_pct'])} | "
             f"{pct(pf['perte_stress_pct'])} | {pf['ratio_tension']:.2f} ({pf['etat_tension'].replace('_', ' ')}) | {pct(pf['stress']['scenario_fictif_krach_pct'])} |")
for a in analyses.values():
    pf = a.portefeuille
    L += ["", f"### {a.nom}", "", a.contraintes["phrase"], "", "| Actif | Nom | Poche | Poids | Score |", "|---|---|---|---|---|"]
    L += [f"| {l['ticker']} | {l['nom']} | {l['poche']} | {pct(l['poids_pct'])} | {l['score']} |" for l in pf["lignes"]]
    if pf["a_confirmer"]:
        L += ["", "À confirmer avec la personne : " + " ; ".join(pf["a_confirmer"]) + "."]
L += ["", "## Fiche d'un actif très médiatisé (NVDA)", "", "| Persona | Verdict | Score | Poids maximal compatible |", "|---|---|---|---|"]
for a in analyses.values():
    r = a.resultats["NVDA"]
    L.append(f"| {a.nom} | {r['libelle_verdict']} | {r['score'] if r['score'] is not None else '—'} | {pct(r.get('poids_max_pct'), 0)} |")
L += ["", "## Demande d'un titre très médiatisé (NVDA)", "", "| Persona | Part demandée | Verdict | Part maximale compatible | Perte de stress avant → après |", "|---|---|---|---|---|"]
for a in analyses.values():
    for part in (5, 20):
        v = a.demande("NVDA", part)
        suite = f"{pct(v['perte_stress_avant_pct'])} → {pct(v['perte_stress_apres_pct'])}" if v.get("perte_stress_apres_pct") is not None else "—"
        L.append(f"| {a.nom} | {part} % | {v['libelle_verdict']} | {pct(v.get('part_max_compatible_pct'), 0)} | {suite} |")
(RACINE / "docs" / "resultats_personas.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
