"""Filtres ESG et controverses documentées, pour le persona Mateo.

Le jeu de départ ne contient aucune donnée ESG. Plutôt que d'inventer une note, on combine
trois éléments vérifiables, chacun avec sa source :

1. Implication dans les énergies fossiles : règle déterministe sur l'activité de l'entreprise
   (et, pour les FNB, part du secteur énergie publiée par Yahoo Finance).
2. Appartenance à l'indice Jantzi Social (FNB iShares XEN), fichier public des positions de
   BlackRock Canada. Attention : c'est une sélection « meilleur de sa catégorie », pas un filtre
   d'exclusion. Enbridge et CNQ y figurent.
3. Controverses : liste établie à la main le 14 novembre 2026 à partir de sources publiques
   (décisions de justice, autorités de réglementation, presse). Non exhaustive.

Sévérité (hypothèse de l'équipe, à déclarer) :
  élevée  = culpabilité reconnue, sanction acceptée ou décision de justice défavorable sur le fond
  moyenne = poursuite en cours, règlement, mesure administrative ou rappel de sécurité
  faible  = litige notable tranché en faveur de l'entreprise
Usage : python scripts/build_esg.py [--universe scripts/universe_extended.csv --out data_extended]
Sorties : data_extra/esg_controversies.csv, data_extra/esg_screens.csv,
          data_extra/raw/xen_holdings_<date>.csv
"""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "Datathon2026" / "alphaforge_starter"
OUT = ROOT / "data_extra"
RAW = OUT / "raw"
RAW.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "alphaforge-datathon-research/0.1 (student project)"}

XEN_URL = ("https://www.blackrock.com/ca/investors/en/products/239574/ishares-jantzi-social-index-etf/"
           "1464253357814.ajax?fileType=csv&fileName=XEN_holdings&dataType=fund")

