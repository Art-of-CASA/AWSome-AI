"""Régression sur les personas : appariement, portefeuille, demande d'un titre, recherche, comparaison, « Et si… ? »."""
import copy
import json

from reco_tests_commun import Analyse, analyse, ch, verifier

from recommandation import appariement as A

amira, mateo, robert = analyse("amira"), analyse("mateo"), analyse("robert")
uni = ch.univers()
hyp = ch.hypotheses()

# ---------- Appariement ----------
for a in (amira, mateo, robert):
    for tk, r in a.resultats.items():
        if r["verdict"] == "exclu":
            verifier(r["score"] is None and r["poids_max_pct"] == 0, f"{a.nom} {tk} : un actif exclu ne doit avoir ni score ni poids")
            verifier(all(l["preuves"] for l in r["lignes"] if l["etat"] == "exclu"), f"{a.nom} {tk} : exclusion sans preuve")
        else:
            verifier(0 <= r["score"] <= 100, f"{a.nom} {tk} : score hors de 0-100")
            tension = any(l["etat"] == "en_tension" and l["borne"] for l in r["lignes"])
            surveille = any(l["etat"] == "a_surveiller" and l["borne"] and l["effet"] in ("CALIBRAGE", "PLAFOND") for l in r["lignes"])
            if tension:
                verifier(r["score"] <= hyp["bornes_score"]["en_tension"], f"{a.nom} {tk} : une tension doit borner le score")
            elif surveille:
                verifier(r["score"] <= hyp["bornes_score"]["a_surveiller"], f"{a.nom} {tk} : un critère à surveiller doit borner le score")
            verifier(all(l["preuves"] for l in r["lignes"] if l["effet"] != "INFORMATION" or l["preuves"]), f"{a.nom} {tk} : ligne sans preuve")

# Amira : le risque élevé est accepté, mais plafonné.
cryptos = [t for t in uni.tickers() if uni[t]["asset_class"] == "crypto"]
for t in cryptos:
    verifier(amira.resultats[t]["verdict"] != "exclu" and amira.resultats[t]["poids_max_pct"] <= 10, f"Amira : {t} doit être accepté et plafonné à 10 %")
    verifier(mateo.resultats[t]["verdict"] == "exclu" and robert.resultats[t]["verdict"] == "exclu", f"{t} doit être exclu pour Mateo et Robert")
verifier(amira.resultats["NVDA"]["verdict"] == "compatible" and amira.resultats["NVDA"]["poids_max_pct"] == 10, "Amira : NVDA compatible, plafonné")
# Mateo : ESG et controverses.
for t in uni.tickers():
    if uni[t]["max_severity"] == "élevée":
        verifier(mateo.resultats[t]["verdict"] == "exclu", f"Mateo : controverse élevée, {t} doit être exclu")
    if uni[t]["speculative"] == "True":
        verifier(mateo.resultats[t]["verdict"] == "exclu", f"Mateo : spéculatif, {t} doit être exclu")
    if uni[t]["max_severity"] == "moyenne" and mateo.resultats[t]["verdict"] != "exclu":
        verifier(mateo.resultats[t]["score"] <= 69, f"Mateo : controverse moyenne, {t} doit être au plus « à examiner »")
# Robert : pas de refus automatique, mais pas d'acquiescement.
r = robert.resultats["NVDA"]
verifier(r["verdict"] == "a_examiner" and r["poids_max_pct"] <= 5 and "D8" in r["criteres_en_tension"],
         "Robert : NVDA doit être « à examiner », plafonné à 5 %, avec l'avertissement D8")
# Une exclusion ne se compense jamais : toutes les préférences satisfaites ne changent rien.
p = copy.deepcopy(ch.charger_persona("mateo")["profil"])
p["D5"] = {"valeurs": ["ia", "semi-conducteurs"], "statut": "validé", "source": "test", "confiance": 1.0}
p["D7"] = {"valeurs": ["croissance"], "statut": "validé", "source": "test", "confiance": 1.0}
verifier(Analyse(p).resultats["NVDA"]["verdict"] == "exclu", "une exclusion ne se compense pas par des préférences")
# Déterminisme.
autre = Analyse(ch.charger_persona("robert")["profil"])
fige = lambda x: json.dumps({t: (r["verdict"], r["score"], r.get("poids_max_pct")) for t, r in x.resultats.items()}, sort_keys=True)  # noqa: E731
verifier(fige(autre) == fige(robert) and autre.portefeuille["poids"] == robert.portefeuille["poids"], "deux exécutions doivent donner le même résultat")

