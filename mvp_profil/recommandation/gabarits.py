"""Textes de secours, écrits par le code à partir des seules sorties d'outils.

Ils servent quand le modèle est indisponible (mode « sans modèle ») ou quand son texte est rejeté par le
vérificateur de fidélité ou par la gouvernance. Tous les chiffres viennent des sorties : ils passent le
vérificateur par construction (testé).
"""
from __future__ import annotations

from .appariement import pct


def _dollars(x: float) -> str:
    return f"{x:,.0f} $".replace(",", " ")


def contraintes(s: dict) -> str:
    lignes = [s["phrase"]]
    if s["exclusions"]:
        lignes.append("Exclusions appliquées : " + " ; ".join(f"{e['libelle']} [profil:{e['critere']}]" for e in s["exclusions"]) + ".")
    if s["reglages_prudents"]:
        lignes.append("Réglages prudents appliqués faute de réponse : " +
                      ", ".join(f"{r['nom']} ({r['libelle']})" for r in s["reglages_prudents"]) + ".")
    if s["inconnus"]:
        lignes.append(f"{s['nb_inconnus']} critères restent sans réponse : aucun filtre n'est inventé pour eux.")
    return "\n".join(lignes)


def portefeuille(pf: dict) -> str:
    if "erreur" in pf:
        return pf["erreur"]
    lignes = [f"Mini-portefeuille fictif de {len(pf['lignes'])} positions pour un montant fictif de {_dollars(pf['montant_fictif_cad'])} :"]
    lignes += [f"- {l['ticker']} ({l['nom']}) : {pct(l['poids_pct'])}, poche {l['poche']}" for l in pf["lignes"]]
    lignes.append(f"Perte de stress : {pct(pf['perte_stress_pct'])}, soit {_dollars(pf['perte_stress_cad'])}, pour un budget de perte de "
                  f"{pct(pf['budget_perte_pct'], 0)} ({_dollars(pf['budget_perte_cad'])}). Tension : {pf['ratio_tension']:.2f} "
                  f"({pf['etat_tension'].replace('_', ' ')}) [calcul:portefeuille:perte_stress].")
    if pf.get("conflits"):
        lignes.append("Contraintes en conflit : " + " ; ".join(pf["conflits"]) + ".")
    if pf.get("a_confirmer"):
        lignes.append("À confirmer avec la personne : " + " ; ".join(pf["a_confirmer"]) + ".")
    lignes.append("Ces mesures décrivent la période " + pf["mesures"]["periode"] + " ; elles ne prédisent rien.")
    return "\n".join(lignes)


def fiche(f: dict) -> str:
    if f.get("verdict") in ("absent", "Absent de l'univers") or "message" in f and "score" not in f:
        sugg = ", ".join(s["ticker"] for s in f.get("suggestions", []))
        return f.get("message", "Actif absent de l'univers.") + (f" Actifs proches : {sugg}." if sugg else "")
    crit = f.get("criteres") or f.get("lignes") or []
    tete = f"{f['ticker']} ({f.get('nom')}) : {f.get('libelle_verdict') or f.get('verdict')}"
    if f.get("score") is not None:
        tete += f", score {f['score']} sur 100, au plus {pct(f.get('poids_max_pct'), 0)} du portefeuille."
    lignes = [tete]
    for titre, etats in (("Ce qui soutient", ("coherent", "satisfaite")), ("Ce qui retient", ("exclu", "en_tension", "a_surveiller", "contraire"))):
        items = [l for l in crit if l["etat"] in etats]
        if items:
            lignes.append(titre + " :")
            lignes += [f"- {l['libelle']} : {l['raison']} [{', '.join(l['preuves'][:2])}]" for l in items]
    if f.get("donnees_manquantes"):
        lignes.append("Données manquantes : " + ", ".join(f["donnees_manquantes"]) + ".")
    return "\n".join(lignes)