CONTROVERSIES = [
    dict(ticker="TD.TO", event_date="2024-10-10", pillar="G", topic="Lutte contre le blanchiment",
         summary="TD Bank (filiale américaine) plaide coupable de violations de la loi américaine sur le secret bancaire "
                 "et de complot de blanchiment ; pénalités totales d'environ 3 G$ US et restrictions d'activité.",
         status="Culpabilité reconnue", severity="élevée",
         source="https://www.justice.gov/criminal/case/united-states-america-v-td-bank-na"),
    dict(ticker="ENB.TO", event_date="2026-07-30", pillar="E/S", topic="Ligne 5, terres autochtones (Bad River)",
         summary="La Cour d'appel du 7e circuit confirme que la ligne 5 empiète sans droit sur la réserve de la bande "
                 "de Bad River depuis 2013 et doit être déplacée ; dommages à recalculer. Enbridge conteste.",
         status="Décision défavorable confirmée en appel", severity="élevée",
         source="https://www.mprnews.org/story/2026/08/06/federal-appeals-court-finds-enbridge-trespassing-on-tribal-lands-must-remove-line-5"),
    dict(ticker="GOOGL", event_date="2024-08-05", pillar="G", topic="Concurrence",
         summary="Jugement fédéral (juge Mehta) : Google a maintenu illégalement un monopole sur la recherche générale ; "
                 "mesures correctives prononcées le 2 septembre 2025.",
         status="Décision défavorable sur le fond", severity="élevée",
         source="https://www.jenner.com/en/news-insights/client-alerts/key-takeaways-from-united-states-v-google"),
    dict(ticker="JNJ", event_date="2025-03-31", pillar="S", topic="Sécurité des produits (talc)",
         summary="Rejet du troisième plan de faillite (Red River Talc) visant à régler les poursuites liées au talc ; "
                 "J&J n'a pas fait appel et défend les dossiers un par un.",
         status="Litiges en cours", severity="moyenne",
         source="https://www.pharmaceutical-technology.com/news/judge-rejects-jjs-9bn-talc-settlement-for-third-time/"),
    dict(ticker="TSLA", event_date="2023-12-12", pillar="S", topic="Sécurité des produits (Autopilot)",
         summary="Rappel NHTSA 23V838000 d'environ 2 millions de véhicules : contrôles de l'Autopilot jugés insuffisants "
                 "contre une mauvaise utilisation ; correctif logiciel, enquête poursuivie.",
         status="Rappel de sécurité", severity="moyenne",
         source="https://www.insurancejournal.com/news/national/2023/12/13/751849.htm"),
    dict(ticker="AMZN", event_date="2025-09-25", pillar="G", topic="Protection du consommateur (Prime)",
         summary="Règlement de 2,5 G$ US avec la FTC (1 G$ de pénalité civile, 1,5 G$ de remboursements) pour des "
                 "inscriptions et résiliations Prime trompeuses ; sans admission de faute.",
         status="Règlement sans admission", severity="moyenne",
         source="https://www.retailtouchpoints.com/features/news-briefs/amazon-settles-ftc-suit-alleging-prime-membership-trickery-for-2-5-billion"),
    dict(ticker="AAPL", event_date="2024-03-21", pillar="G", topic="Concurrence",
         summary="Le département de la Justice et 16 procureurs généraux poursuivent Apple pour monopolisation du marché "
                 "des téléphones intelligents. Apple conteste.",
         status="Poursuite en cours", severity="moyenne",
         source="https://www.justice.gov/archives/opa/pr/justice-department-sues-apple-monopolizing-smartphone-markets"),
    dict(ticker="XOM", event_date="2024-09-23", pillar="E", topic="Recyclage du plastique",
         summary="La Californie poursuit ExxonMobil pour avoir présenté le recyclage du plastique comme une solution "
                 "en le sachant inefficace. ExxonMobil conteste.",
         status="Poursuite en cours", severity="moyenne",
         source="https://www.nbcnews.com/science/environment/california-sues-exxonmobil-plastic-recycling-deception-rcna172267"),
    dict(ticker="JPM", event_date="2023-09-26", pillar="S/G", topic="Affaire Epstein",
         summary="Règlement de 75 M$ US avec les Îles Vierges américaines, après 290 M$ US versés aux victimes en juin 2023, "
                 "pour des liens avec Jeffrey Epstein ; sans admission de faute.",
         status="Règlement sans admission", severity="moyenne",
         source="https://www.cnbc.com/2023/09/26/jpmorgan-to-settle-jeffrey-epstein-suit-by-virgin-islands.html"),
    # --- Univers étendu (Europe, Asie, Afrique), recherche du 14 novembre 2026 ---
    dict(ticker="TTE.PA", event_date="2025-10-23", pillar="E", topic="Écoblanchiment (allégations climatiques)",
         summary="Le tribunal judiciaire de Paris juge trompeuses certaines allégations de neutralité carbone et de "
                 "transition énergétique sur le site grand public ; la plupart des autres demandes sont rejetées.",
         status="Décision défavorable sur le fond (partielle)", severity="élevée",
         source="https://www.pwclegal.be/en/news/paris-court-issues-landmark-greenwashing-ruling-against-totalene.html"),
    dict(ticker="SHEL.L", event_date="2024-11-12", pillar="E", topic="Procès climatique (Milieudefensie)",
         summary="La Cour d'appel de La Haye annule l'obligation de réduire les émissions de 45 % d'ici 2030 imposée en 2021, "
                 "tout en reconnaissant une obligation générale de réduction.",
         status="Demandes rejetées en appel", severity="faible",
         source="https://www.rechtspraak.nl/organisatie-en-contact/organisatie/gerechtshoven/gerechtshof-den-haag/nieuws/2024/11/hague-court-denies-claim-for-reduction-in-shells-co2-emissions"),
    dict(ticker="SAP.DE", event_date="2024-01-10", pillar="G", topic="Corruption (FCPA)",
         summary="Règlement de plus de 220 M$ US avec le DOJ et la SEC pour des pots-de-vin versés à des agents publics "
                 "(Afrique du Sud, Indonésie et autres) ; accord de poursuite différée de trois ans.",
         status="Règlement (accord de poursuite différée)", severity="moyenne",
         source="https://www.davispolk.com/insights/client-update/sap-resolves-fcpa-case-220-million"),
    dict(ticker="MC.PA", event_date="2024-06-10", pillar="S", topic="Chaîne d'approvisionnement (travail)",
         summary="Un tribunal de Milan place l'unité italienne de Dior sous administration judiciaire pour défaut de "
                 "contrôle de sous-traitants exploitant des travailleurs ; mesure levée de façon anticipée en 2025.",
         status="Mesure judiciaire levée", severity="moyenne",
         source="https://fortune.com/europe/2024/06/11/lvmh-italian-dior-maker-investigation-luxury-goods-labor-exploitation-workers/"),
    dict(ticker="NESN.SW", event_date="2024-09", pillar="S/G", topic="Eaux minérales (traitements interdits)",
         summary="Nestlé Waters paie 2 M€ (convention judiciaire d'intérêt public, sans reconnaissance de culpabilité) "
                 "pour des traitements et forages illégaux en France ; enquête pour fraude ouverte en 2025.",
         status="Règlement sans admission ; enquête en cours", severity="moyenne",
         source="https://www.just-drinks.com/news/nestle-fined-e2m-to-close-mineral-water-investigations-in-france"),
    dict(ticker="7203.T", event_date="2024-06-03", pillar="G", topic="Certification des véhicules",
         summary="Toyota reconnaît des essais de certification non conformes aux normes japonaises sur sept modèles ; "
                 "arrêt de livraisons et inspection du ministère des Transports.",
         status="Irrégularités reconnues", severity="moyenne",
         source="https://www.just-auto.com/newsletters/toyota-admits-improper-safety-tests"),
    dict(ticker="1211.HK", event_date="2025-05-27", pillar="S", topic="Conditions de travail (Brésil)",
         summary="Le ministère public du travail brésilien poursuit BYD et deux sous-traitants pour des conditions "
                 "analogues à l'esclavage sur le chantier de son usine de Camaçari (220 travailleurs secourus).",
         status="Poursuite en cours", severity="moyenne",
         source="https://fortune.com/2025/05/29/brazil-sues-byd-china-worker-conditions-analogous-to-slavery/"),
    dict(ticker="9988.HK", event_date="2021-04-10", pillar="G", topic="Concurrence",
         summary="Amende record de 18,2 G yuans (environ 2,8 G$ US) du régulateur chinois du marché pour exclusivité "
                 "imposée aux commerçants ; Alibaba accepte la sanction.",
         status="Sanction acceptée", severity="élevée",
         source="https://www.caixinglobal.com/2021-04-10/alibaba-fined-28-billion-in-landmark-china-antitrust-ruling-101688439.html"),
    dict(ticker="MTN.JO", event_date="2023-09", pillar="S/G", topic="Financement présumé du terrorisme",
         summary="Un tribunal fédéral de New York laisse avancer une poursuite (Anti-Terrorism Act) alléguant des paiements "
                 "aux talibans et des liens avec l'Iran ; MTN nie les allégations.",
         status="Poursuite en cours", severity="moyenne",
         source="https://www.connectingafrica.com/regulation/mtn-s-us-anti-terrorism-cases-move-to-discovery-phase"),
    dict(ticker="0700.HK", event_date="2025-01-06", pillar="G", topic="Désignation militaire américaine",
         summary="Le Pentagone ajoute Tencent à la liste 1260H des « entreprises militaires chinoises » ; Tencent "
                 "conteste. Pas de sanction immédiate.",
         status="Désignation administrative contestée", severity="moyenne",
         source="https://www.morganlewis.com/pubs/2025/01/dods-expanding-list-of-chinese-military-companies"),
]

