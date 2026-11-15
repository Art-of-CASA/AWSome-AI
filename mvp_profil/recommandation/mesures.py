"""Mesures de risque d'un PORTEFEUILLE, sur les séries de prix en CAD.

Tout est descriptif : ce sont des faits passés sur une période dite, jamais une prévision.
Le portefeuille est rééquilibré chaque jour aux poids cibles (hypothèse de calcul, écrite).
"""
from __future__ import annotations

from . import chargement as ch
from . import contraintes as C
from .chargement import hypotheses, nombre, vrai


def serie(poids: dict[str, float], debut: str | None = None, fin: str | None = None, sans_annee: int | None = None):
    """Rendements quotidiens du portefeuille. Un prix manquant un jour donné compte pour un rendement nul."""
    r = ch.rendements()
    tickers = [t for t, w in poids.items() if w > 0 and t in r.columns]
    r = r[tickers].iloc[1:]
    if debut:
        r = r[r.index >= debut]
    if fin:
        r = r[r.index <= fin]
    if sans_annee:
        r = r[r.index.year != sans_annee]
    w = [poids[t] for t in tickers]
    return (r.fillna(0.0) * w).sum(axis=1)


def mesurer(poids: dict[str, float], **periode) -> dict:
    """Volatilité, perte maximale, durée sous l'eau, 2022, pire mois. Pourcentages positifs = pertes en valeur absolue."""
    import numpy as np

    s = serie(poids, **periode)
    if len(s) < 60:
        return {"erreur": "série trop courte pour mesurer le portefeuille", "observations": int(len(s))}
    valeur = (1 + s).cumprod()
    sommet = valeur.cummax()
    dd = valeur / sommet - 1
    creux = dd.idxmin()
    pic = valeur[:creux].idxmax()
    apres = valeur[creux:]
    retour = apres[apres >= valeur[pic]]
    recupere = len(retour) > 0
    jours = int(((retour.index[0] if recupere else valeur.index[-1]) - pic).days)
    a2022 = s[s.index.year == 2022]
    mensuel = (1 + s).groupby([s.index.year, s.index.month]).prod() - 1   # sans alias de fréquence : toutes versions de pandas
    return {
        "volatilite_pct": round(float(s.std() * np.sqrt(252) * 100), 1),
        "perte_max_pct": round(float(-dd.min() * 100), 1),
        "date_sommet": str(pic.date()), "date_creux": str(creux.date()),
        "jours_sous_eau": jours, "recupere": bool(recupere),
        "rendement_2022_pct": round(float(((1 + a2022).prod() - 1) * 100), 1) if len(a2022) > 200 else None,
        "pire_mois_pct": round(float(mensuel.min() * 100), 1),
        "periode": f"{s.index[0].date()} au {s.index[-1].date()}", "observations": int(len(s)),
    }


def stress(poids: dict[str, float], uni, hyp: dict | None = None, **periode) -> dict:
    """Perte de stress = la pire de : perte maximale historique, perte de 2022, choc de taux déclaré.

    Le krach des actions est un SCÉNARIO FICTIF, affiché en sensibilité : il n'entre pas dans la perte retenue.
    """
    hyp = (hyp or hypotheses())["stress"]
    m = mesurer(poids, **periode)
    if "erreur" in m:
        return {"erreur": m["erreur"]}
    taux = 0.0
    krach = 0.0
    for t, w in poids.items():
        a = uni[t]
        classe = a.get("asset_class")
        if classe == "etf_bond":
            sens = nombre(a.get("rate_sensitivity_pct_per_pt"))
            taux += w * min(0.0, (sens or 0.0)) * hyp["choc_taux_points"]
            krach += w * hyp["krach_obligations_pct"]
        elif classe == "crypto":
            krach += w * hyp["krach_crypto_pct"]
        elif classe == "etf_commodity":
            krach += w * hyp["krach_or_pct"]
        else:
            krach += w * hyp["krach_actions_pct"]
    composantes = {"perte_max_historique": m["perte_max_pct"],
                   "annee_2022": round(max(0.0, -(m["rendement_2022_pct"] or 0.0)), 1),
                   "choc_taux": round(-taux, 1)}
    cause = max(composantes, key=composantes.get)
    return {"perte_stress_pct": composantes[cause], "cause": cause, "composantes_pct": composantes,
            "scenario_fictif_krach_pct": round(-krach, 1), "choc_taux_points": hyp["choc_taux_points"],
            "mesures": m}


def expositions(poids: dict[str, float], uni) -> dict:
    """Expositions du portefeuille, en regardant à travers les FNB (principales positions et secteurs connus)."""
    secteurs_fnb, positions = ch.secteurs_fnb(), ch.positions_fnb()
    secteurs: dict[str, float] = {}
    titres: dict[str, float] = {}
    classes: dict[str, float] = {}
    roles: dict[str, float] = {}
    hors_cad = speculatif = crypto = 0.0
    for t, w in poids.items():
        if w <= 0:
            continue
        a = uni[t]
        classes[a["asset_class"]] = classes.get(a["asset_class"], 0.0) + w
        roles[a["role"]] = roles.get(a["role"], 0.0) + w
        if C.expose_change(a):
            hors_cad += w
        if vrai(a.get("speculative")):
            speculatif += w
        if a["asset_class"] == "crypto":
            crypto += w
        if a["asset_class"] == "equity":
            secteurs[a["sector"]] = secteurs.get(a["sector"], 0.0) + w
            titres[t] = titres.get(t, 0.0) + w
        elif t in secteurs_fnb:
            for sec, part in secteurs_fnb[t].items():
                secteurs[sec] = secteurs.get(sec, 0.0) + w * part
        for cible, part in positions.get(t, {}).items():
            titres[cible] = titres.get(cible, 0.0) + w * part
    arr = lambda d: {k: round(v * 100, 1) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}  # noqa: E731
    return {"secteurs_pct": arr(secteurs), "titres_pct": arr(titres), "classes_pct": arr(classes), "roles_pct": arr(roles),
            "hors_cad_pct": round(hors_cad * 100, 1), "speculatif_pct": round(speculatif * 100, 1),
            "crypto_pct": round(crypto * 100, 1),
            "couverture_positions_fnb_pct": {t: round(min(1.0, sum(p for cible, p in positions.get(t, {}).items()
                                                                          if cible in uni and p > 0)) * 100, 1)
                                             for t, w in poids.items() if w > 0 and str(uni[t]["asset_class"]).startswith("etf")},
            "limite": "À travers les FNB, seules les principales positions et la répartition sectorielle sont connues : "
                      "ces expositions sont un minimum connu, pas un inventaire complet. Pour le plafond de change, "
                      "un fonds exposé non couvert compte pour tout son poids : borne prudente, pas part exacte en devises."}


def part_secteur(ticker: str, secteur: str, uni) -> float:
    a = uni[ticker]
    if a["asset_class"] == "equity":
        return 1.0 if a.get("sector") == secteur else 0.0
    return ch.secteurs_fnb().get(ticker, {}).get(secteur, 0.0)