def comparaison(c: dict) -> str:
    if "erreur" in c:
        return c["erreur"]
    e = c["ecart_decisif"]
    a, b = c["a"], c["b"]
    lignes = [f"{a['ticker']} : {a['libelle_verdict']}" + (f", score {a['score']}" if a["score"] is not None else "") +
              f". {b['ticker']} : {b['libelle_verdict']}" + (f", score {b['score']}" if b["score"] is not None else "") + "."]
    if e.get("critere"):
        lignes.append(f"Écart décisif : {e['libelle']} ({e['critere']}), en faveur de {e['en_faveur_de']}. {e['raison']}")
    else:
        lignes.append(e["raison"])
    return "\n".join(lignes)


def demande(v: dict) -> str:
    if v.get("verdict") == "absent":
        return v["raisons"][0]["texte"]
    lignes = [f"Demande : {pct(v['part_demandee_pct'], 0)} du portefeuille en {v['ticker']} ({_dollars(v['montant_demande_cad'])}). "
              f"Verdict : {v['libelle_verdict']} (figé le {v['fige_le'][:19]}, empreinte {v['empreinte']})."]
    for r in v.get("raisons", []):
        lignes.append(f"- {r['critere']} : {r['texte']}")
    if v.get("perte_stress_apres_pct") is not None:
        lignes.append(f"Perte de stress du portefeuille : {pct(v['perte_stress_avant_pct'])} avant, {pct(v['perte_stress_apres_pct'])} après, "
                      f"pour un budget de {pct(v['budget_perte_pct'], 0)} [calcul:demande:perte_stress_apres].")
    if v.get("part_max_compatible_pct") is not None:
        lignes.append(f"Part maximale compatible avec le profil : {pct(v['part_max_compatible_pct'], 0)}.")
    for p in (v.get("incoherence") or {}).get("pistes", []):
        lignes.append(p)
    return "\n".join(lignes)


def et_si(d: dict) -> str:
    if "erreur" in d:
        return d["erreur"]
    m = d["modification"]
    lignes = [f"Scénario fictif : {m['nom']} passe de « {', '.join(m['avant'])} » à « {', '.join(m['apres'])} »."]
    if d["aucun_changement"]:
        return lignes[0] + " Rien ne change : cette réponse ne limite pas le résultat actuel."
    lignes += [f"- {c['element']} : {c['avant']} → {c['apres']}" for c in d["contraintes"]]
    lignes.append(f"{d['nb_actifs_modifies']} actifs changent de score ou de poids maximal, dont {d['nb_changements_de_bande']} changent de verdict.")
    av, ap = d.get("portefeuille_avant"), d.get("portefeuille_apres")
    if av and ap:
        lignes.append(f"Perte de stress du portefeuille : {pct(av['perte_stress_pct'])} → {pct(ap['perte_stress_pct'])} ; "
                      f"part de croissance : {pct(av['part_croissance_pct'])} → {pct(ap['part_croissance_pct'])}.")
    return "\n".join(lignes)


def sensibilite(s: dict) -> str:
    lignes = ["Mise à l'épreuve des hypothèses (une à la fois) :"]
    for e in s["essais"]:
        pf = e["portefeuille"]
        suite = f" ; perte de stress {pct(pf['perte_stress_pct'])}" if pf else ""
        lignes.append(f"- {e['essai']} : {e['nb_changements_de_bande']} actifs changent de verdict{suite}.")
    lignes.append(s["limites"])
    return "\n".join(lignes)


PAR_OUTIL = {"lire_contraintes": contraintes, "construire_portefeuille": portefeuille, "chercher_actif": fiche,
             "comparer_actifs": comparaison, "evaluer_demande": demande, "et_si": et_si, "tester_sensibilite": sensibilite}


def depuis_appels(appels: list[dict]) -> str:
    """Texte de secours pour une suite d'appels d'outils."""
    morceaux = [PAR_OUTIL[a["outil"]](a["sortie"]) for a in appels if a["outil"] in PAR_OUTIL and "erreur" not in a["sortie"]]
    erreurs = [a["sortie"]["erreur"] for a in appels if "erreur" in a["sortie"]]
    return "\n\n".join(morceaux + erreurs) or "Aucune donnée ne permet de répondre à cette question : je préfère ne rien affirmer."