# ---------- Portefeuille ----------
for a in (amira, mateo, robert):
    pf = a.portefeuille
    verifier("erreur" not in pf, f"{a.nom} : {pf.get('erreur')}")
    total = sum(l["poids_pct"] for l in pf["lignes"]) + pf["non_investi_pct"]
    verifier(abs(total - 100) < 0.6, f"{a.nom} : la somme des poids fait {total}")
    verifier(hyp["portefeuille"]["nb_positions_min"] <= pf["nb_positions"] <= hyp["portefeuille"]["nb_positions_max"], f"{a.nom} : nombre de positions")
    verifier(not pf["conflits"], f"{a.nom} : contraintes en conflit {pf['conflits']}")
    verifier(all(a.resultats[l["ticker"]]["verdict"] == "compatible" for l in pf["lignes"]), f"{a.nom} : actif non compatible dans le portefeuille")
    verifier(all(l["poids_pct"] <= a.resultats[l["ticker"]]["poids_max_pct"] + 0.1 for l in pf["lignes"]), f"{a.nom} : poids au-dessus du maximum compatible")
    verifier(pf["perte_stress_pct"] <= a.contraintes["budget_perte_pct"], f"{a.nom} : perte de stress au-dessus du budget")
    verifier(pf["etat_tension"] == "coherent", f"{a.nom} : tension {pf['etat_tension']}")
    verifier(all(c["preuves"] for c in pf["controles"][:3]), f"{a.nom} : contrôle de risque sans preuve")
    verifier(abs(pf["perte_stress_cad"] - pf["perte_stress_pct"] / 100 * pf["montant_fictif_cad"]) < 0.01, "tension en dollars incohérente")
verifier(robert.portefeuille["perte_stress_pct"] < mateo.portefeuille["perte_stress_pct"] < amira.portefeuille["perte_stress_pct"],
         "le risque des portefeuilles doit suivre l'ordre Robert < Mateo < Amira")
actions = lambda a: sum(l["poids_pct"] for l in a.portefeuille["lignes"] if l["classe"] in ("equity", "etf_equity"))  # noqa: E731
verifier(20 <= actions(robert) <= 40.5, f"Robert : le portefeuille doit contenir des actions sans dépasser 40 % ({actions(robert)})")
verifier(mateo.portefeuille["mesures"]["volatilite_pct"] <= 15, "Mateo : volatilité au-dessus de 15 %")
verifier(robert.portefeuille["mesures"]["volatilite_pct"] <= 15, "Robert : volatilité au-dessus de 15 %")
e = amira.portefeuille["expositions"]
verifier(e["crypto_pct"] <= 10.05 and e["speculatif_pct"] <= 10.05, "Amira : plafonds crypto et spéculatif")
tech = sum(e["secteurs_pct"].get(s, 0) for s in amira.contraintes["plafonds"]["secteur_emploi"]["secteurs"])
verifier(tech <= 25.1, f"Amira : exposition effective au secteur de son emploi {tech} > 25 %")
verifier(len({uni[l['ticker']]['sector'] for l in amira.portefeuille['lignes']}) >= 4, "Amira : diversification insuffisante")

# ---------- Demande d'un titre (cas Robert) ----------
d20, d5 = robert.demande("NVDA", 20), robert.demande("nvidia", 5)
verifier(d20["verdict"] == "en_tension" and d20["part_max_compatible_pct"] == 5, f"Robert, 20 % de NVDA : {d20['verdict']} max {d20['part_max_compatible_pct']}")
verifier(d5["verdict"] == "a_surveiller", "Robert, 5 % de NVDA : compatible avec les plafonds mais à surveiller, pas d'acquiescement")
verifier(d20["perte_stress_apres_pct"] > d20["perte_stress_avant_pct"], "l'ajout doit augmenter la perte de stress")
verifier(robert.demande("NVDA", 20)["empreinte"] == d20["empreinte"], "même demande, même empreinte")
verifier(robert.demande("BTC-USD", 5)["verdict"] == "exclu" and robert.demande("GME", 5)["verdict"] == "absent", "exclu et absent")
verifier(mateo.demande("NVDA", 1)["verdict"] == "exclu", "Mateo : NVDA exclu quelle que soit la part")

