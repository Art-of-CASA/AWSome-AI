"""Collecte des données complémentaires pour AWSome AI.

Produit, dans data_extra/ :
  fundamentals_annual.csv   états financiers annuels (Yahoo Finance via yfinance), format long
  fundamentals_ratios.csv   ratios dérivés par société et exercice
  etf_overview.csv          frais, actifs sous gestion, catégorie, répartition par classe d'actifs
  etf_top_holdings.csv      10 principales positions de chaque FNB
  etf_sector_weights.csv    répartition sectorielle de chaque FNB
  news_recent.csv           titres d'actualités récents (Yahoo Finance), sans le texte des articles
  attention_wikipedia.csv   pages vues quotidiennes Wikipédia (anglais) par actif

Usage :
  python scripts/fetch_extra_data.py                       univers de départ -> data_extra/
  python scripts/fetch_extra_data.py --universe scripts/universe_extended.csv --out data_extended
  Étape seule : ajouter wiki ou ratios en argument.
Simulation uniquement. Aucune donnée personnelle.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "awsome-ai_starter"
OUT = ROOT / "data_extra"
OUT.mkdir(exist_ok=True)

START, END = "2021-11-12", "2026-11-12"
UA = {"User-Agent": "awsome-ai-datathon-research/0.1 (student project)"}

universe = pd.read_csv(STARTER / "assets_universe.csv")
EQUITIES: list[str] = []
ETFS: list[str] = []


def configure(universe_path: Path, out: Path) -> None:
    """Choisit l'univers d'actifs et le dossier de sortie."""
    global universe, EQUITIES, ETFS, OUT
    universe = pd.read_csv(universe_path)
    EQUITIES = universe.loc[universe.asset_class == "equity", "ticker"].tolist()
    ETFS = universe.loc[universe.asset_class.str.startswith("etf"), "ticker"].tolist()
    OUT = out
    OUT.mkdir(exist_ok=True)
    if "wiki_article" in universe:  # l'univers peut fournir ses propres articles Wikipédia
        WIKI.update({t: a for t, a in zip(universe.ticker, universe.wiki_article) if isinstance(a, str) and a})

# Champs retenus dans les états financiers (noms Yahoo)
FIELDS = {
    "income_stmt": ["Total Revenue", "Operating Income", "EBITDA", "Net Income", "Diluted EPS",
                    "Interest Expense"],
    "balance_sheet": ["Total Assets", "Total Debt", "Net Debt", "Stockholders Equity",
                      "Cash And Cash Equivalents", "Current Assets", "Current Liabilities"],
    "cashflow": ["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
                 "Cash Dividends Paid"],
}
# Délai prudent entre la fin d'exercice et la publication des états annuels (hypothèse).
FILING_LAG_DAYS = 90


def fetch_fundamentals() -> pd.DataFrame:
    rows = []
    for tk in EQUITIES:
        t = yf.Ticker(tk)
        try:
            fin_ccy = t.info.get("financialCurrency")
        except Exception:
            fin_ccy = None
        for stmt, fields in FIELDS.items():
            try:
                df = getattr(t, stmt)
            except Exception as e:  # noqa: BLE001
                print(f"  {tk} {stmt}: {e}")
                continue
            for f in fields:
                if f not in df.index:
                    continue
                for fy_end, v in df.loc[f].items():
                    if pd.isna(v):
                        continue
                    rows.append(dict(ticker=tk, fiscal_year_end=pd.Timestamp(fy_end).date(),
                                     statement=stmt, field=f, value=float(v),
                                     currency=fin_ccy or "unknown"))
        print(f"fundamentals {tk}: ok ({fin_ccy})")
        time.sleep(0.5)
    df = pd.DataFrame(rows)
    df["available_from"] = (pd.to_datetime(df.fiscal_year_end)
                            + pd.Timedelta(days=FILING_LAG_DAYS)).dt.date
    return df


def ratios(f: pd.DataFrame) -> pd.DataFrame:
    w = f.pivot_table(index=["ticker", "fiscal_year_end", "currency", "available_from"],
                      columns="field", values="value").reset_index().sort_values(["ticker", "fiscal_year_end"])
    g = lambda c: w[c] if c in w else pd.Series(index=w.index, dtype=float)  # noqa: E731
    out = w[["ticker", "fiscal_year_end", "currency", "available_from"]].copy()
    out["net_margin"] = g("Net Income") / g("Total Revenue")
    out["debt_to_equity"] = g("Total Debt") / g("Stockholders Equity")
    out["net_debt_to_ebitda"] = g("Net Debt") / g("EBITDA")
    out["interest_coverage"] = g("Operating Income") / g("Interest Expense").abs()
    out["fcf_margin"] = g("Free Cash Flow") / g("Total Revenue")
    out["current_ratio"] = g("Current Assets") / g("Current Liabilities")
    out["roe"] = g("Net Income") / g("Stockholders Equity")
    out["revenue_growth"] = g("Total Revenue").groupby(w.ticker).pct_change(fill_method=None)
    out["dividends_to_fcf"] = g("Cash Dividends Paid").abs() / g("Free Cash Flow")
    # Banques et assureurs : revenus, marges et flux de trésorerie ne se lisent pas comme pour
    # une entreprise industrielle (dépôts, prêts, placements). On le signale au lieu de cacher les chiffres.
    fin = set(universe.loc[universe.sector == "Financials", "ticker"])
    out["industrial_ratios_meaningful"] = ~out.ticker.isin(fin)
    return out


def fetch_etfs():
    over, hold, sect = [], [], []
    for tk in ETFS:
        fd = yf.Ticker(tk).funds_data
        rec = dict(ticker=tk)
        try:
            rec.update({f"overview_{k}": v for k, v in (fd.fund_overview or {}).items()})
        except Exception as e:  # noqa: BLE001
            print(f"  {tk} overview: {e}")
        try:
            ops = fd.fund_operations
            col = tk if tk in ops.columns else ops.columns[0]
            for k, v in ops[col].items():
                rec[f"ops_{k}"] = v
        except Exception as e:  # noqa: BLE001
            print(f"  {tk} operations: {e}")
        try:
            rec.update({f"asset_{k}": v for k, v in (fd.asset_classes or {}).items()})
        except Exception as e:  # noqa: BLE001
            print(f"  {tk} asset classes: {e}")
        try:
            h = fd.top_holdings.reset_index()
            h.columns = ["holding_symbol", "holding_name", "weight"]
            h.insert(0, "etf", tk)
            hold.append(h)
        except Exception as e:  # noqa: BLE001
            print(f"  {tk} holdings: {e}")
        try:
            for k, v in (fd.sector_weightings or {}).items():
                sect.append(dict(etf=tk, sector=k, weight=v))
        except Exception as e:  # noqa: BLE001
            print(f"  {tk} sectors: {e}")
        over.append(rec)
        print(f"etf {tk}: ok")
        time.sleep(0.5)
    return (pd.DataFrame(over),
            pd.concat(hold, ignore_index=True) if hold else pd.DataFrame(),
            pd.DataFrame(sect))


def fetch_news() -> pd.DataFrame:
    rows = []
    for tk in universe.ticker:
        try:
            items = yf.Ticker(tk).news or []
        except Exception as e:  # noqa: BLE001
            print(f"  {tk} news: {e}")
            continue
        for it in items:
            c = it.get("content", it)
            rows.append(dict(
                ticker=tk, published_utc=c.get("pubDate"), title=c.get("title"),
                provider=(c.get("provider") or {}).get("displayName"),
                url=(c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url"),
                related=",".join(sorted({s["symbol"] for s in ((c.get("finance") or {}).get("stockTickers") or [])})),
            ))
        time.sleep(0.3)
    return pd.DataFrame(rows)


# Article Wikipédia (anglais) le plus représentatif de chaque actif.
# Pour un FNB, on prend l'article de l'indice ou du fonds : c'est un indicateur d'attention, pas une mesure exacte.
WIKI = {
    "RY.TO": "Royal_Bank_of_Canada", "TD.TO": "Toronto-Dominion_Bank", "MFC.TO": "Manulife",
    "ENB.TO": "Enbridge", "CNQ.TO": "Canadian_Natural_Resources", "CNR.TO": "Canadian_National_Railway",
    "FTS.TO": "Fortis_Inc.", "ATD.TO": "Alimentation_Couche-Tard", "SHOP.TO": "Shopify",
    "CSU.TO": "Constellation_Software", "AAPL": "Apple_Inc.", "MSFT": "Microsoft", "NVDA": "Nvidia",
    "GOOGL": "Alphabet_Inc.", "AMZN": "Amazon_(company)", "TSLA": "Tesla,_Inc.",
    "JPM": "JPMorgan_Chase", "JNJ": "Johnson_&_Johnson", "PG": "Procter_&_Gamble",
    "XOM": "ExxonMobil", "XIU.TO": "S&P/TSX_60", "SPY": "SPDR_S&P_500_ETF_Trust", "QQQ": "Nasdaq-100",
    "ESGV": "Vanguard_Group", "XBB.TO": "IShares", "ZST.TO": "BMO_Global_Asset_Management",
    "AGG": "IShares", "TLT": "United_States_Treasury_security", "GLD": "SPDR_Gold_Shares",
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum",
}


def fetch_wiki() -> pd.DataFrame:
    rows = []
    s, e = START.replace("-", ""), END.replace("-", "")
    for tk, art in WIKI.items():
        if tk not in set(universe.ticker):
            continue
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
               f"all-access/user/{urllib.parse.quote(art, safe='')}/daily/{s}00/{e}00")
        data = None
        for attempt in range(6):  # l'API limite le débit (HTTP 429) : on attend puis on relance
            try:
                data = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
                break
            except Exception as ex:  # noqa: BLE001
                print(f"  wiki {tk} (essai {attempt + 1}): {ex}")
                time.sleep(5 * (attempt + 1))
        if data is None:
            continue
        for it in data.get("items", []):
            rows.append(dict(date=pd.to_datetime(it["timestamp"][:8]).date(), ticker=tk,
                             article=art, views=it["views"]))
        print(f"wiki {tk}: {len(data.get('items', []))} jours")
        time.sleep(1.5)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser()
    ap.add_argument("step", nargs="?", default="all", choices=["all", "wiki", "ratios"])
    ap.add_argument("--universe", type=Path, default=STARTER / "assets_universe.csv")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    configure(args.universe, ROOT / args.out if not args.out.is_absolute() else args.out)
    if args.step == "wiki":  # relancer seulement la partie Wikipédia
        fetch_wiki().to_csv(OUT / "attention_wikipedia.csv", index=False)
        sys.exit(0)
    if args.step == "ratios":  # recalculer les ratios sans retélécharger
        ratios(pd.read_csv(OUT / "fundamentals_annual.csv")).to_csv(OUT / "fundamentals_ratios.csv", index=False)
        sys.exit(0)
    f = fetch_fundamentals()
    f.to_csv(OUT / "fundamentals_annual.csv", index=False)
    ratios(f).to_csv(OUT / "fundamentals_ratios.csv", index=False)
    o, h, s = fetch_etfs()
    o.to_csv(OUT / "etf_overview.csv", index=False)
    h.to_csv(OUT / "etf_top_holdings.csv", index=False)
    # Yahoo renvoie une répartition factice (100 % « technology ») pour certains fonds obligataires (BNDW) :
    # une répartition concentrée à 100 % sur un seul secteur n'est pas une répartition d'actions, on l'écarte.
    if len(s):
        s = s[s.groupby("etf").weight.transform("max") < 0.999]
    s.to_csv(OUT / "etf_sector_weights.csv", index=False)
    fetch_news().to_csv(OUT / "news_recent.csv", index=False)
    fetch_wiki().to_csv(OUT / "attention_wikipedia.csv", index=False)
    print("Terminé :", sorted(p.name for p in OUT.iterdir()))
