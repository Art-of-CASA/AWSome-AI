"""Ajoute à data_extended/ les actifs de scripts/universe_extended.csv qui n'y sont pas encore.

Les actifs déjà présents ne sont PAS retéléchargés : Yahoo recalcule adj_close à chaque téléchargement, et les
chiffres déjà publiés ne doivent pas bouger. Seules des lignes sont ajoutées aux fichiers existants.

Réutilise les fonctions des scripts d'origine (mêmes traitements, mêmes formats) :
  build_extended_prices.prices   prix, dividendes, fractionnements, sous-unités (pence, cents), erreurs d'unité
  fetch_extra_data               états financiers, ratios, FNB, actualités, pages vues Wikipédia
Change : Banque du Canada (API Valet) pour les devises nouvelles ; à défaut, taux croisé avec Yahoo.
Ensuite, relancer : build_esg.py (univers étendu), compute_metrics.py, build_asset_criteria.py.

Usage : python scripts/ajouter_actifs.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_extended_prices as bp  # noqa: E402
import fetch_extra_data as fe  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "data_extended"


ARRIMAGE_USD = {"SAR": 3.75}  # riyal saoudien : 3,75 pour 1 dollar américain depuis 1986


def ajouter(nom: str, df: pd.DataFrame, colonnes_libres: bool = False, cle: str | None = None) -> None:
    """Ajoute des lignes à un CSV existant, dans l'ordre de ses colonnes. colonnes_libres : union des colonnes.
    cle : colonne du ticker ; les tickers déjà présents dans le fichier sont ignorés, pour qu'une reprise après une
    interruption n'ajoute rien en double."""
    chemin = EXT / nom
    if cle and df is not None and not df.empty and chemin.exists():
        df = df[~df[cle].isin(set(pd.read_csv(chemin, usecols=[cle])[cle]))]
    if df is None or df.empty:
        print(f"  {nom} : rien à ajouter")
        return
    if not chemin.exists():
        df.to_csv(chemin, index=False)
    elif colonnes_libres:
        pd.concat([pd.read_csv(chemin), df], ignore_index=True).to_csv(chemin, index=False)
    else:
        entetes = pd.read_csv(chemin, nrows=0).columns.tolist()
        manquantes = [c for c in entetes if c not in df.columns]
        if manquantes or len(df.columns) != len(entetes):
            raise SystemExit(f"{nom} : colonnes différentes ({manquantes or sorted(set(df.columns) - set(entetes))})")
        brut = chemin.read_bytes()
        if not brut.endswith(b"\n"):
            with open(chemin, "ab") as fh:
                fh.write(b"\r\n" if b"\r\n" in brut else b"\n")
        df[entetes].to_csv(chemin, mode="a", header=False, index=False,
                           lineterminator="\r\n" if b"\r\n" in brut else "\n")
    print(f"  {nom} : +{len(df)} lignes")


def change(devises: list[str]) -> pd.DataFrame:
    """Taux vers le CAD pour des devises nouvelles, au même format que fx_to_cad_daily.csv."""
    existant = pd.read_csv(EXT / "fx_to_cad_daily.csv")
    usdcad = existant[existant.currency == "USD"].set_index("date").cad_per_unit
    rows = []
    for c in devises:
        url = (f"https://www.bankofcanada.ca/valet/observations/FX{c}CAD/json?start_date={bp.START}&end_date=2026-11-12")
        rep = requests.get(url, timeout=60)
        obs = rep.json().get("observations", []) if rep.ok else []
        vals = [(o["d"], float(o[f"FX{c}CAD"]["v"])) for o in obs if o.get(f"FX{c}CAD", {}).get("v") not in (None, "")]
        if len(vals) > 1000:
            rows += [dict(date=d, currency=c, cad_per_unit=v, source=f"Banque du Canada, série FX{c}CAD") for d, v in vals]
            print(f"  change {c} : Banque du Canada, {len(vals)} jours")
            fin = max(d for d, _ in vals)
            if c in ARRIMAGE_USD and fin < usdcad.index.max():  # série interrompue : devise arrimée au dollar américain
                suite = usdcad[usdcad.index > fin]
                rows += [dict(date=d, currency=c, cad_per_unit=round(v / ARRIMAGE_USD[c], 6),
                              source=f"Croisé : BdC FXUSDCAD ÷ {ARRIMAGE_USD[c]:g}".replace(".", ",")
                                     + " (arrimage officiel du riyal au dollar américain)") for d, v in suite.items()]
                print(f"  change {c} : série interrompue le {fin}, {len(suite)} jours complétés par l'arrimage au dollar")
            continue
        h = yf.Ticker(f"USD{c}=X").history(start=bp.START, end=bp.END).Close  # taux croisé, comme pour DKK et EGP
        h.index = h.index.date
        n = 0
        for d, cad in usdcad.items():
            v = h.get(pd.Timestamp(d).date())
            if v is not None and v > 0:
                rows.append(dict(date=d, currency=c, cad_per_unit=cad / float(v),
                                 source=f"Croisé : BdC FXUSDCAD ÷ Yahoo USD{c}=X"))
                n += 1
        print(f"  change {c} : taux croisé Yahoo, {n} jours")
    return pd.DataFrame(rows)


