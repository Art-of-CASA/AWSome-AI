"""Expérience : et si un modèle construisait le portefeuille seul, de A à Z ?

Le 15 novembre 2026, Claude Sonnet 5.5 (Amazon Bedrock) a reçu, pour chaque persona, le profil en clair, la synthèse
calculée (budget de perte, part d'actions indicative) et l'univers complet (111 actifs, 16 colonnes). Consigne : un
portefeuille de 5 à 12 positions respectant TOUTES les contraintes, en JSON. Trois essais par persona, sans outil.
Les réponses sont recopiées ci-dessous telles quelles. Ce script les juge avec les contrôles du moteur.

    python scripts/experience_modele_seul.py        écrit docs/experience_modele_seul.md
"""
import os
import statistics
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "mvp_profil"))
os.environ.setdefault("ALPHAFORGE_TRACES_LOCALES", "1")

from recommandation import chargement as ch, contraintes as C, mesures as M, portefeuille as P  # noqa: E402
from recommandation.analyse import Analyse  # noqa: E402
from recommandation.appariement import pct  # noqa: E402
from recommandation.preuves import Registre  # noqa: E402

# (persona, durée en s, jetons de sortie, perte de stress estimée par le modèle, positions)
REPONSES = [
    ("amira", 14.3, 1614, 38.5, [("QQQ", 18), ("ESGV", 17), ("VT", 10), ("SMH", 10), ("MSFT", 10), ("CSU.TO", 7), ("2330.TW", 8), ("ASML.AS", 5), ("NVDA", 5), ("BTC-USD", 5), ("GLD", 5)]),
    ("amira", 14.3, 1949, 37.9, [("QQQ", 18), ("ESGV", 15), ("VT", 10), ("SMH", 8), ("MSFT", 10), ("CSU.TO", 7), ("ASML.AS", 7), ("2330.TW", 7), ("NVDA", 5), ("BTC-USD", 5), ("GLD", 4), ("AGG", 4)]),
    ("amira", 29.1, 1691, 37.0, [("QQQ", 15), ("ESGV", 15), ("VT", 12), ("SMH", 8), ("MSFT", 10), ("CSU.TO", 6), ("2330.TW", 7), ("ASML.AS", 7), ("NVDA", 6), ("BTC-USD", 4), ("GLD", 5), ("AGG", 5)]),
    ("mateo", 29.1, 1847, 15.5, [("ZLB.TO", 14), ("ESGV", 12), ("QQQ", 6), ("CNR.TO", 6), ("FTS.TO", 5), ("RY.TO", 5), ("XBB.TO", 20), ("XSB.TO", 16), ("CLF.TO", 10), ("XSH.TO", 6)]),
    ("mateo", 29.1, 1903, 15.5, [("ZLB.TO", 12), ("USMV", 8), ("ESGV", 8), ("RY.TO", 6), ("CNR.TO", 5), ("FTS.TO", 5), ("ASML.AS", 3), ("XBB.TO", 25), ("XSB.TO", 15), ("CLF.TO", 8), ("ZST.TO", 5)]),
    ("mateo", 29.1, 1977, 16.0, [("ZLB.TO", 14), ("ESGV", 10), ("USMV", 6), ("RY.TO", 5), ("CNR.TO", 5), ("FTS.TO", 5), ("2330.TW", 3), ("XBB.TO", 22), ("XGB.TO", 10), ("XSB.TO", 12), ("ZST.TO", 8)]),
    ("robert", 29.1, 1833, 11.9, [("XBB.TO", 20), ("XSB.TO", 14), ("CLF.TO", 14), ("XSH.TO", 8), ("CASH.TO", 5), ("GLD", 5), ("ZLB.TO", 10), ("VDY.TO", 7), ("RY.TO", 4), ("JNJ", 5), ("KO", 4), ("USMV", 4)]),
    ("robert", 29.1, 1841, 11.7, [("XBB.TO", 22), ("XSB.TO", 16), ("CLF.TO", 11), ("XSH.TO", 8), ("ZST.TO", 6), ("GLD", 5), ("ZLB.TO", 12), ("VDY.TO", 8), ("USMV", 5), ("JNJ", 4), ("RY.TO", 3)]),
    ("robert", 29.1, 1668, 12.0, [("XBB.TO", 20), ("XSB.TO", 15), ("CLF.TO", 12), ("XSH.TO", 8), ("ZST.TO", 5), ("GLD", 5), ("ZLB.TO", 10), ("VDY.TO", 8), ("JNJ", 5), ("RY.TO", 4), ("KO", 4), ("USMV", 4)]),
]
JETONS_ENTREE = 9272   # moyenne mesurée par appel