# Implication dans les énergies fossiles selon l'activité principale (règle documentée).
FOSSIL = {
    "CNQ.TO": ("directe", "Production de pétrole, de gaz et de sables bitumineux"),
    "XOM": ("directe", "Exploration, production et raffinage de pétrole et de gaz"),
    "ENB.TO": ("directe", "Transport par pipeline et distribution de pétrole et de gaz"),
    "FTS.TO": ("partielle", "Services publics, dont distribution de gaz naturel"),
    "TTE.PA": ("directe", "Exploration, production et raffinage de pétrole et de gaz, GNL"),
    "SHEL.L": ("directe", "Exploration, production et raffinage de pétrole et de gaz, GNL"),
    "RELIANCE.NS": ("directe", "Raffinage et pétrochimie (première activité par les revenus), télécoms et commerce"),
    "SOL.JO": ("directe", "Carburants et produits chimiques à partir de charbon et de gaz (Secunda)"),
}


def xen_holdings() -> pd.DataFrame:
    r = requests.get(XEN_URL, headers=UA, timeout=60)
    r.raise_for_status()
    text = r.content.decode("utf-8-sig")
    as_of = text.splitlines()[0].split(",", 1)[1].strip().strip('"')
    as_of = pd.to_datetime(as_of).date()
    (RAW / f"xen_holdings_{as_of}.csv").write_text(text, encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Ticker,"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df = df[df["Asset Class"] == "Equity"].copy()
    df["as_of"] = as_of
    return df


def main(universe_path: Path, out: Path) -> None:
    universe = pd.read_csv(universe_path)
    contro = pd.DataFrame(CONTROVERSIES)
    contro = contro[contro.ticker.isin(universe.ticker)].copy()
    contro["researched_on"] = date(2026, 11, 14)
    contro.to_csv(out / "esg_controversies.csv", index=False)

    has_tsx = ((universe.market == "TSX") & (universe.asset_class == "equity")).any()
    if has_tsx:  # l'indice Jantzi ne concerne que les actions canadiennes
        xen = xen_holdings()
        xen_set, xen_asof = set(xen.Ticker.astype(str)), xen.as_of.iloc[0]
    else:
        xen_set, xen_asof = set(), None

    sect = pd.read_csv(out / "etf_sector_weights.csv")
    energy_w = sect[sect.sector == "energy"].set_index("etf").weight

    rows = []
    for _, a in universe.iterrows():
        tk = a.ticker
        base = tk.replace(".TO", "")
        fossil, fossil_note = FOSSIL.get(tk, ("aucune", "Activité principale hors énergies fossiles"))
        if a.asset_class.startswith("etf"):
            w = energy_w.get(tk)
            fossil = "non disponible" if pd.isna(w) else f"part énergie {w:.1%}"
            fossil_note = "Part du secteur énergie publiée par Yahoo Finance (fund data)"
            if a.asset_class in ("etf_bond", "etf_commodity"):
                fossil, fossil_note = "non applicable", "Fonds obligataire ou d'or : pas de répartition sectorielle en actions"
        if a.asset_class == "crypto":
            fossil, fossil_note = "indirecte", "Consommation d'énergie du minage (Bitcoin) ; Ether en preuve d'enjeu depuis 2022"
        c = contro[contro.ticker == tk]
        rows.append(dict(
            ticker=tk,
            fossil_involvement=fossil,
            fossil_note=fossil_note,
            in_jantzi_social_index=(base in xen_set) if a.market == "TSX" and a.asset_class == "equity" else None,
            jantzi_as_of=xen_asof if a.market == "TSX" and a.asset_class == "equity" else None,
            controversies=len(c),
            max_severity=next((s for s in ("élevée", "moyenne", "faible") if (c.severity == s).any()),
                              "aucune trouvée"),
            controversy_topics="; ".join(c.topic),
            esg_data_status=("partielle" if a.asset_class in ("equity", "crypto") else "fonds : méthodologie de l'émetteur"),
        ))
    pd.DataFrame(rows).to_csv(out / "esg_screens.csv", index=False)
    print(f"esg_controversies.csv : {len(contro)} lignes ; esg_screens.csv : {len(rows)} lignes ; XEN au {xen_asof}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", type=Path, default=STARTER / "assets_universe.csv")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    main(args.universe, args.out if args.out.is_absolute() else ROOT / args.out)
