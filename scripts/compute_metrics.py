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
  - Temps de récupération : jours civils entre le creux de la pire baisse et le retour au sommet
    précédent ; vide si le sommet n'est pas encore retrouvé.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
EXT = ROOT / "data_extended"
SRRI = [0.005, 0.02, 0.05, 0.10, 0.15, 0.25]  # bornes supérieures des classes 1 à 6


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
    return 1 + sum(vol > b for b in SRRI)


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
        y22 = s[s.index.year == 2022]
        w = pd.concat({"asset": weekly[tk], "VT": weekly["VT"], "SPY": weekly["SPY"]}, axis=1).dropna()
        w = w.rename(columns={"asset": tk}) if tk not in ("VT", "SPY") else w.assign(**{tk: w["asset"]})
        vol = r.std() * np.sqrt(ppy)
        rows.append(dict(
            ticker=tk, first_date=s.index[0].date(), last_date=s.index[-1].date(), observations=len(s),
            cagr_cad=(s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1,
            vol_cad=vol, risk_class=risk_class(vol),
            max_drawdown=dd.min(), drawdown_trough=trough.date(),
            recovery_days=(rec.index[0] - trough).days if len(rec) else None,
            current_drawdown=dd.iloc[-1],
            return_2022=y22.iloc[-1] / y22.iloc[0] - 1 if len(y22) > 1 else None,
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
