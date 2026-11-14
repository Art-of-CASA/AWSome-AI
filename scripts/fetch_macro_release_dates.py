"""Dates de première publication des séries macro mensuelles.

Les fichiers macro du jeu de départ sont datés au mois de référence. Pour éviter d'utiliser
une donnée avant sa publication, ce script retrouve pour chaque observation :
  - la date de première publication (première « vintage » ALFRED qui la contient) ;
  - la valeur publiée ce jour-là (avant révisions).

Séries américaines : archive ALFRED de la Fed de St. Louis (vintages réels, sans clé d'API).
Séries quotidiennes (taux) : décalage d'un jour ouvré, publiées le lendemain.
IPC canadien (Banque du Canada) : pas de vintages publics ; règle prudente, disponible le
28 du mois suivant (Statistique Canada publie l'IPC vers la troisième semaine). Hypothèse documentée.

Sortie : data_extra/macro_release_dates.csv
"""
from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
OUT = ROOT / "data_extra"
OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "alphaforge-datathon-research/0.1 (student project)"}

US_MONTHLY = ["CPIAUCSL", "UNRATE"]
VINTAGE_START, VINTAGE_END = "2021-11-01", "2026-11-13"
OBS_START = "2021-06-01"
CHUNK = 12  # ALFRED ne renvoie que 12 vintages par requête


def first_releases(series: str) -> pd.DataFrame:
    days = pd.date_range(VINTAGE_START, VINTAGE_END, freq="D")
    frames = []
    for i in range(0, len(days), CHUNK):
        chunk = days[i:i + CHUNK]
        url = ("https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=" + ",".join([series] * len(chunk))
               + "&vintage_date=" + ",".join(d.strftime("%Y-%m-%d") for d in chunk)
               + f"&cosd={OBS_START}")
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), parse_dates=["observation_date"])
        df = df[df.observation_date >= OBS_START].set_index("observation_date")
        df.columns = [pd.Timestamp(c.split("_")[-1]) for c in df.columns]
        frames.append(df)
        time.sleep(0.3)
    wide = pd.concat(frames, axis=1)
    wide = wide.apply(pd.to_numeric, errors="coerce")
    wide = wide.loc[:, ~wide.columns.duplicated()].sort_index(axis=1)
    rows = []
    for obs, row in wide.iterrows():
        avail = row.dropna()
        if avail.empty:
            rows.append(dict(series_id=series, observation_date=obs.date(), release_date=None,
                             first_value=None, method="ALFRED: jamais publiée dans la fenêtre"))
            continue
        rel = avail.index[0]
        # Une observation déjà présente dans la première vintage interrogée a été publiée avant.
        method = "ALFRED vintage" if rel > days[0] else "ALFRED: publiée avant le début de la fenêtre"
        rows.append(dict(series_id=series, observation_date=obs.date(), release_date=rel.date(),
                         first_value=avail.iloc[0], method=method))
    print(f"{series}: {len(rows)} observations")
    return pd.DataFrame(rows)


def rule_based(macro: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sid, g in macro.groupby("series_id"):
        freq = g.frequency.iloc[0]
        if sid in US_MONTHLY:
            continue
        for d, v in zip(g.date, g.value):
            if "month" in freq.lower():
                nxt = (d + pd.offsets.MonthBegin(1))
                rel = nxt + pd.Timedelta(days=27)
                method = "Règle prudente : 28 du mois suivant (hypothèse)"
            else:
                rel = d + pd.offsets.BDay(1)
                method = "Règle : jour ouvré suivant (hypothèse)"
            rows.append(dict(series_id=sid, observation_date=d.date(), release_date=rel.date(),
                             first_value=v, method=method))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    macro = pd.read_csv(STARTER / "macro_rates.csv", parse_dates=["date"])
    parts = [first_releases(s) for s in US_MONTHLY] + [rule_based(macro)]
    out = pd.concat(parts, ignore_index=True).sort_values(["series_id", "observation_date"])
    out.to_csv(OUT / "macro_release_dates.csv", index=False)
    print("Écrit :", OUT / "macro_release_dates.csv", len(out), "lignes")
