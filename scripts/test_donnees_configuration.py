"""Non-régressions locales des calculs, correspondances et validations de publication."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from zipfile import ZipFile

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RACINE / "scripts"), str(RACINE / "mvp_profil")]
import build_asset_criteria as actifs
import compute_metrics as metriques
from build_donnees_chercheur import resoudre_position
from preparer_mvp import construire, verifier_archive
from version_profil import FICHIERS, version_depuis_empreintes

# Le premier rendement de janvier appartient bien à l'année civile.
s = pd.Series([100., 110., 121.], index=pd.to_datetime(["2021-12-31", "2022-01-03", "2022-12-30"]))
assert abs(metriques.rendement_annee(s, 2022) - .21) < 1e-12
assert metriques.rendement_annee(s.iloc[1:], 2022) is None
assert metriques.rendement_annee(s.iloc[:1], 2022) is None

# La configuration pilote réellement les deux barèmes qui étaient morts.
srri = metriques.CFG["classe_risque_bornes_volatilite"]
frais = actifs.CFG["frais_fnb_bornes"]
try:
    metriques.CFG["classe_risque_bornes_volatilite"] = [.50]
    assert metriques.risk_class(.20) == 1
    actifs.CFG["frais_fnb_bornes"] = [.001, .002, .003]
    assert actifs.classe_frais(.004).startswith("eleves_")
finally:
    metriques.CFG["classe_risque_bornes_volatilite"] = srri
    actifs.CFG["frais_fnb_bornes"] = frais
assert actifs.classe_frais(.004) == "faibles_0_15_0_50"  # politique effective historique conservée
assert actifs.classe_frais(.01) == "eleves_a_partir_de_1"

# Les frontières partagées avec le profil sont inclusives là où le plafond l'est.
assert actifs.classe_volatilite(7.999) == "faible_moins_8"
assert actifs.classe_volatilite(8) == actifs.classe_volatilite(15) == "moderee_8_15"
assert actifs.classe_volatilite(25) == "elevee_15_25"
assert actifs.classe_recuperation(365, "recupere") == "rapide_moins_1_an"
assert actifs.classe_recuperation(730, "recupere") == "moyenne_1_2_ans"
assert actifs.classe_recuperation(float("nan"), "baisse_en_cours") == "baisse_en_cours"
ligne = SimpleNamespace(rate_sensitivity="faible", sector="Health Care", themes="sante",
                        fossil_involvement="aucune", fx_risk="present", currency="USD", fx_vol_contribution=.025)
assert "sensible_aux_devises" not in actifs.sensibilite_macro(ligne)
ligne.fx_risk = "notable"
assert "sensible_aux_devises" in actifs.sensibilite_macro(ligne)

# Le signe du résultat net ne se déduit ni du ROE ni de la marge : capitaux propres
# négatifs, revenus négatifs, bénéfice nul et données manquantes restent distincts.
ratios, annuels = [], []
def exercice(ticker, annee, net, equity, roe, dette=.2, publication=None):
    date = f"{annee}-12-31"
    dispo = publication or f"{annee + 1}-03-31"
    ratios.append(dict(ticker=ticker, fiscal_year_end=date, available_from=dispo,
                       roe=roe, debt_to_equity=dette, net_margin=-.1,
                       revenue_growth=.02, interest_coverage=2., fcf_margin=.01,
                       dividends_to_fcf=.3, industrial_ratios_meaningful=True))
    for champ, valeur in (("Net Income", net), ("Stockholders Equity", equity)):
        if valeur is not None:
            annuels.append(dict(ticker=ticker, fiscal_year_end=date, available_from=dispo,
                                field=champ, value=valeur))

exercice("PERTE_EQUITY_NEG", 2025, -10., -100., .1, -.2)
exercice("PROFIT_EQUITY_NEG", 2025, 10., -100., -.1, -.2)
exercice("EQUITY_NUL", 2025, 10., 0., float("inf"), float("inf"))
exercice("REVENU_NEG", 2025, 10., 100., .1)
exercice("NET_INCONNU", 2025, None, 100., .2)
exercice("EQUITY_INCONNU", 2025, 10., None, .2)
exercice("ZERO", 2025, 0., 100., 0., 0.)
exercice("DERNIER_INVALIDE", 2024, 20., 100., .2)
exercice("DERNIER_INVALIDE", 2025, -10., -100., .1, -.2)
exercice("NON_PUBLIE", 2024, 10., 100., .1)
exercice("NON_PUBLIE", 2026, -10., -100., .1, -.2, publication="2027-03-31")
fond = actifs.fundamentals_summary(pd.DataFrame(ratios), pd.DataFrame(annuels)).set_index("ticker")
assert fond.loc["PERTE_EQUITY_NEG", "profitable_years_share"] == 0.
assert fond.loc["PROFIT_EQUITY_NEG", "profitable_years_share"] == 1.
assert fond.loc["REVENU_NEG", "profitable_years_share"] == 1.
assert fond.loc["ZERO", "profitable_years_share"] == 0.
assert fond.loc["ZERO", "roe_last"] == fond.loc["ZERO", "debt_to_equity_last"] == 0.
assert pd.isna(fond.loc["NET_INCONNU", "profitable_years_share"])
assert fond.loc["EQUITY_INCONNU", "profitable_years_share"] == 1.
for ticker in ("PERTE_EQUITY_NEG", "PROFIT_EQUITY_NEG", "EQUITY_NUL", "EQUITY_INCONNU", "DERNIER_INVALIDE"):
    assert pd.isna(fond.loc[ticker, "roe_last"])
    assert pd.isna(fond.loc[ticker, "debt_to_equity_last"])
assert fond.loc["NON_PUBLIE", "profitable_years_share"] == 1.
assert fond.loc["NON_PUBLIE", "roe_last"] == .1
assert fond.loc["NON_PUBLIE", "fiscal_years"] == 1

for dette in (-.2, float("inf"), float("nan")):
    ligne_fin = SimpleNamespace(asset_class="equity", industrial_ratios_meaningful=True,
                                debt_to_equity_last=dette, roe_last=float("nan"),
                                fcf_margin_last=0., interest_coverage_last=0., profitable_years_share=0.)
    assert "faible_endettement" not in actifs.sante_financiere(ligne_fin)
    assert "rentabilite_elevee_roe" not in actifs.sante_financiere(ligne_fin)
    assert "pertes_recurrentes" in actifs.sante_financiere(ligne_fin)

# Une cotation en CAD ne couvre pas les actifs étrangers ; une couverture USD ne
# couvre pas le change USD/CAD. Une vraie couverture CAD ne crée pas de risque.
xeqt = actifs.classe_devise("XEQT.TO", "etf_equity", "CAD")
assert xeqt == "cad_actifs_etrangers_non_couverts"
assert actifs.risque_change(xeqt, 0.) == "present"
assert actifs.risque_change(actifs.classe_devise("BNDW", "etf_bond", "USD"), 0.) == "present"
assert actifs.risque_change("cad", .1) == "aucun"
assert actifs.risque_change("cad_couvert", .1) == "aucun"
assert actifs.risque_change("autre_devise", float("nan")) == "present"
assert actifs.risque_change("usd", actifs.CFG["change_contribution_notable"]) == "notable"

# Aucun préfixe ambigu : GOOG est relié par émetteur, pas par prix ou titre équivalent.
table = json.loads((RACINE / "config" / "correspondances_positions_fnb.json").read_text(encoding="utf-8"))
univers = {"GOOGL": {}, "VOD.JO": {}, "RY.TO": {}}
assert resoudre_position("GOOGL", univers, table) == ("GOOGL", "titre_exact")
assert resoudre_position("GOOG", univers, table) == ("GOOGL", "meme_emetteur")
assert resoudre_position("VOD", univers, table) == ("", "non_relie")
assert resoudre_position("VOD.L", univers, table) == ("", "non_relie")
assert resoudre_position("RY", univers, table) == ("RY.TO", "alias_cotation")

# Un paquet altéré est rejeté par une exception, y compris sous python -O.
with tempfile.TemporaryDirectory(prefix="awsome-ai-paquet-") as dossier:
    racine = Path(dossier).resolve()
    source = racine / "source"
    for nom in FICHIERS:
        p = source / nom
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(("contenu test " + nom).encode())
    paquet = racine / "paquet.zip"
    manifeste = construire(paquet, source)
    assert verifier_archive(paquet) == manifeste
    assert manifeste["version"] == version_depuis_empreintes(dict(reversed(list(manifeste["fichiers"].items()))))
    altere = racine / "altere.zip"
    with ZipFile(paquet) as z, ZipFile(altere, "w") as out:
        for nom in z.namelist():
            out.writestr(nom, b"altere" if nom == "app.py" else z.read(nom))
    for options in ([], ["-O"]):
        code = ("import sys;sys.path.insert(0,sys.argv[1]);from preparer_mvp import verifier_archive;"
                "from pathlib import Path;verifier_archive(Path(sys.argv[2]))")
        r = subprocess.run([sys.executable, *options, "-c", code, str(RACINE / "scripts"), str(altere)],
                           capture_output=True, text=True, check=False)
        assert r.returncode != 0 and "Empreinte du paquet incorrecte" in r.stderr

# La validation du corpus reste active lorsque les assertions sont désactivées.
code = ("import sys,json,types;sys.path.insert(0,sys.argv[1]);import evaluer_classement as e;"
        "e.JEU=types.SimpleNamespace(read_text=lambda **kw:json.dumps({'phrases':[{'id':'x','question':'?','reponse':'x',"
        "'attendu':{'A2':['HORS_LISTE']}}]}));e.charger()")
for options in ([], ["-O"]):
    r = subprocess.run([sys.executable, *options, "-c", code, str(RACINE / "mvp_profil")],
                       capture_output=True, text=True, check=False)
    assert r.returncode != 0 and "valeur hors liste" in r.stderr

print("Données/configuration OK : rendement annuel, bénéfices bruts, ratios interprétables, change des sous-jacents, seuils, frontières, émetteurs, paquet et corpus vérifiés")
