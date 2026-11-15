"""Contrat de données : libellés profil ↔ actifs, grille ↔ règles exécutables, univers variable, états explicites."""
import csv
import shutil
import tempfile
from pathlib import Path

from reco_tests_commun import RACINE, Analyse, analyse, ch, verifier

from recommandation import contraintes as C
from criteres import CRITERES

# 1. Chaque ligne de la grille a une règle exécutable ou une mention « non codée » motivée.
grille = list(csv.DictReader((RACINE / "config" / "criteres_appariement.csv").open(encoding="utf-8")))
regles = ch.regles()["regles"]
for ligne in grille:
    r = regles.get(ligne["id"])
    verifier(r is not None, f"{ligne['id']} : aucune règle dans config/regles_appariement.json")
    verifier(r["codee"] or r.get("raison_non_codee"), f"{ligne['id']} : règle non codée sans raison")
verifier(set(regles) == {l["id"] for l in grille}, "Règles sans ligne dans la grille : " + str(set(regles) - {l["id"] for l in grille}))

# 2. Chaque colonne citée par une règle ou une correspondance existe dans le fichier des actifs.
uni = ch.univers()
for cid, r in regles.items():
    for col in r["colonnes"]:
        verifier(col == "*" or col in uni.colonnes, f"{cid} : colonne d'actif inconnue « {col} »")


def conditions(x):
    if isinstance(x, dict):
        if "colonne" in x and "valeurs" in x:
            yield x
        for v in x.values():
            yield from conditions(v)
    elif isinstance(x, list):
        for v in x:
            yield from conditions(v)


for cond in conditions(ch.correspondances()):
    verifier(cond["colonne"] in uni.colonnes, f"correspondances.json : colonne inconnue « {cond['colonne']} »")

# 3. Chaque valeur du profil utilisée par une règle a une correspondance, ou une mention explicite sans effet.
corr = ch.correspondances()
for cid, table in (("D5", "themes"), ("D6", "themes"), ("D3", "regions"), ("D1", "classes"), ("E1", "E1"), ("E5", "E5"), ("F2", "F2"), ("G3", "G3")):
    for v in CRITERES[cid]["valeurs"]:
        e = corr[table].get(v)
        verifier(e is not None, f"{cid} = {v} : aucune correspondance côté actifs")
        verifier(any(k in e for k in ("colonne", "toutes", "aucun_actif", "sans_effet", "exclure", "plafonner", "accessible", "comme")),
                 f"{cid} = {v} : correspondance sans effet déclaré")
for emploi in CRITERES["A12"]["valeurs"]:
    verifier(emploi in corr["secteur_emploi_vers_gics"], f"A12 = {emploi} : secteur d'emploi sans correspondance")
verifier(set(CRITERES["B5"]["valeurs"]) == {a["kw_volatilite"] for a in uni.actifs.values()},
         "B5 et kw_volatilite n'ont plus le même vocabulaire")

# 4. Une valeur ciblée par une correspondance existe réellement dans l'univers, sinon elle doit être déclarée sans actif.
orphelines = []
for cond in conditions({k: corr[k] for k in ("themes", "regions", "classes", "E1", "E5", "F2")}):
    presentes = {v for a in uni.actifs.values() for v in ch.etiquettes(a.get(cond["colonne"]))}
    if not presentes & set(cond["valeurs"]):
        orphelines.append((cond["colonne"], cond["valeurs"]))
verifier(not orphelines, f"Correspondances qui ne touchent aucun actif sans le dire : {orphelines}")

# 5. Les trois personas se chargent ; les quatre états sont explicites ; rien n'est inventé pour un inconnu.
for nom in ch.personas_disponibles():
    a = analyse(nom)
    etats = {e["etat"] for e in a.contraintes["etats"].values()}
    verifier(etats <= {"CONNU", "INCERTAIN", "INCONNU", "NON_APPLICABLE"}, f"{nom} : état de critère inattendu {etats}")
    for inconnu in a.contraintes["inconnus"]:
        verifier(inconnu["traitement"], f"{nom} : critère inconnu {inconnu['critere']} sans traitement écrit")
    prudents = {r["critere"] for r in a.contraintes["reglages_prudents"]}
    for ex in a.contraintes["exclusions"]:
        connu = a.contraintes["etats"].get(ex["critere"], {}).get("etat") == "CONNU"
        verifier(connu or ex["critere"] in prudents or ex["critere"].startswith("X"),
                 f"{nom} : exclusion {ex['critere']} sans réponse ni réglage prudent déclaré")
