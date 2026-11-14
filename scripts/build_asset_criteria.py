"""Calcule, pour chacun des 66 actifs, les critères qui se comparent au profil de l'investisseur.

Entrées : jeu de départ, data_extra/, data_extended/, config/seuils_criteres.json
Sortie  : data_extended/asset_criteria.csv  (une ligne par actif, une colonne par critère)

Chaque critère d'actif correspond à un critère du profil (voir docs/criteres_profil_actifs.md et
config/criteres_appariement.csv). Tout est calculé par du code à partir de données datées, sauf
les colonnes marquées « hypothèse » (thèmes, complexité, accessibilité), écrites à la main ici.
Simulation uniquement : aucune de ces valeurs n'est une recommandation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
EXTRA, EXT = ROOT / "data_extra", ROOT / "data_extended"
CFG = json.loads((ROOT / "config" / "seuils_criteres.json").read_text(encoding="utf-8"))
ASOF = pd.Timestamp("2026-11-12")

# --- Critères écrits à la main (hypothèses de l'équipe, à justifier) -------------------------
THEMES = {
    "NVDA": "ia;semi-conducteurs", "MSFT": "ia;logiciel;infonuagique", "GOOGL": "ia;publicite_numerique;infonuagique",
    "AMZN": "commerce_en_ligne;infonuagique;ia", "AAPL": "electronique_grand_public", "TSLA": "vehicule_electrique;ia",
    "SHOP.TO": "commerce_en_ligne;logiciel", "CSU.TO": "logiciel", "2330.TW": "ia;semi-conducteurs",
    "ASML.AS": "ia;semi-conducteurs", "005930.KS": "semi-conducteurs;electronique_grand_public", "SAP.DE": "logiciel;ia",
    "INFY.NS": "services_informatiques", "0700.HK": "jeux_video;reseaux_sociaux;ia", "9988.HK": "commerce_en_ligne;infonuagique;ia",
    "1211.HK": "vehicule_electrique;batteries", "7203.T": "automobile;hybride", "6758.T": "jeux_video;divertissement;electronique_grand_public",
    "NPN.JO": "holding;internet", "MC.PA": "luxe", "NESN.SW": "alimentation", "PG": "produits_menagers", "ATD.TO": "depanneurs",
    "SHP.JO": "supermarches", "NOVO-B.CO": "pharmacie;obesite", "AZN.L": "pharmacie;oncologie", "JNJ": "pharmacie;dispositifs_medicaux",
    "APN.JO": "pharmacie;generiques", "SIE.DE": "automatisation;infrastructures", "CNR.TO": "chemin_de_fer;infrastructures",
    "FTS.TO": "services_publics;infrastructures", "ENB.TO": "pipelines;infrastructures", "CNQ.TO": "petrole;sables_bitumineux",
    "XOM": "petrole;gaz", "TTE.PA": "petrole;gaz;gnl", "SHEL.L": "petrole;gaz;gnl", "RELIANCE.NS": "raffinage;telecoms;commerce",
    "SOL.JO": "chimie;carburants_synthetiques", "GFI.JO": "or;mines", "GLD": "or", "MTN.JO": "telecoms;paiement_mobile",
    "VOD.JO": "telecoms;paiement_mobile", "RY.TO": "banque", "TD.TO": "banque", "JPM": "banque", "HSBA.L": "banque",
    "HDFCBANK.NS": "banque", "FSR.JO": "banque", "SBK.JO": "banque", "COMI.CA": "banque", "MFC.TO": "assurance",
    "BTC-USD": "crypto", "ETH-USD": "crypto;contrats_intelligents", "QQQ": "technologie_large", "ESGV": "esg",
}
# Complexité pour un investisseur non spécialiste : 1 simple, 2 intermédiaire, 3 complexe.
COMPLEXITY_3 = {"BTC-USD", "ETH-USD", "NPN.JO", "COMI.CA"}  # crypto, holding à étages, devise instable
COMPLEXITY_2_CLASSES = {"etf_bond", "etf_commodity"}
# Accès pour un particulier canadien (à vérifier selon le courtier).
ACCESS = {
    "TSX": "directe", "NASDAQ": "directe", "NYSE": "directe", "NYSE Arca": "directe", "Cboe BZX": "directe",
    "Nasdaq": "directe", "Crypto (24/7)": "plateforme_crypto",
    "Euronext Amsterdam": "courtier_international", "Euronext Paris": "courtier_international", "Xetra": "courtier_international",
    "SIX Swiss Exchange": "courtier_international", "Nasdaq Copenhagen": "courtier_international",
    "London Stock Exchange": "courtier_international", "Tokyo Stock Exchange": "courtier_international",
    "Hong Kong Exchange": "courtier_international", "Johannesburg Stock Exchange": "courtier_international",
    "Taiwan Stock Exchange": "via_adr_ou_fnb", "Korea Exchange": "via_adr_ou_fnb",
    "National Stock Exchange of India": "via_adr_ou_fnb", "Egyptian Exchange": "via_fnb_seulement",
}
# Secteur d'emploi de l'investisseur -> secteurs GICS qui doublent son exposition (capital humain).
# Utilisé côté profil ; listé ici pour mémoire.


def load():
    u0 = pd.read_csv(STARTER / "assets_universe.csv")
    u1 = pd.read_csv(EXT / "assets_universe.csv")
    u = pd.concat([u0, u1], ignore_index=True)
    p = pd.concat([pd.read_csv(STARTER / "prices_daily.csv"), pd.read_csv(EXT / "prices_daily.csv")], ignore_index=True)
    p["date"] = pd.to_datetime(p.date)
    ca = pd.concat([pd.read_csv(STARTER / "corporate_actions.csv"), pd.read_csv(EXT / "corporate_actions.csv")], ignore_index=True)
    ca["ex_date"] = pd.to_datetime(ca.ex_date)
    fx = pd.read_csv(EXT / "fx_to_cad_daily.csv", parse_dates=["date"])
    met = pd.read_csv(EXT / "asset_metrics_cad.csv")
    rat = pd.concat([pd.read_csv(EXTRA / "fundamentals_ratios.csv"), pd.read_csv(EXT / "fundamentals_ratios.csv")], ignore_index=True)
    esg = pd.concat([pd.read_csv(EXTRA / "esg_screens.csv"), pd.read_csv(EXT / "esg_screens.csv")], ignore_index=True)
    wiki = pd.concat([pd.read_csv(EXTRA / "attention_wikipedia.csv"), pd.read_csv(EXT / "attention_wikipedia.csv")], ignore_index=True)
    wiki["date"] = pd.to_datetime(wiki.date)
    etf = pd.concat([pd.read_csv(EXTRA / "etf_overview.csv"), pd.read_csv(EXT / "etf_overview.csv")], ignore_index=True)
    macro = pd.read_csv(STARTER / "macro_rates.csv", parse_dates=["date"])
    return u, p, ca, fx, met, rat, esg, wiki, etf, macro


def fx_series(fx, ccy):
    return fx[fx.currency == ccy].set_index("date").cad_per_unit.sort_index()


HEBDO: dict[str, pd.Series] = {}  # rendements hebdomadaires en CAD, pour les corrélations entre actifs


def per_asset(u, p, ca, fx, macro, wiki):
    y10 = macro[macro.series_id == "DGS10"].set_index("date").value.sort_index()
    y10_w = y10.resample("W-FRI").last().diff()  # variation hebdomadaire du taux US 10 ans, en points
    rf = macro[macro.series_id == "V39079"].value.mean() / 100  # taux sans risque : taux directeur BdC moyen
    rows = []
    for _, a in u.iterrows():
        tk, ccy = a.ticker, None
        g = p[p.ticker == tk].sort_values("date").set_index("date")
        ccy = g.currency.iloc[0]
        f = fx_series(fx, ccy).reindex(g.index, method="ffill") if ccy != "CAD" else pd.Series(1.0, index=g.index)
        cad = g.adj_close * f
        r_loc, r_cad = g.adj_close.pct_change().dropna(), cad.pct_change().dropna()
        ppy = len(r_loc) / ((g.index[-1] - g.index[0]).days / 365.25)
        vol_loc, vol_cad = r_loc.std() * np.sqrt(ppy), r_cad.std() * np.sqrt(ppy)
        last = g.loc[g.index >= ASOF - pd.Timedelta(days=365)]
        adv_cad = (last.close * last.volume * f.reindex(last.index)).mean()
        # Dividendes
        d = ca[(ca.ticker == tk) & (ca.action == "dividend")].set_index("ex_date").value
        ttm = d[d.index > ASOF - pd.Timedelta(days=365)].sum()
        yearly = d.groupby(d.index.year).sum().reindex(range(2022, 2026), fill_value=0.0)
        cut = bool(((yearly.pct_change() < -CFG["baisse_dividende_annuelle_significative"]) & (yearly.shift() > 0)).any())
        years_paid = int((yearly > 0).sum())
        # Sensibilité aux taux : bêta des rendements hebdomadaires en CAD sur la variation du taux US 10 ans
        w = pd.concat({"r": cad.resample("W-FRI").last().pct_change(fill_method=None), "dy": y10_w}, axis=1).dropna()
        rate_beta = w.r.cov(w.dy) / w.dy.var() * 100 if len(w) > 50 else np.nan
        # Attention médiatique : jours de pic (z-score > seuil sur fenêtre glissante)
        wv = wiki[wiki.ticker == tk].set_index("date").views.sort_index()
        median_views = wv.median() if len(wv) else np.nan
        if len(wv) > 200:
            win = CFG["attention_fenetre_jours"]
            z = (wv - wv.rolling(win).median()) / wv.rolling(win).std()
            spikes = z > CFG["attention_pic_zscore"]
            spikes_per_year = spikes.sum() / ((wv.index[-1] - wv.index[0]).days / 365.25)
            recent_spike = bool(spikes[wv.index > ASOF - pd.Timedelta(days=30)].any())
        else:
            spikes_per_year, recent_spike = np.nan, None
        HEBDO[tk] = cad.resample("W-FRI").last().pct_change(fill_method=None)
        # Efficience rendement/risque (historique, information seulement)
        yrs = (cad.index[-1] - cad.index[0]).days / 365.25
        cagr = (cad.iloc[-1] / cad.iloc[0]) ** (1 / yrs) - 1
        downside = r_cad[r_cad < 0].std() * np.sqrt(ppy)
        # Momentum récent et volume anormal (effet de mode)
        recent = cad[cad.index > ASOF - pd.Timedelta(days=91)]
        vol_1y = last.volume[last.volume > 0]
        vol_30j = g.volume[g.index > ASOF - pd.Timedelta(days=30)]
        rows.append(dict(ticker=tk, vol_local=vol_loc, fx_vol_contribution=vol_cad - vol_loc,
                         sharpe=(cagr - rf) / vol_cad, sortino=(cagr - rf) / downside if downside > 0 else np.nan,
                         return_3m=recent.iloc[-1] / recent.iloc[0] - 1 if len(recent) > 5 else np.nan,
                         volume_spike_ratio=(vol_30j.max() / vol_1y.median()) if len(vol_1y) > 50 and vol_1y.median() > 0 else np.nan,
                         dividend_payments_12m=int((d.index > ASOF - pd.Timedelta(days=365)).sum()),
                         dividend_growth_2022_2025=(yearly[2025] / yearly[2022] - 1) if yearly[2022] > 0 else np.nan,
                         avg_daily_value_cad_12m=adv_cad, unit_price_cad=g.close.iloc[-1] * f.iloc[-1],
                         dividend_yield_ttm=ttm / g.close.iloc[-1] if ttm > 0 else 0.0,
                         dividend_years_paid_2022_2025=years_paid, dividend_cut_2022_2025=cut,
                         rate_sensitivity_pct_per_pt=rate_beta, attention_median_daily_views=median_views,
                         attention_spikes_per_year=spikes_per_year, attention_spike_last_30d=recent_spike))
    return pd.DataFrame(rows)


def fundamentals_summary(rat):
    rat = rat.copy()
    rat["available_from"] = pd.to_datetime(rat.available_from)
    rat = rat[rat.available_from <= ASOF]  # seulement ce qui était publié à la date d'analyse
    g = rat.sort_values("fiscal_year_end").groupby("ticker")
    out = pd.DataFrame({
        "fiscal_years": g.size(),
        "profitable_years_share": g.net_margin.apply(lambda s: (s.dropna() > 0).mean() if s.notna().any() else np.nan),
        "revenue_growth_avg": g.revenue_growth.apply(lambda s: s.dropna().mean() if s.notna().any() else np.nan),
        "debt_to_equity_last": g.debt_to_equity.last(),
        "interest_coverage_last": g.interest_coverage.last(),
        "roe_last": g.roe.last(),
        "fcf_margin_last": g.fcf_margin.last(),
        "dividends_to_fcf_last": g.dividends_to_fcf.last(),
        "industrial_ratios_meaningful": g.industrial_ratios_meaningful.last(),
    })
    return out.reset_index()


def classify(df):
    c = CFG
    df["horizon_min_years"] = df.risk_class.astype(str).map(c["horizon_min_ans_par_classe"]).astype(int)
    df.loc[df.recovery_days.isna(), "horizon_min_years"] += c["horizon_min_plus_si_non_recupere"]
    df["stress_loss"] = np.minimum(df.max_drawdown, df.return_2022.fillna(0).clip(upper=0))
    liq = c["liquidite_cad_par_jour"]
    df["liquidity_level"] = np.select([df.avg_daily_value_cad_12m >= liq["elevee"], df.avg_daily_value_cad_12m >= liq["moyenne"]],
                                      ["elevee", "moyenne"], "faible")
    df.loc[df.asset_class == "crypto", "liquidity_level"] = "elevee"
    df["high_unit_price"] = df.unit_price_cad > c["prix_unitaire_eleve_cad"]
    df["fx_risk"] = np.where(df.currency == "CAD", "aucun",
                             np.where(df.fx_vol_contribution.abs() >= c["change_contribution_notable"], "notable", "present"))
    df["rate_sensitivity"] = np.select(
        [df.rate_sensitivity_pct_per_pt <= -c["sensibilite_taux_notable_pct_par_point"],
         df.rate_sensitivity_pct_per_pt >= c["sensibilite_taux_notable_pct_par_point"]], ["baisse_si_taux_montent", "hausse_si_taux_montent"], "faible")
    df["income_asset"] = (df.dividend_yield_ttm >= c["revenu_rendement_dividende_min"]) & ~df.dividend_cut_2022_2025
    df["speculative"] = (df.asset_class == "crypto") | (df.vol_cad >= c["speculatif_volatilite_min"]) | \
                        (df.max_drawdown <= -c["speculatif_perte_max_min"])
    df["established"] = (df.asset_class == "equity") & (df.profitable_years_share == 1) & \
                        (df.dividend_years_paid_2022_2025 == 4) & ~df.speculative
    # Croissance nominale non comparable dans une devise à forte inflation (ex. livre égyptienne).
    df.loc[df.currency.isin(c["devises_forte_inflation"]), "revenue_growth_avg"] = np.nan
    df["growth"] = df.revenue_growth_avg >= c["croissance_revenus_forte"]
    df["defensive"] = ((df.vol_cad <= c["defensif_volatilite_max"]) & (df.beta_vt_weekly <= c["defensif_beta_max"])) | (df.risk_class <= 4)
    df["diversifier_vs_world"] = df.corr_vt_weekly <= c["diversifiant_correlation_vt_max"]
    # Médiatisation relative à l'univers : forte audience ET pics fréquents (quantiles, pas de seuil absolu).
    lvl = df.attention_median_daily_views.quantile(c["attention_niveau_fort_quantile"])
    pk = df.attention_spikes_per_year.quantile(c["attention_pics_quantile"])
    df["media_hype"] = np.select(
        [df.attention_spikes_per_year.isna() | (df.asset_class != "equity") & (df.asset_class != "crypto"),
         (df.attention_median_daily_views >= lvl) & (df.attention_spikes_per_year >= pk),
         df.attention_median_daily_views >= lvl],
        ["non_applicable", "tres_mediatise", "tres_suivi"], "normale")
    df["themes"] = df.ticker.map(THEMES).fillna("")
    df["complexity"] = np.where(df.ticker.isin(COMPLEXITY_3), 3,
                                np.where(df.asset_class.isin(COMPLEXITY_2_CLASSES) | ~df.region.isin(["Amérique du Nord", "Monde"]), 2, 1))
    df.loc[df.asset_class == "crypto", "complexity"] = 3
    df["access_canada"] = df.market.map(ACCESS).fillna("a_verifier")
    df["foreign_dividend_withholding"] = np.where((df.currency == "CAD") | (df.dividend_yield_ttm == 0), "non", "oui_a_verifier")
    df["role"] = np.select([df.asset_class.isin(["etf_bond"]), df.ticker.isin(["GLD"]), df.income_asset, df.defensive,
                            df.speculative, df.growth], ["stabilisateur", "couverture", "revenu", "defensif", "speculatif", "croissance"],
                           "coeur")
    return df


# ---------- Mots-clés (vocabulaire du tableau « critères et mots-clés résultants » de l'équipe) ----------
# Implications connues, écrites à la main, NON exhaustives (le seuil de revenus n'est pas disponible).
EXCLUSIONS = {
    "MC.PA": ["alcool"],                                   # vins et spiritueux (Moët Hennessy)
    "MSFT": ["contrats_de_defense"], "AMZN": ["contrats_de_defense"], "GOOGL": ["contrats_de_defense"],  # contrat infonuagique JWCC du Pentagone (2022)
    "JNJ": ["tests_sur_animaux"], "AZN.L": ["tests_sur_animaux"], "NOVO-B.CO": ["tests_sur_animaux"],
    "APN.JO": ["tests_sur_animaux"],                       # pharmacie : essais précliniques exigés par la réglementation
    "ENB.TO": ["atteinte_droits_autochtones"],             # ligne 5, Bad River (décision confirmée en appel, 2026)
}
SECTEURS_DEFENSIFS = {"Consumer Staples", "Utilities", "Health Care", "Communication Services"}
SECTEURS_CYCLIQUES = {"Consumer Discretionary", "Materials", "Industrials", "Energy", "Financials", "Information Technology"}


def _tranche(x, bornes, noms, defaut="non_disponible"):
    if pd.isna(x):
        return defaut
    for b, n in zip(bornes, noms):
        if x < b:
            return n
    return noms[-1]


def mots_cles(df, caps: pd.Series, top10: pd.Series, n_top: pd.Series) -> pd.DataFrame:
    """Colonnes kw_* : chaque valeur est un mot-clé du tableau de l'équipe, calculé à partir de nos données."""
    eq = df.asset_class == "equity"
    pct = lambda s: -s * 100  # noqa: E731  (perte en % positif)
    df["kw_perte_max_historique"] = [_tranche(pct(x), [10, 20, 30, 40, 1e9], ["moins_10", "10_20", "20_30", "30_40", "plus_40"])
                                     for x in df.max_drawdown]
    df["kw_volatilite"] = [_tranche(v * 100, [8, 15, 25, 1e9], ["faible_moins_8", "moderee_8_15", "elevee_15_25", "tres_elevee_plus_25"])
                           for v in df.vol_cad]
    df["kw_recuperation"] = [("non_recupere" if pd.isna(d) else _tranche(d, [365, 730, 1e9], ["rapide_moins_1_an", "moyenne_1_2_ans", "longue_plus_2_ans"]))
                             for d in df.recovery_days]
    df["kw_choc_2022"] = [("hausse" if r > 0 else _tranche(-r * 100, [10, 25, 1e9], ["baisse_limitee_moins_10", "baisse_moderee_10_25", "baisse_forte_plus_25"]))
                          if pd.notna(r) else "non_disponible" for r in df.return_2022]
    df["kw_beta"] = [_tranche(b, [0.7, 1.2, 1e9], ["faible_moins_0_7", "neutre_0_7_1_2", "eleve_plus_1_2"]) for b in df.beta_vt_weekly]
    bndw = HEBDO["BNDW"]
    df["corr_obligations_weekly"] = [HEBDO[t].corr(bndw) for t in df.ticker]
    df["kw_diversification"] = ["correlation_negative" if c < 0 else "faible_correlation_marche" if c <= 0.3
                                else "correle_actions" for c in df.corr_vt_weekly]
    df.loc[df.corr_obligations_weekly >= 0.5, "kw_diversification"] = "correle_obligations"
    df["kw_rendement_dividende"] = [("aucun" if y == 0 else _tranche(y * 100, [1, 3, 5, 1e9], ["faible_moins_1", "moyen_1_3", "eleve_3_5", "tres_eleve_plus_5_a_examiner"]))
                                    for y in df.dividend_yield_ttm]
    def durabilite(r):
        if r.dividend_yield_ttm == 0:
            return "sans_dividende"
        tags = ["dividende_reduit_ou_suspendu" if r.dividend_cut_2022_2025 else
                "croissance_du_dividende" if r.dividend_growth_2022_2025 > 0.10 else "dividende_stable"]
        if pd.notna(r.dividends_to_fcf_last) and r.industrial_ratios_meaningful is True:
            tags.append("ratio_distribution_soutenable" if 0 < r.dividends_to_fcf_last <= 0.75 else "ratio_distribution_eleve")
        return ";".join(tags)
    df["kw_dividende_durabilite"] = df.apply(durabilite, axis=1)
    df["kw_distribution"] = ["capitalisant" if n == 0 else "distribution_mensuelle" if n >= 10 else "distribuant"
                             for n in df.dividend_payments_12m]
    cap = df.ticker.map(caps)
    df["market_cap_usd"] = cap
    df["kw_capitalisation"] = [(_tranche(c / 1e9, [0.3, 2, 10, 1e12], ["micro", "petite", "moyenne", "grande"]) if e else "non_applicable")
                               for c, e in zip(cap, eq)]
    def sante(r):
        if not (r.asset_class == "equity"):
            return "non_applicable"
        if r.industrial_ratios_meaningful is not True:
            return "banque_ou_assureur_ratios_specifiques"
        t = []
        if pd.notna(r.debt_to_equity_last) and r.debt_to_equity_last < 0.5: t.append("faible_endettement")
        if pd.notna(r.roe_last) and r.roe_last > 0.15: t.append("rentabilite_elevee_roe")
        if pd.notna(r.fcf_margin_last) and r.fcf_margin_last > 0: t.append("flux_tresorerie_positifs")
        if pd.notna(r.interest_coverage_last) and r.interest_coverage_last > 8: t.append("couverture_interets_elevee")
        if r.profitable_years_share == 1: t.append("resultats_stables")
        if pd.notna(r.profitable_years_share) and r.profitable_years_share < 0.5: t.append("pertes_recurrentes")
        return ";".join(t) or "aucun_signal_positif"
    df["kw_sante_financiere"] = df.apply(sante, axis=1)
    df["kw_croissance_resultats"] = [("non_applicable" if not e else "non_comparable" if pd.isna(g) else
                                      "forte_plus_15" if g >= 0.15 else "moderee" if g >= 0.03 else "stable" if g >= -0.03 else "en_declin")
                                     for g, e in zip(df.revenue_growth_avg, eq)]
    df["kw_cycle"] = ["defensif" if s in SECTEURS_DEFENSIFS else "cyclique" if s in SECTEURS_CYCLIQUES
                      else "refuge" if t == "GLD" else "obligataire" if a == "etf_bond" else "speculatif" if a == "crypto" else "marche_large"
                      for s, t, a in zip(df.sector, df.ticker, df.asset_class)]
    def macro(r):
        t = []
        if r.rate_sensitivity == "baisse_si_taux_montent": t.append("sensible_aux_taux")
        if r.sector == "Energy" or "petrole" in r.themes or r.fossil_involvement == "directe": t.append("sensible_au_petrole")
        if r.fx_risk == "notable" or (r.currency != "CAD" and abs(r.fx_vol_contribution) >= 0.02): t.append("sensible_aux_devises")
        return ";".join(t) or "aucune_sensibilite_marquee"
    df["kw_sensibilite_macro"] = df.apply(macro, axis=1)
    df["kw_protection_inflation"] = ["or" if ("or" in th.split(";")) else "matieres_premieres_energie" if s == "Energy"
                                     else "a_resiste_en_2022" if (pd.notna(r) and r > 0) else "sans_protection_demontree"
                                     for th, s, r in zip(df.themes, df.sector, df.return_2022)]
    df["kw_frais"] = [(_tranche(f * 100, [0.15, 0.5, 1, 1e9], ["ultra_reduits_moins_0_15", "faibles_0_15_0_50", "moderes_0_50_1", "eleves_plus_1"])
                       if pd.notna(f) else "non_applicable") for f in df.etf_expense_ratio]
    # Un FNB dont moins de 6 lignes pèsent plus de 80 % détient d'autres fonds (XEQT, BNDW) : la règle des
    # 10 premières positions ne s'applique pas. (Pour AGG, Yahoo ne renvoie qu'une ligne de liquidités : non concerné.)
    df["kw_concentration"] = ["titre_individuel" if a == "equity" else "actif_unique" if a in ("crypto", "etf_commodity")
                              else "fonds_de_fonds_diversifie" if n_top.get(t, 10) < 6 and top10.get(t, 0) > 0.80
                              else ("fonds_diversifie;forte_ponderation_10_premiers" if top10.get(t, 0) > 0.40 else "fonds_diversifie")
                              for a, t in zip(df.asset_class, df.ticker)]
    def attention(r):
        t = {"tres_mediatise": ["tres_mediatise"], "tres_suivi": ["tres_suivi"], "normale": ["peu_mediatise"]}.get(r.media_hype, [])
        if pd.notna(r.return_3m) and abs(r.return_3m) > 0.30: t.append("variation_recente_extreme")
        if pd.notna(r.volume_spike_ratio) and r.volume_spike_ratio > 3: t.append("pic_de_volume_anormal")
        return ";".join(t) or "non_applicable"
    df["kw_attention"] = df.apply(attention, axis=1)
    df["kw_efficience"] = [_tranche(s, [0.3, 0.8, 1e9], ["ratio_faible", "ratio_moyen", "ratio_eleve"]) for s in df.sharpe]
    df["kw_risque_pays"] = ["exposition_chine" if c == "Chine" else "exposition_chine_partielle" if t in ("VWO", "VT")
                            else "devise_instable" if c == "Égypte" else "marche_emergent" if c in ("Inde", "Afrique du Sud", "Taïwan", "Corée du Sud")
                            else "pays_developpe" if a != "crypto" else "sans_pays"
                            for c, t, a in zip(df.country, df.ticker, df.asset_class)]
    df["kw_devise"] = [("sans_devise_souveraine" if a == "crypto" else "cad_actifs_etrangers_non_couverts" if t == "XEQT.TO"
                        else "usd_couvert" if t == "BNDW" else "cad" if c == "CAD" else "usd" if c == "USD" else "autre_devise")
                       for a, t, c in zip(df.asset_class, df.ticker, df.currency)]
    df["kw_fiscalite"] = [("revenu_interets" if a == "etf_bond" else "gains_en_capital_seulement" if y == 0
                           else "dividendes_canadiens_admissibles" if (m == "TSX" and a == "equity") else
                           "distributions_canadiennes" if c == "CAD" else "dividendes_etrangers")
                          for a, y, m, c in zip(df.asset_class, df.dividend_yield_ttm, df.market, df.currency)]
    df["kw_exclusions"] = [";".join((["energie_fossile"] if f == "directe" else []) + EXCLUSIONS.get(t, [])) or "aucune_connue"
                           for t, f in zip(df.ticker, df.fossil_involvement)]
    return df