def juger(a: Analyse, positions) -> dict:
    uni = a.uni
    inconnus = [t for t, _ in positions if t not in uni]
    poids = {t: w / 100 for t, w in positions if t in uni}
    ct = P.controles(poids, a.contraintes, uni, a.hyp, Registre())
    exclus = [t for t in poids if a.resultats[t]["verdict"] == "exclu"]
    hors_poids = [f"{t} {w * 100:.0f} % > {a.resultats[t]['poids_max_pct']:.0f} %" for t, w in poids.items()
                  if a.resultats[t]["verdict"] != "exclu" and w * 100 > a.resultats[t]["poids_max_pct"] + 0.1]
    return {"somme": sum(w for _, w in positions), "inconnus": inconnus, "exclus": exclus, "hors_poids": hors_poids,
            "conflits": [c for c in ct["conflits"] if "Aucun actif exclu" not in c], "stress": ct["stress"]["perte_stress_pct"],
            "tension": ct["ratio_tension"], "etat": ct["etat_tension"], "volatilite": ct["stress"]["mesures"]["volatilite_pct"]}


L = ["# Expérience : un portefeuille construit par un modèle seul, sans moteur", "",
     "Produit par `python scripts/experience_modele_seul.py`. Simulation éducative ; aucun conseil financier.", "",
     "**Question.** Faut-il confier la construction du portefeuille à des agents de A à Z, ou garder des règles écrites ?", "",
     "**Protocole.** Claude Sonnet 5.5 sur Amazon Bedrock, le 15 novembre 2026. Pour chaque persona : le profil en clair, la synthèse "
     "calculée (budget de perte, part d'actions indicative) et l'univers complet (111 actifs, 16 colonnes). Consigne : 5 à 12 positions, "
     "poids totalisant 100, toutes les contraintes respectées. Trois essais par persona, sans outil. Les neuf réponses sont jugées par "
     "les contrôles du moteur (`portefeuille.controles`), les mêmes que pour nos propres portefeuilles.", "",
     "## Résultats", "",
     "| Persona | Essai | Somme | Actifs exclus retenus | Contraintes en conflit | Perte de stress estimée par le modèle | Perte de stress mesurée | Écart |",
     "|---|---|---|---|---|---|---|---|"]
analyses = {n: Analyse(ch.charger_persona(n)["profil"], nom=n.capitalize()) for n in ch.personas_disponibles()}
par_persona: dict[str, list] = {}
fautes = 0
ecarts = []
for i, (nom, duree, sortie, estime, positions) in enumerate(REPONSES):
    j = juger(analyses[nom], positions)
    par_persona.setdefault(nom, []).append(dict(positions))
    probleme = bool(j["exclus"] or j["conflits"] or j["hors_poids"] or j["inconnus"] or abs(j["somme"] - 100) > 0.01)
    fautes += probleme
    ecarts.append(abs(estime - j["stress"]))
    raisons_exclus = "; ".join(f"{t} ({analyses[nom].resultats[t]['critere_decisif']})" for t in j["exclus"]) or "aucun"
    L.append(f"| {nom.capitalize()} | {i % 3 + 1} | {j['somme']:g} | {raisons_exclus} | {'; '.join(j['conflits'] + j['hors_poids']) or 'aucune'} | "
             f"{pct(estime)} | {pct(j['stress'])} | {pct(abs(estime - j['stress']))} |")

L += ["", "## Stabilité d'un essai à l'autre", "", "| Persona | Actifs communs aux trois essais | Actifs cités au moins une fois | Écart moyen de poids entre essais |", "|---|---|---|---|"]
for nom, essais in par_persona.items():
    tous = set().union(*essais)
    communs = set.intersection(*(set(e) for e in essais))
    diff = [abs(essais[x].get(t, 0) - essais[y].get(t, 0)) for t in tous for x, y in ((0, 1), (0, 2), (1, 2))]
    L.append(f"| {nom.capitalize()} | {len(communs)} | {len(tous)} | {statistics.mean(diff):.1f} point |".replace(".", ","))  # noqa

L += ["", "## Coût et délai", "", "| | Modèle seul | Moteur à règles |", "|---|---|---|",
      f"| Délai par portefeuille | {min(r[1] for r in REPONSES):.0f} à {max(r[1] for r in REPONSES):.0f} s | moins de 0,1 s |",
      f"| Jetons par portefeuille | environ {JETONS_ENTREE} en entrée, {round(statistics.mean(r[2] for r in REPONSES))} en sortie | aucun |",
      "| Même entrée, même sortie | non | oui (testé) |",
      "| Chaque poids relié à une règle et à une preuve | non : une phrase de justification par ligne | oui |"]

