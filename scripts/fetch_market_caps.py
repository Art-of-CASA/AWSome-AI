"""Capitalisation boursière des actions (jeu de départ + univers étendu), convertie en USD.

Sortie : data_extended/market_caps.csv  (ticker, market_cap_local, currency, market_cap_usd, retrieved_on)
Source : Yahoo Finance via yfinance (fast_info.market_cap), instantané du jour de collecte.
Conversion : taux de data_extended/fx_to_cad_daily.csv (dernier jour publié), devise -> CAD -> USD.
"""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
EXT = ROOT / "data_extended"
MINOR = {"GBp": ("GBP", 100.0), "ZAc": ("ZAR", 100.0)}

u = pd.concat([pd.read_csv(STARTER / "assets_universe.csv"), pd.read_csv(EXT / "assets_universe.csv")])
fx = pd.read_csv(EXT / "fx_to_cad_daily.csv", parse_dates=["date"]).sort_values("date").groupby("currency").cad_per_unit.last()
rows = []
for tk in u.loc[u.asset_class == "equity", "ticker"]:
    try:
        fi = yf.Ticker(tk).fast_info
        cap, ccy = fi.market_cap, fi.currency
    except Exception as e:  # noqa: BLE001
        print(f"  {tk}: {e}")
        continue
    ccy, div = MINOR.get(ccy, (ccy, 1.0))
    cap = cap / div if cap else None
    usd = cap * fx[ccy] / fx["USD"] if cap and ccy in fx else None
    rows.append(dict(ticker=tk, market_cap_local=cap, currency=ccy, market_cap_usd=usd, retrieved_on=date.today()))
    print(f"{tk}: {usd / 1e9 if usd else float('nan'):.1f} G$ US")
    time.sleep(0.3)
pd.DataFrame(rows).to_csv(EXT / "market_caps.csv", index=False)