if __name__ == "__main__":
    u, p, ca, fx, met, rat, esg, wiki, etf, macro = load()
    base = met.merge(u[["ticker", "market", "country"]], on="ticker", how="left")
    base["country"] = base.country.fillna(base.region)
    df = base.merge(per_asset(u, p, ca, fx, macro, wiki), on="ticker") \
             .merge(fundamentals_summary(rat), on="ticker", how="left") \
             .merge(esg[["ticker", "fossil_involvement", "in_jantzi_social_index", "controversies", "max_severity", "controversy_topics"]], on="ticker", how="left") \
             .merge(etf[["ticker", "ops_Annual Report Expense Ratio"]].rename(columns={"ops_Annual Report Expense Ratio": "etf_expense_ratio"}), on="ticker", how="left")
    df = classify(df)
    caps = pd.read_csv(EXT / "market_caps.csv").set_index("ticker").market_cap_usd
    top = pd.concat([pd.read_csv(EXTRA / "etf_top_holdings.csv"), pd.read_csv(EXT / "etf_top_holdings.csv")])
    df = mots_cles(df, caps, top.groupby("etf").weight.sum(), top.groupby("etf").size())
    df.to_csv(EXT / "asset_criteria.csv", index=False)
    kw = [c for c in df.columns if c.startswith("kw_")]
    pd.set_option("display.width", 250, "display.max_colwidth", 60)
    for c in kw:
        print(f"{c:28s}", df[c].str.split(";").explode().value_counts().to_dict())
    print(f"\n{len(df)} actifs, {df.shape[1]} colonnes -> data_extended/asset_criteria.csv")