def capitalisations(actions: list[str]) -> pd.DataFrame:
    fx = pd.read_csv(EXT / "fx_to_cad_daily.csv").sort_values("date").groupby("currency").cad_per_unit.last()
    rows = []
    for tk in actions:
        try:
            fi = yf.Ticker(tk).fast_info
            cap, ccy = fi.market_cap, fi.currency
        except Exception as e:  # noqa: BLE001
            print(f"  capitalisation {tk} : {e}")
            continue
        ccy, div = bp.MINOR.get(ccy, (ccy, 1.0))
        cap = cap / div if cap else None
        usd = cap * fx[ccy] / fx["USD"] if cap and ccy in fx else None
        rows.append(dict(ticker=tk, market_cap_local=cap, currency=ccy, market_cap_usd=usd, retrieved_on=date.today()))
        time.sleep(0.3)
    return pd.DataFrame(rows)


def main() -> None:
    u = pd.read_csv(ROOT / "scripts" / "universe_extended.csv")
    # assets_universe.csv est écrit en dernier : un actif n'y figure qu'une fois toutes ses données ajoutées.
    deja = set(pd.read_csv(EXT / "assets_universe.csv", usecols=["ticker"]).ticker)
    nouveaux = u[~u.ticker.isin(deja)].reset_index(drop=True)
    if nouveaux.empty:
        print("Aucun actif à ajouter.")
        return
    print(f"{len(nouveaux)} actifs à ajouter : {', '.join(nouveaux.ticker)}")

    # 1. Prix, opérations sur titres, devise de cotation
    sans_prix = nouveaux[~nouveaux.ticker.isin(set(pd.read_csv(EXT / "prices_daily.csv", usecols=["ticker"]).ticker))]
    if len(sans_prix):
        p, a, q = bp.prices(sans_prix)
        attendues = dict(zip(nouveaux.ticker, nouveaux.currency))
        ecarts = {t: (c, attendues[t]) for t, c in p.groupby("ticker").currency.first().items() if c != attendues[t]}
        if ecarts:
            raise SystemExit(f"Devise de cotation différente de l'univers : {ecarts}")
        ajouter("prices_daily.csv", p)
        ajouter("corporate_actions.csv", a)
        ajouter("quote_currency_raw.csv", pd.Series(q, name="yahoo_quote_currency").rename_axis("ticker").reset_index(), cle="ticker")

    # 2. Change pour les devises nouvelles
    connues = set(pd.read_csv(EXT / "fx_to_cad_daily.csv", usecols=["currency"]).currency)
    nouvelles = sorted(set(nouveaux.currency) - connues)
    if nouvelles:
        ajouter("fx_to_cad_daily.csv", change(nouvelles))

    # 3. États financiers, FNB, actualités, attention (fonctions de fetch_extra_data, univers = les nouveaux)
    with tempfile.TemporaryDirectory() as tmp:
        chemin = Path(tmp) / "nouveaux.csv"
        nouveaux.to_csv(chemin, index=False)
        fe.configure(chemin, Path(tmp))
        if fe.EQUITIES:  # sans action dans le lot (que des FNB), il n'y a pas d'états financiers à lire
            f = fe.fetch_fundamentals()
            ajouter("fundamentals_annual.csv", f, cle="ticker")
            ajouter("fundamentals_ratios.csv", fe.ratios(f), cle="ticker")
        if fe.ETFS:
            o, h, s = fe.fetch_etfs()
            ajouter("etf_overview.csv", o[~o.ticker.isin(set(pd.read_csv(EXT / "etf_overview.csv").ticker))], colonnes_libres=True)
            ajouter("etf_top_holdings.csv", h, cle="etf")
            # Comme dans le fichier existant : pas de répartition sectorielle pour un fonds obligataire
            obligataires = set(nouveaux.loc[nouveaux.asset_class == "etf_bond", "ticker"])
            ajouter("etf_sector_weights.csv", s[~s.etf.isin(obligataires)] if len(s) else s, cle="etf")
        ajouter("news_recent.csv", fe.fetch_news(), cle="ticker")
        ajouter("attention_wikipedia.csv", fe.fetch_wiki(), cle="ticker")

    # 4. Capitalisations, univers, avertissements
    ajouter("market_caps.csv", capitalisations(nouveaux.loc[nouveaux.asset_class == "equity", "ticker"].tolist()), cle="ticker")
    u.to_csv(EXT / "assets_universe.csv", index=False)
    if bp.WARNINGS:
        with open(EXT / "data_quality_warnings.txt", "a", encoding="utf-8") as fh:
            fh.write(f"Ajout du {date.today()} (scripts/ajouter_actifs.py)\n" + "\n".join(bp.WARNINGS) + "\n")
    print("Avertissements :", *(bp.WARNINGS or ["aucun"]), sep="\n  ")


if __name__ == "__main__":
    main()