# ---------- Recherche ----------
verifier(robert.rechercher("nvidia")["ticker"] == robert.rechercher("NVDA")["ticker"] == robert.rechercher(" nvda ")["ticker"] == "NVDA", "recherche par nom et ticker")
abs_ = robert.rechercher("GameStop")
verifier(abs_["verdict"] == "absent" and "score" not in abs_, "un actif absent ne reçoit aucun score")
f = robert.rechercher("XBB")
verifier(f["verdict"] == "compatible" and f["explication"]["soutient"] and f["score"] >= f["seuils"]["compatible"], "au-dessus du seuil : dire pourquoi c'est adapté")
f = robert.rechercher("tesla")
verifier(f["verdict"] == "a_examiner" and f["explication"]["retient"], "sous le seuil : dire ce qui pose problème")

# ---------- Comparaison ----------
c = robert.comparer("nvda", "xbb")
verifier(c["ecart_decisif"]["en_faveur_de"] == "XBB.TO" and c["ecart_decisif"]["effet"] in ("CALIBRAGE", "PLAFOND"), "écart décisif NVDA / XBB pour Robert")
verifier("erreur" in robert.comparer("nvda", "inconnu"), "comparaison avec un actif absent")
c = mateo.comparer("ENB.TO", "RY.TO")
verifier(c["ecart_decisif"]["effet"] == "DURE" and c["ecart_decisif"]["en_faveur_de"] == "RY.TO", "une exclusion doit être l'écart décisif")

# ---------- « Et si… ? » et sensibilité ----------
avant = json.dumps(robert.profil, sort_keys=True, ensure_ascii=False)
e = mateo.et_si("E2", "indifferent")
verifier(any(x["element"] == "Exclusion retirée" for x in e["contraintes"]) and e["decompte_apres"]["exclu"] < e["decompte_avant"]["exclu"],
         "Mateo : ne plus refuser les controverses doit lever une exclusion")
verifier(all(a["regles_en_cause"] for a in e["actifs_modifies"]), "chaque changement doit nommer sa règle")
e = robert.et_si("B6", "equilibre")
verifier(not any(x["element"].startswith("Budget") for x in e["contraintes"]),
         "Robert : son budget reste limité par son horizon de 3 à 5 ans, même avec une fourchette moins prudente")
e = amira.et_si("B6", "prudent")
verifier(any(x["element"].startswith("Budget") and x["apres"] < x["avant"] for x in e["contraintes"]) and
         e["portefeuille_apres"]["perte_stress_pct"] < e["portefeuille_avant"]["perte_stress_pct"],
         "Amira : une fourchette prudente observée doit abaisser le budget et le risque du portefeuille")
verifier("erreur" in robert.et_si("A2", "vingt ans") and "erreur" in robert.et_si("Z9", "x"), "valeur hors liste fermée refusée")
verifier(json.dumps(robert.profil, sort_keys=True, ensure_ascii=False) == avant, "« Et si… ? » ne doit jamais modifier le profil")
s = robert.sensibilite()
verifier({x["axe"] for x in s["essais"]} == {"horizon", "seuils", "periode"}, "sensibilité : horizon, seuils, période")

print("Moteur OK : appariement (exclusions non compensables, bornes, preuves), portefeuilles des trois personas, "
      "demande de titre, recherche, comparaison, « Et si… ? », sensibilité")
for a in (amira, mateo, robert):
    pf = a.portefeuille
    print(f"  {a.nom:6} {A.decompte(a.resultats)} | portefeuille : {pf['nb_positions']} positions, croissance {pf['part_croissance_pct']} %, "
          f"stress {pf['perte_stress_pct']} % / budget {pf['budget_perte_pct']} %")
