"""Cas adverses de l'audit : fonds, change, sensibilité et persistance, sans cloud."""
from pathlib import Path
import tempfile
from unittest.mock import patch

from reco_tests_commun import Analyse, analyse, ch, verifier
from recommandation import appariement as A, contraintes as C, mesures as M, portefeuille as P, traces
from recommandation.preuves import Registre


uni = ch.univers()
mateo, robert = analyse("mateo"), analyse("robert")

# Une exclusion grave ne doit pas être contournée par l'enveloppe d'un fonds.
verifier(mateo.fiche("GOOGL")["verdict"] == "exclu", "GOOGL doit être exclu pour Mateo")
fonds_google = [t for t, ps in ch.positions_fnb().items() if ps.get("GOOGL", 0) > 0 and t in uni]
verifier(bool(fonds_google), "le jeu doit exercer le cas d'exposition indirecte")
for t in fonds_google:
    fiche = mateo.fiche(t)
    verifier(fiche["verdict"] == "exclu", f"{t} laisse entrer GOOGL par une détention indirecte")
    verifier(any(p["id"] == "actif:GOOGL:max_severity" for p in fiche["preuves"]),
             f"{t} : la controverse du sous-jacent doit avoir une preuve")
verifier(mateo.portefeuille["expositions"]["titres_pct"].get("GOOGL", 0) == 0,
         "le portefeuille final expose encore Mateo à une controverse exclue connue")

# Les activités exclues sont aussi propagées ; une classe ou un accès non accepté ne l'est pas.
tabac = next(ex for ex in mateo.contraintes["exclusions"] if ex["critere"] == "E5" and ex.get("valeur") == "tabac")
avec_tabac = {"XBB.TO": {"PM": .02, "INCONNU": .4}}
with patch.object(C, "positions_fnb", return_value=avec_tabac):
    verifier(C.positions_exclues(uni["XBB.TO"], tabac, uni) == {"PM": .02}, "position tabac connue ignorée")
    f = A.evaluer_actif("XBB.TO", mateo.contraintes, uni)
    verifier(f["verdict"] == "exclu" and "PM" in f["message"], "le fonds exposé au tabac doit être exclu et expliqué")
    classe = {"mode": "hors", "condition": {"colonne": "asset_class", "valeurs": ["etf_bond"]}}
    verifier(not C.exclusion_s_applique(uni["XBB.TO"], classe, uni),
             "une restriction sur les classes ne doit pas se propager aux titres du fonds")
with patch.object(C, "positions_fnb", return_value={"XBB.TO": {"PM": 0}}):
    verifier(not C.exclusion_s_applique(uni["XBB.TO"], tabac, uni), "une position de poids nul ne doit pas exclure")

# Couverture partielle : informer sans transformer l'absence de preuve en preuve d'absence.
f = mateo.fiche("XEQT.TO")
verifier(any("part restante est inconnue" in l["raison"] for l in f["lignes"]),
         "les sous-jacents non couverts doivent rester inconnus")
ctl = next(c for c in mateo.portefeuille["controles"] if c["critere"] == "H2")
verifier("connue" in ctl["contrainte"] and "garantie" in ctl["detail"], "le contrôle ESG doit annoncer sa couverture limitée")

# Un fonds non couvert ne devient pas CAD parce qu'il est négocié au Canada.
verifier(M.expositions({"XEQT.TO": 1.0}, uni)["hors_cad_pct"] == 100.0, "XEQT échappe au plafond de change")
verifier(not C.expose_change({"kw_devise": "cad_couvert", "fx_risk": "present"}), "couverture CAD ignorée")
verifier(C.expose_change({"kw_devise": "usd_couvert", "fx_risk": "present"}), "couverture USD assimilée à CAD")
ctls = P.controles({"XEQT.TO": 1.0}, robert.contraintes, uni, ch.hypotheses(), Registre())
verifier(any(c["critere"] == "D4" and c["etat"] == "en_conflit" for c in ctls["lignes"]),
         "un portefeuille 100 % XEQT doit dépasser le plafond de change de Robert")

# Une sensibilité ne retire pas les ajouts imposés en même temps qu'elle change son hypothèse.
avec = Analyse(ch.charger_persona("robert")["profil"], ajouts={"NVDA": 5.0})
variantes = []
comparer = Analyse.comparer_a


def observer(self, autre):
    variantes.append(autre)
    return comparer(self, autre)


with patch.object(Analyse, "comparer_a", observer):
    avec.sensibilite()
verifier(len(variantes) >= 6 and all(a.ajouts == {"NVDA": 5.0} for a in variantes),
         "la sensibilité perd les ajouts de l'utilisateur")
verifier(all(abs(a.portefeuille["poids"].get("NVDA", 0) - .05) < 1e-6 for a in variantes),
         "la part imposée doit rester fixe dans chaque variante")

# La perte de persistance ne doit jamais être annoncée comme une écriture réussie.
j = traces.Journal(persister=True)
with patch.object(Path, "mkdir", side_effect=PermissionError("disque indisponible")):
    j.noter("audit_local")
verifier(j.stockage() == "mémoire seulement" and j.erreur_stockage and len(j.evenements) == 1,
         "une erreur disque locale doit laisser une trace mémoire et un état exact")


class TableEnPanne:
    def put_item(self, **kwargs):
        raise RuntimeError("table indisponible")


with tempfile.TemporaryDirectory() as d, patch.object(traces, "DOSSIER", Path(d)):
    j = traces.Journal(persister=True)
    j._table = TableEnPanne()
    j.noter("audit_secours")
    verifier(j.stockage().startswith("fichier local") and (Path(d) / f"{j.session}.jsonl").is_file(),
             "le secours local après DynamoDB doit continuer à fonctionner")

print("Audit corrigé : exclusions indirectes prouvées, couverture inconnue visible, change CAD/non couvert, "
      "ajouts conservés en sensibilité et état de persistance exact.")
