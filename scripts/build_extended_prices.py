"""Prix, opérations sur titres et taux de change de l'univers étendu (Europe, Asie, Afrique, FNB mondiaux).

Même format que le jeu de départ AWSome AI, pour pouvoir fusionner les deux univers.
  data_extended/assets_universe.csv    copie de scripts/universe_extended.csv
  data_extended/prices_daily.csv       date, ticker, open, high, low, close, adj_close, volume, currency
  data_extended/corporate_actions.csv  ex_date, ticker, action, value, unit
  data_extended/fx_to_cad_daily.csv    date, currency, cad_per_unit, source

Traitements :
  - Londres cote en pence (GBp) et Johannesburg en cents (ZAc) : prix et dividendes divisés par 100
    et exprimés en GBP et ZAR.
  - Change : Banque du Canada (API Valet) quand la devise y est publiée ; sinon Yahoo Finance
    (DKK et EGP). Aucun remplissage : une ligne par jour publié.
  - Aucun alignement de calendrier, comme dans le jeu de départ.
Usage : python scripts/build_extended_prices.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_extended"
OUT.mkdir(exist_ok=True)
START, END = "2021-11-12", "2026-11-13"  # END exclusif pour yfinance : dernière date = 2026-11-12
MINOR = {"GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ZAC": ("ZAR", 100.0)}
BOC = ["EUR", "CHF", "GBP", "JPY", "HKD", "KRW", "TWD", "INR", "ZAR", "USD"]
YAHOO_FX = ["DKK", "EGP"]


WARNINGS: list[str] = []


def fix_unit_glitches(p: pd.DataFrame) -> pd.DataFrame:
    """Corrige les jours isolés où Yahoo mélange unité et sous-unité (prix 100 fois trop petit ou grand).

    Règle : si la clôture d'un jour vaut moins de 1/20 ou plus de 20 fois la médiane des 10 jours
    voisins, le jour est remis à l'échelle par 100. Chaque correction est consignée.
    """
    cols = ["open", "high", "low", "close", "adj_close"]
    for tk, g in p.groupby("ticker"):
        med = g.close.rolling(11, center=True, min_periods=5).median()
        ratio = g.close / med
        for idx in g.index[(ratio < 0.05) | (ratio > 20)]:
            factor = 100.0 if ratio[idx] < 0.05 else 0.01
            p.loc[idx, cols] = p.loc[idx, cols] * factor
            WARNINGS.append(f"{tk} {p.loc[idx, 'date']} : prix remis à l'échelle x{factor:g} "
                            f"(rapport à la médiane voisine {ratio[idx]:.4f}, erreur d'unité Yahoo)")
    return p


def prices(universe: pd.DataFrame):
    tickers = universe.ticker.tolist()
    raw = yf.download(tickers, start=START, end=END, auto_adjust=False, actions=True,
                      progress=False, threads=True, group_by="ticker")
    rows, actions, quote_ccy = [], [], {}
    for tk in tickers:
        ccy = yf.Ticker(tk).fast_info.currency
        major, div = MINOR.get(ccy, (ccy, 1.0))
        quote_ccy[tk] = ccy
        d = raw[tk].dropna(subset=["Close"]).copy()
        for c in ["Open", "High", "Low", "Close", "Adj Close"]:
            d[c] = d[c] / div
        d = d.reset_index()
        rows.append(pd.DataFrame(dict(date=d.Date.dt.date, ticker=tk, open=d.Open, high=d.High, low=d.Low,
                                      close=d.Close, adj_close=d["Adj Close"], volume=d.Volume, currency=major)))
        for _, r in d[d.Dividends > 0].iterrows():
            actions.append(dict(ex_date=r.Date.date(), ticker=tk, action="dividend",
                                value=r.Dividends / div, unit=f"{major} per share"))
        for _, r in d[d["Stock Splits"] > 0].iterrows():
            actions.append(dict(ex_date=r.Date.date(), ticker=tk, action="split",
                                value=r["Stock Splits"], unit="ratio"))
            if r["Stock Splits"] > 100:
                WARNINGS.append(f"{tk} {r.Date.date()} : « fractionnement » de {r['Stock Splits']:g} pour 1 "
                                "dans Yahoo, sans saut de prix ; métadonnée probablement erronée, ne pas l'utiliser")
        print(f"{tk}: {len(d)} jours, cotation {ccy} -> {major}")
    p = pd.concat(rows, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True)
    p = fix_unit_glitches(p)
    if p.duplicated(["ticker", "date"]).any():
        raise SystemExit("Lignes en double dans les prix")
    if (p[["open", "high", "low", "close", "adj_close"]] <= 0).any().any():
        raise SystemExit("Prix nuls ou négatifs")
    return p, pd.DataFrame(actions).sort_values(["ticker", "ex_date"]), quote_ccy


def fx() -> pd.DataFrame:
    series = ",".join(f"FX{c}CAD" for c in BOC)
    url = f"https://www.bankofcanada.ca/valet/observations/{series}/json?start_date={START}&end_date=2026-11-12"
    obs = requests.get(url, timeout=60).json()["observations"]
    rows = []
    for o in obs:
        for c in BOC:
            v = o.get(f"FX{c}CAD", {}).get("v")
            if v not in (None, ""):
                rows.append(dict(date=o["d"], currency=c, cad_per_unit=float(v),
                                 source=f"Banque du Canada, série FX{c}CAD"))
    # DKK et EGP absents de la Banque du Canada : taux croisé USD/CAD (BdC) ÷ USD/devise (Yahoo),
    # calculé seulement les jours où la Banque du Canada publie.
    usdcad = {r["date"]: r["cad_per_unit"] for r in rows if r["currency"] == "USD"}
    for c in YAHOO_FX:
        h = yf.Ticker(f"USD{c}=X").history(start=START, end=END).Close
        h.index = h.index.date
        for d, cad in usdcad.items():
            v = h.get(pd.Timestamp(d).date())
            if v is not None and v > 0:
                rows.append(dict(date=d, currency=c, cad_per_unit=cad / float(v),
                                 source=f"Croisé : BdC FXUSDCAD ÷ Yahoo USD{c}=X"))
    rows += [dict(date=d.date().isoformat(), currency="CAD", cad_per_unit=1.0, source="identité")
             for d in pd.bdate_range(START, "2026-11-12")]
    out = pd.DataFrame(rows).sort_values(["currency", "date"])
    print(out.groupby("currency").agg(n=("date", "size"), first=("date", "min"), last=("date", "max")))
    return out


if __name__ == "__main__":
    u = pd.read_csv(ROOT / "scripts" / "universe_extended.csv")
    u.to_csv(OUT / "assets_universe.csv", index=False)
    p, a, q = prices(u)
    p.to_csv(OUT / "prices_daily.csv", index=False)
    a.to_csv(OUT / "corporate_actions.csv", index=False)
    pd.Series(q, name="yahoo_quote_currency").rename_axis("ticker").to_csv(OUT / "quote_currency_raw.csv")
    fx().to_csv(OUT / "fx_to_cad_daily.csv", index=False)
    (OUT / "data_quality_warnings.txt").write_text(
        "Généré par scripts/build_extended_prices.py\n" + ("\n".join(WARNINGS) or "Aucun avertissement.") + "\n",
        encoding="utf-8")
    print("Prix :", len(p), "lignes ; opérations :", len(a))
    print("\n".join(WARNINGS))
