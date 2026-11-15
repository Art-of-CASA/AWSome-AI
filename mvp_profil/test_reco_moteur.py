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

# ---------- Encaisse, ajouts imposés et contrainte limitante ----------
for a in (amira, mateo, robert):
    pf = a.portefeuille
    verifier(abs(sum(pf["poids"].values()) * 100 + pf["encaisse_pct"] - 100) < 0.2, f"{a.nom} : poids + encaisse = 100 %")
    verifier(pf["limite_par"], f"{a.nom} : la contrainte qui limite la part de croissance doit être nommée")
avec = Analyse(ch.charger_persona("robert")["profil"], ajouts={"NVDA": 5.0})
verifier(abs(avec.portefeuille["poids"]["NVDA"] - 0.05) < 1e-6 and not avec.portefeuille["conflits"], "un ajout imposé garde son poids, sans conflit")
verifier(any(l["demande"] for l in avec.portefeuille["lignes"]), "un ajout demandé est marqué comme tel")
d = robert.proposer_ajout("nvidia", 20)
verifier(d["decision"] == "reduit" and d["part_pct"] == 5 and not d["mises_a_jour"]["possible"], "Robert, 20 % de NVDA : part réduite, aucune réponse déclarée ne suffirait")
d = robert.proposer_ajout("nvidia", 10)
verifier(d["mises_a_jour"]["possible"] and {c["critere"] for c in d["mises_a_jour"]["changements"]} == {"D9", "D12"}, "Robert, 10 % de NVDA : deux plafonds déclarés à revoir")
d = mateo.proposer_ajout("NVDA", 5)
verifier(d["decision"] == "refuse" and d["alternatives"] and all(mateo.resultats[x["ticker"]]["verdict"] == "compatible" for x in d["alternatives"]),
         "Mateo, NVDA : refus avec des alternatives compatibles")
verifier(robert.proposer_ajout("gamestop")["decision"] == "absent", "actif absent")
verifier(robert.trouver_par_envie("un peu d'or")["envie"] == ["or"] and robert.trouver_par_envie("zzz")["envie"] is None, "recherche par envie")

# ---------- Robustesse : 200 profils aléatoires (réponses manquantes, incertaines, contradictoires) ----------
import random  # noqa: E402
from criteres import CRITERES  # noqa: E402

rnd = random.Random(2026)
construits = sans = 0
for i in range(200):
    p = {}
    for cid, d in CRITERES.items():
        if rnd.random() < 0.12:
            continue
        vals = d["valeurs"]
        v = rnd.sample(vals, rnd.randint(1, min(3, len(vals)))) if d.get("multiple") else [rnd.choice(vals)]
        if len(v) > 1 and any(x in ("aucun", "aucune") for x in v):
            v = [x for x in v if x in ("aucun", "aucune")][:1]
        statut = rnd.choices(["validé", "retenu", "incertain", "à préciser"], [80, 8, 6, 6])[0]
        p[cid] = {"valeurs": [] if statut == "à préciser" else v, "source": "aléatoire", "citation": "", "confiance": 1.0, "statut": statut, "motif": ""}
    a = Analyse(p)
    pf = a.portefeuille
    if "erreur" in pf:
        sans += 1
        verifier(not any(r["verdict"] == "compatible" for r in a.resultats.values()) or pf.get("diagnostic") is not None, f"profil {i} : refus sans diagnostic")
        continue
    construits += 1
    verifier(abs(sum(pf["poids"].values()) * 100 + pf["encaisse_pct"] - 100) < 0.2, f"profil {i} : poids + encaisse ≠ 100 %")
    verifier(all(a.resultats[t]["verdict"] == "compatible" for t in pf["poids"]), f"profil {i} : actif non compatible retenu")
    verifier(all(w * 100 <= a.resultats[t]["poids_max_pct"] + 0.11 for t, w in pf["poids"].items()), f"profil {i} : poids au-dessus du maximum compatible")
    verifier(not pf["conflits"], f"profil {i} : contrainte dépassée {pf['conflits']}")
    verifier(pf["etat_tension"] != "en_tension", f"profil {i} : perte de stress au-dessus du budget ({pf['ratio_tension']})")
    verifier(pf["encaisse_pct"] < 0.5 or pf["raison_encaisse"], f"profil {i} : encaisse non expliquée")
print(f"Robustesse : 200 profils aléatoires, {construits} portefeuilles sans aucune limite dépassée, {sans} sans actif compatible (diagnostic donné)")

print("Moteur OK : appariement (exclusions non compensables, bornes, preuves), portefeuilles des trois personas, "
      "demande de titre, recherche, comparaison, « Et si… ? », sensibilité")
for a in (amira, mateo, robert):
    pf = a.portefeuille
    print(f"  {a.nom:6} {A.decompte(a.resultats)} | portefeuille : {pf['nb_positions']} positions, croissance {pf['part_croissance_pct']} %, "
          f"stress {pf['perte_stress_pct']} % / budget {pf['budget_perte_pct']} %")
