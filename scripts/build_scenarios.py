"""Précalcule les données des mises en situation du questionnaire (fichier JSON livré avec le site).

Sortie : mvp_profil/scenarios.json
  replay      : trajectoire mensuelle de 10 000 $ (CAD) de janvier 2022 à décembre 2024 pour 3 portefeuilles ;
                les anciens arrêts restent des métadonnées de compatibilité, sans interrompre le replay.
  replay_quotidien.json : mêmes portefeuilles, séances réelles pour l'animation continue et sa révélation.
  fourchettes : pour 5 portefeuilles, rendements sur un an glissant (centile 5, médiane, centile 95) et volatilité
  mode        : 4 titres anonymisés (2 très médiatisés, 2 établis peu médiatisés) avec leurs faits mesurés
Toutes les valeurs viennent de nos données (jeu de départ + univers étendu), converties en CAD.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
EXT = ROOT / "data_extended"

p = pd.concat([pd.read_csv(STARTER / "prices_daily.csv"), pd.read_csv(EXT / "prices_daily.csv")])
p["date"] = pd.to_datetime(p.date)
fx = pd.read_csv(EXT / "fx_to_cad_daily.csv", parse_dates=["date"])
crit = pd.read_csv(EXT / "asset_criteria.csv").set_index("ticker")


def cad(tk: str) -> pd.Series:
    g = p[p.ticker == tk].set_index("date").sort_index()
    c = g.currency.iloc[0]
    f = fx[fx.currency == c].set_index("date").cad_per_unit.sort_index().reindex(g.index, method="ffill") if c != "CAD" else 1.0
    return g.adj_close * f


def portefeuille(poids: dict[str, float], debut: str | None = None) -> pd.Series:
    """Portefeuille rééquilibré chaque jour (approximation simple), base 1 au début."""
    r = pd.concat({t: cad(t).pct_change() for t in poids}, axis=1).dropna()
    if debut:
        r = r.loc[debut:]
    return (1 + (r * pd.Series(poids)).sum(axis=1)).cumprod()


PORTEFEUILLES = {
    "tres_prudent": ("Très prudent", {"XEQT.TO": 0.2, "XBB.TO": 0.8}),
    "prudent": ("Prudent", {"XEQT.TO": 0.4, "XBB.TO": 0.6}),
    "equilibre": ("Équilibré", {"XEQT.TO": 0.6, "XBB.TO": 0.4}),
    "croissance": ("Croissance", {"XEQT.TO": 0.8, "XBB.TO": 0.2}),
    "actions": ("100 % actions", {"XEQT.TO": 1.0}),
}

# ---------- Replay 2022 ----------
REPLAY = {"equilibre": PORTEFEUILLES["equilibre"], "actions": PORTEFEUILLES["actions"],
          "technologie": ("Actions technologiques", {"QQQ": 1.0})}
ARRETS = ["2022-03-31", "2022-06-30", "2022-09-30", "2022-12-30"]
replay = {}
replay_quotidien = {}
for cle, (nom, poids) in REPLAY.items():
    s = portefeuille(poids, "2022-01-03").loc[:"2024-12-31"] * 10000
    mensuel = s.resample("ME").last()
    # Point 0 = départ (10 000 $) ; point k = fin du mois k. Sans ce point de départ, toutes les valeurs
    # affichées seraient décalées d'un mois.
    replay[cle] = {"nom": nom, "composition": poids,
                   "mois": ["départ"] + [d.strftime("%Y-%m") for d in mensuel.index],
                   "valeurs": [10000.0] + [round(v, 0) for v in mensuel],
                   "arrets": [{"date": d, "mois_index": int(np.searchsorted(mensuel.index, pd.Timestamp(d))) + 1,
                               "valeur": round(float(s.loc[:d].iloc[-1]), 0)} for d in ARRETS],
                   "creux": round(float(s.min()), 0), "fin": round(float(s.iloc[-1]), 0)}
    dates = [pd.Timestamp("2022-01-01")] + list(s.index)
    replay_quotidien[cle] = {"nom": nom, "dates": [d.strftime("%Y-%m-%d") for d in dates],
                            "valeurs": [10000.0] + [round(float(v), 4) for v in s],
                            "mois_positions": [round((d - dates[0]).days / 30.4375, 4) for d in dates],
                            "crise_fin": sum(d.year == 2022 for d in s.index)}

# ---------- Fourchettes de résultats sur un an ----------
# Les fenêtres glissantes d'un an sur 5 ans seulement donnent un résultat trompeur (en 2022, obligations et
# actions ont baissé ensemble : le portefeuille très prudent y paraît plus risqué que le 100 % actions).
# On simule donc 10 000 années en rééchantillonnant par blocs de 21 séances les rendements quotidiens réels
# (même tirage pour tous les portefeuilles, graine fixe : résultat reproductible).
#
# Le rendement MOYEN des 5 dernières années n'est pas utilisé (obligations à plat, actions en forte hausse :
# ce serait du rendement passé déguisé). On garde la DISPERSION observée et on recentre chaque portefeuille sur
# le rendement attendu de la Norme d'hypothèses de projection 2026 (FP Canada et Institut de planification
# financière, 16 avril 2026) : revenu fixe 3,2 % ; actions canadiennes 6,3 %, américaines 6,4 %,
# internationales 6,6 %, émergentes 7,5 % (avant frais). XEQT ≈ 45 % É.-U., 25 % Canada, 25 % international,
# 5 % émergents (approximation de sa répartition) : 0,45×6,4 + 0,25×6,3 + 0,25×6,6 + 0,05×7,5 ≈ 6,5 %.
ATTENDU = {"XEQT.TO": 0.065, "XBB.TO": 0.032}
SOURCE_HYPOTHESES = ("Norme d'hypothèses de projection 2026, FP Canada et Institut de planification financière : "
                     "https://www.newswire.ca/news-releases/fp-canada-tm-and-the-institute-of-financial-planning-jointly-publish-the-2026-projection-assumption-guidelines-for-financial-planners-804319758.html")
N_ANNEES, BLOC, SEANCES = 10_000, 21, 252
base = pd.concat({t: cad(t).pct_change() for t in ["XEQT.TO", "XBB.TO"]}, axis=1).dropna()
rng = np.random.default_rng(2026)
debuts = rng.integers(0, len(base) - BLOC, size=(N_ANNEES, SEANCES // BLOC))
fourchettes = {}
for cle, (nom, poids) in PORTEFEUILLES.items():
    r = (base[list(poids)] * pd.Series(poids)).sum(axis=1).to_numpy()
    mu = sum(w * ATTENDU[t] for t, w in poids.items())
    log_r = np.log1p(r)
    log_r = log_r - log_r.mean() + np.log1p(mu) / SEANCES  # dispersion réelle, moyenne = hypothèse publiée
    cumul = np.cumsum(np.concatenate([[0.0], log_r]))
    annee = (cumul[debuts + BLOC] - cumul[debuts]).sum(axis=1)  # somme des 12 blocs d'un mois
    r1 = np.expm1(annee)
    fourchettes[cle] = {"nom": nom, "composition": poids, "mauvaise": round(float(np.percentile(r1, 5)), 4),
                        "typique": round(float(np.median(r1)), 4), "bonne": round(float(np.percentile(r1, 95)), 4),
                        "volatilite": round(float(np.std(r) * np.sqrt(252)), 4), "annees_simulees": N_ANNEES,
                        "rendement_attendu": round(mu, 4),
                        "methode": "dispersion : rééchantillonnage par blocs de 21 séances des rendements 2021-2026 (CAD) ; "
                                   "moyenne : " + SOURCE_HYPOTHESES}

# ---------- Test de l'effet de mode ----------
SECTEURS = {"Consumer Discretionary": "Automobile et consommation", "Information Technology": "Technologie",
            "Financials": "Banque", "Consumer Staples": "Consommation de base", "Utilities": "Services publics",
            "Health Care": "Santé", "Communication Services": "Communications", "Energy": "Énergie"}
eq = crit[crit.asset_class == "equity"]
hype = eq[(eq.media_hype == "tres_mediatise")].sort_values("attention_spikes_per_year", ascending=False)
hype = hype[hype.attention_spike_last_30d.astype(str) == "True"].head(2) if (hype.attention_spike_last_30d.astype(str) == "True").sum() >= 2 else hype.head(2)
calmes = eq[(eq.media_hype == "normale") & (eq.established) & (eq.vol_cad < 0.20)].sort_values("vol_cad").head(2)
choix = []
for tk, r in pd.concat([hype, calmes]).iterrows():
    choix.append({"ticker": tk, "nom": str(r["name"]), "mediatise": bool(r.media_hype == "tres_mediatise"),
                  "secteur": SECTEURS.get(r.sector, r.sector), "rendement_3m": round(float(r.return_3m), 4),
                  "volatilite": round(float(r.vol_cad), 4), "perte_max": round(float(r.max_drawdown), 4),
                  "dividende": round(float(r.dividend_yield_ttm), 4), "pic_recent": str(r.attention_spike_last_30d) == "True",
                  # fait neutre affiché pour les quatre titres (médiane quotidienne, Wikipédia en anglais)
                  "vues_par_jour": round(float(r.attention_median_daily_views))})
# Ordre fixe, alterné, pour que tout le monde voie la même liste
choix = [choix[i] for i in (0, 2, 1, 3)]
for lettre, c in zip("ABCD", choix):
    c["lettre"] = lettre

out = {"genere_le": pd.Timestamp.today().strftime("%Y-%m-%d"), "source": "jeu de départ + univers étendu, en CAD",
       "replay": replay, "fourchettes": fourchettes, "mode": choix}
(ROOT / "mvp_profil" / "scenarios.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
(ROOT / "mvp_profil" / "replay_quotidien.json").write_text(
    json.dumps(replay_quotidien, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
for k, v in replay.items():
    print(f"replay {k}: arrêts {[a['valeur'] for a in v['arrets']]}, creux {v['creux']}, fin {v['fin']}")
for k, v in fourchettes.items():
    print(f"fourchette {k}: {v['mauvaise']:+.1%} / {v['typique']:+.1%} / {v['bonne']:+.1%}  vol {v['volatilite']:.1%}")
for c in choix:
    print(f"mode {c['lettre']}: {c['ticker']} médiatisé={c['mediatise']} 3m={c['rendement_3m']:+.1%} vol={c['volatilite']:.0%}")