verifier(C.etat_critere({}, "E5")["etat"] == "INCONNU", "critère absent : doit être INCONNU")
verifier(C.etat_critere({"E5": {"valeurs": ["aucune"], "statut": "validé"}}, "E5")["etat"] == "NON_APPLICABLE", "valeur neutre")
verifier(C.etat_critere({"E5": {"valeurs": ["tabac"], "statut": "incertain"}}, "E5")["etat"] == "INCERTAIN", "statut incertain")
verifier(C.etat_critere({"E5": {"valeurs": [], "statut": "à préciser"}}, "E5")["etat"] == "INCONNU", "à préciser")
incertain = Analyse({**ch.charger_persona("mateo")["profil"], "E5": {"valeurs": ["tabac"], "statut": "incertain", "source": "IA", "confiance": 0.4}})
verifier(not [e for e in incertain.contraintes["exclusions"] if e["critere"] == "E5"], "une réponse incertaine ne doit pas filtrer")

# 6. Univers variable : un actif ajouté est évalué, cherché et comparé ; une ligne incomplète est signalée, jamais notée.
with tempfile.TemporaryDirectory() as d:
    copie = Path(d) / "asset_criteria.csv"
    shutil.copy(uni.chemin, copie)
    lignes = list(csv.DictReader(copie.open(encoding="utf-8")))
    nouveau = dict(next(l for l in lignes if l["asset_class"] == "equity" and l["speculative"] == "False"))
    nouveau.update(ticker="FICTIF.TO", name="Société fictive de test")
    troue = dict(nouveau, ticker="TROU.TO", name="Actif sans données", stress_loss="", vol_cad="")
    with copie.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=uni.colonnes)
        w.writeheader()
        w.writerows(lignes[:-3] + [nouveau, troue])       # trois actifs retirés, deux ajoutés
    u2 = ch.Univers(copie)
    verifier(len(u2) == len(uni) - 1, "le nombre d'actifs doit suivre le fichier")
    a2 = Analyse(ch.charger_persona("amira")["profil"], univers=u2)
    f = a2.rechercher("fictif")
    verifier(f["ticker"] == "FICTIF.TO" and f["score"] is not None, "l'actif ajouté doit être trouvé et noté")
    verifier(a2.rechercher("TROU.TO")["verdict"] == "donnees_insuffisantes", "une ligne incomplète doit donner « données insuffisantes »")
    verifier(a2.rechercher(lignes[-1]["ticker"])["verdict"] == "absent", "un actif retiré doit être « absent »")
    verifier("erreur" not in a2.comparer("FICTIF.TO", lignes[0]["ticker"]), "l'actif ajouté doit pouvoir être comparé")
    sans = Path(d) / "sans_colonne.csv"
    with sans.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[c for c in uni.colonnes if c != "stress_loss"], extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes[:5])
    try:
        ch.Univers(sans)
        raise AssertionError("une colonne requise absente doit faire échouer le chargement")
    except ValueError:
        pass

# 7. Le site ne lit que mvp_profil/ : les données embarquées doivent suivre leurs sources, et le paquet tout contenir.
import importlib.util  # noqa: E402
from pathlib import Path as _P  # noqa: E402

spec = importlib.util.spec_from_file_location("build_reco", RACINE / "scripts" / "build_donnees_recommandation.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
verifier(build.a_jour(), "Données de recommandation périmées : relancer python scripts/build_donnees_recommandation.py")
from version_profil import FICHIERS  # noqa: E402
paquet = _P(ch.PAQUET)
attendus = {f"recommandation/{p.relative_to(paquet).as_posix()}" for p in paquet.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".csv", ".json")}
verifier(attendus <= set(FICHIERS), f"Fichiers de recommandation absents de version_profil.FICHIERS : {sorted(attendus - set(FICHIERS))}")
verifier(set(ch.prix_cad().columns) >= set(uni.tickers()), "Des actifs n'ont pas de série de prix embarquée")

print(f"Contrat OK : {len(grille)} lignes de grille reliées à une règle, correspondances vérifiées sur {len(uni)} actifs, "
      "états explicites, univers variable (ajout, retrait, ligne incomplète, colonne absente), données embarquées à jour")
