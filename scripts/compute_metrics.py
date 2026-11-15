"""Indicateurs de risque en CAD pour l'univers complet (jeu de départ + univers étendu).

Sortie : data_extended/asset_metrics_cad.csv (une ligne par actif).

Méthode (toutes les valeurs sont descriptives : le passé ne prédit pas l'avenir) :
  - Prix ajustés (adj_close) convertis en CAD avec le taux de la Banque du Canada du même jour,
    ou du dernier jour publié avant (pas de taux les jours fériés canadiens). Pour DKK et EGP :
    taux croisé (voir data_extended/fx_to_cad_daily.csv).
  - Chaque actif garde son propre calendrier de cotation (pas de remplissage des prix).
  - Volatilité annualisée : écart-type des rendements quotidiens × racine du nombre moyen de
    séances par an de l'actif (≈ 250 pour une action, 365 pour une crypto).
  - Corrélation et bêta : rendements HEBDOMADAIRES (vendredi) en CAD contre VT (monde) et SPY,
    pour neutraliser le décalage horaire entre l'Asie, l'Europe et l'Amérique.
  - Classe de risque 1 à 7 : bandes de volatilité de type SRRI (hypothèse à valider).
  - Durée sous l'eau (underwater_days) : jours civils entre le SOMMET qui précède la pire baisse et le
    retour à ce sommet. C'est ce que demande la question B7 (« combien de temps pour retrouver sa valeur »).
    Vide si le sommet n'est pas encore retrouvé ; underwater_days_so_far donne alors la durée écoulée.
  - recovery_days (du CREUX au retour) est gardé pour information : il sous-estime l'attente réelle.
"""
from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
EXT = ROOT / "data_extended"
CFG = json.loads((ROOT / "config" / "seuils_criteres.json").read_text(encoding="utf-8"))


def load():
    u0 = pd.read_csv(STARTER / "assets_universe.csv").assign(region="Amérique du Nord", universe="départ")
    u0.loc[u0.asset_class == "crypto", "region"] = "Crypto"
    u1 = pd.read_csv(EXT / "assets_universe.csv").assign(universe="étendu")
    u = pd.concat([u0, u1], ignore_index=True)
    p = pd.concat([pd.read_csv(STARTER / "prices_daily.csv"), pd.read_csv(EXT / "prices_daily.csv")],
                  ignore_index=True)
    p["date"] = pd.to_datetime(p.date)
    fx = pd.read_csv(EXT / "fx_to_cad_daily.csv", parse_dates=["date"])
    return u, p, fx


def to_cad(p: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (tk, ccy), g in p.groupby(["ticker", "currency"]):
        g = g.sort_values("date")
        f = fx[fx.currency == ccy].sort_values("date")[["date", "cad_per_unit"]]
        m = pd.merge_asof(g[["date", "adj_close"]], f, on="date", direction="backward")
        m["cad"] = m.adj_close * m.cad_per_unit
        out.append(m.assign(ticker=tk)[["date", "ticker", "cad"]])
    return pd.concat(out).dropna()


def risk_class(vol: float) -> int:
    # Cette échelle d'actif reste distincte des classes de tolérance B5 du profil.
    return 1 + sum(vol > b for b in CFG["classe_risque_bornes_volatilite"])


def rendement_annee(prix: pd.Series, annee: int) -> float | None:
    """Rendement entre la dernière clôture de l'année précédente et la fin de l'année visée.

    Sans clôture antérieure, l'année n'est pas comparable : ne pas substituer sa
    première clôture, qui supprimerait le rendement du premier jour de cotation.
    """
    prix = prix.dropna().sort_index()
    courant = prix[prix.index.year == annee]
    precedent = prix[prix.index.year == annee - 1]
    if courant.empty or precedent.empty:
        return None
    return float(courant.iloc[-1] / precedent.iloc[-1] - 1)


def metrics(cad: pd.DataFrame) -> pd.DataFrame:
    wide = cad.pivot(index="date", columns="ticker", values="cad")
    weekly = wide.ffill().resample("W-FRI").last().pct_change(fill_method=None)
    rows = []
    for tk in wide.columns:
        s = wide[tk].dropna()
        r = s.pct_change().dropna()
        years = (s.index[-1] - s.index[0]).days / 365.25
        ppy = len(r) / years
        dd = s / s.cummax() - 1
        trough = dd.idxmin()
        peak_before = s[:trough].idxmax()
        rec = s[trough:][s[trough:] >= s[peak_before]]
        w = pd.concat({"asset": weekly[tk], "VT": weekly["VT"], "SPY": weekly["SPY"]}, axis=1).dropna()
        w = w.rename(columns={"asset": tk}) if tk not in ("VT", "SPY") else w.assign(**{tk: w["asset"]})
        vol = r.std() * np.sqrt(ppy)
        rows.append(dict(
            ticker=tk, first_date=s.index[0].date(), last_date=s.index[-1].date(), observations=len(s),
            cagr_cad=(s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1,
            vol_cad=vol, risk_class=risk_class(vol),
            max_drawdown=dd.min(), drawdown_peak=peak_before.date(), drawdown_trough=trough.date(),
            recovery_days=(rec.index[0] - trough).days if len(rec) else None,
            underwater_days=(rec.index[0] - peak_before).days if len(rec) else None,
            underwater_days_so_far=None if len(rec) else (s.index[-1] - peak_before).days,
            current_drawdown=dd.iloc[-1],
            return_2022=rendement_annee(s, 2022),
            var95_daily=np.percentile(r, 5),
            worst_month=s.resample("ME").last().pct_change().min(),
            corr_vt_weekly=w[tk].corr(w["VT"]), beta_vt_weekly=w[tk].cov(w["VT"]) / w["VT"].var(),
            corr_spy_weekly=w[tk].corr(w["SPY"]),
        ))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    u, p, fx = load()
    m = metrics(to_cad(p, fx))
    out = u[["ticker", "name", "asset_class", "region", "currency", "sector", "universe"]].merge(m, on="ticker")
    out.to_csv(EXT / "asset_metrics_cad.csv", index=False)
    show = out.assign(**{c: (out[c] * 100).round(1) for c in ["cagr_cad", "vol_cad", "max_drawdown", "return_2022"]})
    print(show[["ticker", "region", "vol_cad", "risk_class", "max_drawdown", "return_2022", "recovery_days",
                "corr_vt_weekly"]].round(2).to_string())