mesures_moteur = {n: a.portefeuille for n, a in analyses.items()}
L += ["", "## Comparaison avec le moteur", "", "| Persona | Budget de perte | Moteur : perte de stress | Modèle seul : perte de stress mesurée (3 essais) |", "|---|---|---|---|"]
for nom, a in analyses.items():
    vals = [juger(a, r[4])["stress"] for r in REPONSES if r[0] == nom]
    L.append(f"| {nom.capitalize()} | {pct(a.contraintes['budget_perte_pct'], 0)} | {pct(mesures_moteur[nom]['perte_stress_pct'])} | "
             + ", ".join(pct(v) for v in vals) + " |")

implicites = sum(1 for nom, *_, positions in REPONSES if any("emploi" in c for c in juger(analyses[nom], positions)["conflits"]))
dures = sum(1 for nom, *_, positions in REPONSES if juger(analyses[nom], positions)["exclus"] or juger(analyses[nom], positions)["hors_poids"])
L += ["", "## Lecture", "",
      "**Ce que le modèle fait bien.**",
      f"- Sur ces neuf essais, il respecte les contraintes écrites en toutes lettres : {dures} portefeuille sur {len(REPONSES)} retient un actif "
      "exclu ou dépasse un plafond par titre. Les poids totalisent 100 à chaque fois, aucun ticker n'est inventé.",
      "- Ses portefeuilles sont diversifiés et sensés (or pour Robert, semi-conducteurs pour Amira). Pour Amira, il utilise mieux le budget de "
      "perte que notre moteur, qui reste très en dessous.",
      "", "**Ce qu'il fait moins bien.**",
      f"- **Il ne voit pas les règles qu'on ne lui écrit pas.** {implicites} portefeuilles sur {len(REPONSES)} dépassent le plafond d'exposition au "
      "secteur de l'emploi (25 %, fonds compris) : le profil disait « secteur d'emploi : technologie », pas la règle. Le moteur l'applique "
      "toujours ; le modèle seulement si on pense à la lui rappeler.",
      f"- **Il estime son risque, il ne le calcule pas.** L'écart moyen entre la perte de stress qu'il annonce et celle que nous mesurons sur les "
      f"prix est de {pct(statistics.mean(ecarts))}, toujours dans le même sens (il surestime).",
      "- **Il ne se répète pas.** Pour la même personne, les poids changent d'un essai à l'autre, et pour Mateo moins de la moitié des actifs "
      "cités reviennent dans les trois essais. Deux utilisateurs identiques recevraient deux portefeuilles différents.",
      "- **Il est lent et ne laisse pas de trace vérifiable.** Quinze à trente secondes par portefeuille, contre moins d'un dixième de seconde, "
      "et une phrase de justification par ligne au lieu d'une preuve par contrainte.",
      "- **Rien n'est garanti.** Neuf essais sur trois personas ne font pas une statistique : ils montrent que c'est souvent juste, pas que "
      "c'est toujours juste. Or une exclusion (armement, tabac) doit tenir à chaque fois.",
      "", "## Décision", "",
      "Nous gardons les règles pour tout ce qui doit être exact et identique d'une fois à l'autre : exclusions, plafonds, poids, perte de stress, "
      "verdicts. Les agents font ce que les règles font mal : comprendre une demande en langage courant, choisir les outils, expliquer, proposer "
      "une alternative, refuser. Dans « Parler au conseiller », le modèle ne modifie le portefeuille qu'à travers des outils dont le code "
      "vérifie chaque effet.", "",
      "## Améliorations tirées de l'expérience", "",
      "1. **Modèle qui propose, moteur qui valide.** Laisser le modèle suggérer plusieurs portefeuilles candidats ; le moteur écarte ceux qui "
      "violent une contrainte, mesure les autres et garde le meilleur. On gagne son sens de la composition sans perdre la garantie.",
      "2. **Mieux utiliser le budget des profils dynamiques.** Le modèle donne plus de poids aux thèmes d'intérêt (semi-conducteurs, IA) ; notre "
      "moteur pourrait incliner davantage les poids vers les préférences quand la tension est très basse.",
      "3. **Rendre les règles implicites visibles.** Le plafond du secteur de l'emploi surprend : il mérite d'être dit à la personne dès la "
      "synthèse du profil, pas seulement dans les contrôles du portefeuille.",
      "4. **Mesurer avant d'élargir.** Refaire cette expérience sur quelques dizaines de profils annotés avant de confier davantage au modèle."]
(RACINE / "docs" / "experience_modele_seul.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L[10:48]))
