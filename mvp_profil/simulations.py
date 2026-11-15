"""Mises en situation : mesurer ce que l'utilisateur FAIT, pas seulement ce qu'il déclare.

1. Replay      : il revit une vraie période de marché (2022, dates masquées) avec un portefeuille proche de
                 son profil déclaré ; les séances défilent sans arrêt et il peut intervenir quand il veut.
                 -> B2 point de rupture observé (comparé au déclaré B1)
2. Fourchettes : il choisit entre 5 portefeuilles décrits par leur fourchette de résultats sur un an.
                 -> B6 arbitrage risque/rendement (comparé à la volatilité déclarée B5)
3. Effet de mode : il choisit un titre parmi 4, dont 2 très médiatisés (faits mesurés, noms masqués).
                 -> D8O attrait observé pour les titres médiatisés (comparé au déclaré D8)
Données : scenarios.json (précalculé par scripts/build_scenarios.py à partir de nos données en CAD).
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from profil import entree, valeur_curseur
from replay_composant import replay_marche
from replay_moteur import QUOTIDIEN, appliquer_message, baisse_montree, nouvel_etat, resultat_final

SCEN = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
CLASSES_RUPTURE = [(7, "5"), (15, "10"), (25, "20"), (35, "30"), (45, "40"), (999, "50_plus")]
DECISIONS = ["Garder", "Réduire de moitié", "Tout vendre", "Renforcer (ajouter 2 000 $)"]
VERS_B6 = {"tres_prudent": "prudent", "prudent": "prudent", "equilibre": "equilibre",
           "croissance": "dynamique", "actions": "dynamique"}


def _v(profil, cid):
    e = profil.get(cid)
    return e["valeurs"] if e and e["statut"] in ("validé", "retenu") else []


def portefeuille_replay(profil) -> str:
    """Portefeuille proche du profil DÉCLARÉ : on teste sa propre tolérance, pas celle d'un autre.

    Seuls le risque et l'horizon déclarés comptent. Un thème d'intérêt (IA…) ne suffit pas à montrer un
    portefeuille 100 % technologique à une personne prudente ou à l'horizon court.
    """
    b5, a2 = _v(profil, "B5"), _v(profil, "A2")
    court = bool(a2 and a2[0] in ("moins_3_ans", "3_5_ans"))
    if b5 and b5[0] == "tres_elevee_plus_25" and not court:
        return "technologie"
    if b5 and b5[0] in ("elevee_15_25", "tres_elevee_plus_25") and not court:
        return "actions"
    return "equilibre"


def _fmt(x: float) -> str:
    return f"{x:,.0f} $".replace(",", " ")


def _graphique(valeurs: list[float], total_mois: int):
    """Courbe de la valeur, axe non ramené à zéro (sinon une baisse de 15 % paraît plate) + repère à 10 000 $."""
    import altair as alt
    df = pd.DataFrame({"Mois": range(len(valeurs)), "Valeur": valeurs})  # mois 0 = départ
    bas, haut = min(min(valeurs), 10000) * 0.95, max(max(valeurs), 10000) * 1.03
    x = alt.X("Mois:Q", scale=alt.Scale(domain=[0, total_mois]), title="Mois",
              axis=alt.Axis(format="d", tickMinStep=1))
    y = alt.Y("Valeur:Q", scale=alt.Scale(domain=[bas, haut], zero=False), title="Valeur ($)")
    ligne = alt.Chart(df).mark_line(color="#235d50", strokeWidth=3).encode(x=x, y=y, tooltip=["Mois", alt.Tooltip("Valeur:Q", format=",.0f")])
    repere = alt.Chart(pd.DataFrame({"y": [10000]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
    st.altair_chart((repere + ligne).properties(height=240), width="stretch")


# ---------- 1. Replay ----------
def replay(S) -> bool:
    """Replay quotidien continu : aucune réponse n'est exigée pour laisser passer le temps."""
    if "rp" not in S or "session_id" not in S.rp:
        S.rp = nouvel_etat(portefeuille_replay(S.profil))
    rp = S.rp
    sc = SCEN["replay"][rp["cle"]]
    quotidien = QUOTIDIEN[rp["cle"]]
    valeurs = quotidien["valeurs"]
    crise = valeurs[:quotidien["crise_fin"] + 1]
    apercu = '<small>APERÇU INTERACTIF · Aucun profil créé</small>' if S.get("demo_replay") else ""
    st.html(f'<div class="af-sim-intro">{apercu}<h2>Et si les marchés baissaient ?</h2>'
            '<p>Vous partez avec <strong>10 000 $ fictifs</strong>. Regardez le marché évoluer et intervenez '
            'seulement si vous le souhaitez.</p>'
            f'<small>{escape(sc["nom"])} · Séances historiques réelles en CAD · Période masquée · Environ 55 secondes</small></div>')
    if not rp["fini"]:
        message = replay_marche(session_id=rp["session_id"], values=crise,
                                month_positions=quotidien["mois_positions"][:len(crise)], state=rp,
                                ack=rp["seq"], key="replay_continu_" + rp["session_id"])
        try:
            nouveau = appliquer_message(rp, message, crise)
        except ValueError:
            st.warning("Cette action n'a pas pu être enregistrée. Le replay conserve vos dernières décisions validées.")
            return False
        if nouveau is not rp:
            S.rp = nouveau
            st.rerun()
        return False
    # La suite 2023–2024 n'est transmise à aucun composant avant cette révélation.
    final = resultat_final(rp, valeurs)
    st.markdown("**La période se dévoile : 2022.** Actions et obligations ont baissé ensemble pendant "
                "la hausse rapide des taux. Voici ce qui s'est passé ensuite, jusqu'à fin 2024.")
    _graphique(sc["valeurs"], len(sc["valeurs"]) - 1)
    a, b, c = st.columns(3)
    a.metric("Votre valeur finale simulée", _fmt(final))
    b.metric("Sans intervention", _fmt(valeurs[-1]))
    c.metric("Vos apports au total", _fmt(rp["apports"]))
    if rp["apports"] > 10000:
        st.caption("Vous avez ajouté du capital : les deux valeurs finales ne représentent pas un rendement comparable.")
    vt, pr = rp["vente_totale"], rp["premiere_reduction"]
    pire = baisse_montree(crise, rp["cursor"])
    if vt:
        st.info(f"Vous avez choisi de vendre à la séance {vt['index']}, alors que le marché était à {-vt['perte']:+.1%}. "
                f"La baisse la plus forte montrée avant votre décision était de {pire:.1f} %.")
    else:
        st.info(f"Vous êtes resté investi pendant une baisse allant jusqu'à {pire:.1f} %. "
                "Cela ne permet pas de connaître votre réaction à une baisse plus forte.")
    st.caption("Ce parcours décrit le passé et ne prédit pas l'avenir. Une simulation ne reproduit pas toutes "
               "les émotions d'une perte réelle ; votre profil retiendra le plus prudent entre vos réponses et vos décisions.")
    label = "Revenir à l’accueil" if S.get("demo_replay") else "Continuer"
    if st.button(label, type="primary", key="replay_suite"):
        reduction = round(pr["perte"] * 100, 1) if pr else None
        if vt and vt["perte"] > 0:
            val = valeur_curseur({"classes": CLASSES_RUPTURE}, vt["perte"] * 100)
            S.profil["B2"] = entree([val], "replay", citation=f"{vt['decision']} à la séance {vt['index']} (marché {-vt['perte']:+.1%})",
                                    perte=round(vt["perte"] * 100, 1), reduction=reduction, baisse_max_montree=round(pire, 1))
        else:
            cit = (f"a vendu à {-vt['perte']:+.1%}, sans vente en perte" if vt else
                   f"a réduit de moitié à {-pr['perte']:+.1%}, sans jamais tout vendre" if pr else
                   "est resté investi sans réduire") + f" ; baisse maximale montrée : {pire:.1f} %"
            S.profil["B2"] = entree(["non_atteint"], "replay", citation=cit, reduction=reduction, baisse_max_montree=round(pire, 1))
        S.replay_trace = {"portefeuille": rp["cle"], "format": "continu_quotidien", "decisions": rp["decisions"],
                          "seance_fin": rp["cursor"], "baisse_max_montree": round(pire, 1), "final": round(final),
                          "apports": rp["apports"], "sans_rien_faire": round(valeurs[-1])}
        return True
    return False


# ---------- 2. Fourchettes ----------
def fourchettes(S) -> bool:
    st.subheader("Quel équilibre vous ressemble ?")
    st.write("Imaginez **10 000 $ placés pendant un an**. Comparez ce que ce montant pourrait devenir "
             "dans une mauvaise année, une année typique ou une bonne année, puis choisissez un portefeuille.")
    bornes = [10000 * (1 + f[k]) for f in SCEN["fourchettes"].values() for k in ("mauvaise", "bonne")]
    minimum, maximum = min(bornes + [10000]) - 200, max(bornes + [10000]) + 200
    position = lambda valeur: (valeur - minimum) / (maximum - minimum) * 100
    cartes, labels = [], {}
    for i, (cle, f) in enumerate(SCEN["fourchettes"].items(), 1):
        mv, ty, bo = (10000 * (1 + f[k]) for k in ("mauvaise", "typique", "bonne"))
        cartes.append(
            f'<article class="af-range-card" aria-label="Portefeuille {i}">'
            f'<span class="af-range-number">N° {i}</span>'
            f'<div class="af-range-value af-range-poor"><small>Mauvaise année</small><strong>{_fmt(mv)}</strong></div>'
            f'<div class="af-range-plot" role="img" aria-label="Fourchette de {_fmt(mv)} à {_fmt(bo)}, '
            f'valeur typique {_fmt(ty)}, repère de départ 10 000 dollars">'
            '<i class="af-range-track"></i>'
            f'<i class="af-range-span" style="left:{position(mv):.3f}%;width:{position(bo)-position(mv):.3f}%"></i>'
            f'<i class="af-range-baseline" style="left:{position(10000):.3f}%"></i>'
            f'<i class="af-range-median" style="left:{position(ty):.3f}%"></i></div>'
            f'<div class="af-range-value af-range-typical"><small>Année typique</small><strong>{_fmt(ty)}</strong></div>'
            f'<div class="af-range-value af-range-good"><small>Bonne année</small><strong>{_fmt(bo)}</strong></div></article>')
        labels[f"N° {i} : entre {_fmt(mv)} et {_fmt(bo)}, typiquement {_fmt(ty)}"] = cle
    st.html('<div class="af-range-list">' + "".join(cartes) + '</div>')
    st.caption("Même échelle pour les cinq portefeuilles · Trait fin : vos 10 000 $ de départ · "
               "Point plein : valeur typique · Scénarios simulés, sans garantie")
    with st.expander("Comment lire ces scénarios et leurs limites"):
        st.write("Une mauvaise année correspond ici au seuil des 5 % d'années les plus faibles ; "
                 "une bonne année, au seuil des 5 % les plus fortes. Des résultats plus extrêmes restent possibles. "
                 "La valeur typique est la médiane des simulations.")
        st.caption("**Scénario fictif** · Variations réelles 2021–2026 : 10 000 années rééchantillonnées. "
                   "Les rendements sont centrés sur les hypothèses 2026 de FP Canada et de l'IPF, avant frais. "
                   "Ces hypothèses ne sont pas des promesses.")
        st.caption("**Limite** · Cinq ans de données ne contiennent qu'une seule crise et sous-estiment les très "
                   "mauvaises années. En 2022, le portefeuille équilibré a perdu environ 15 % en neuf mois, "
                   "davantage que sa « mauvaise année » affichée ici.")
    with st.form("fourchettes"):
        choix = st.radio("Votre choix", list(labels), index=None)
        ok = st.form_submit_button("Choisir", type="primary")
    if ok and choix:
        cle = labels[choix]
        f = SCEN["fourchettes"][cle]
        S.profil["B6"] = entree([VERS_B6[cle]], "fourchettes",
                                citation=f"{choix.split(' :')[0]} ({f['nom'].lower()}, volatilité {f['volatilite']:.0%})")
        return True
    return False


# ---------- 3. Effet de mode ----------
def effet_de_mode(S) -> bool:
    st.subheader("Qu'est-ce qui attire votre attention ?")
    st.write("Vous avez **1 000 $ fictifs** à placer dans **un seul titre**. Comparez les quatre fiches, "
             "puis choisissez celui qui vous attire. Leurs noms seront révélés après votre choix.")
    st.caption("**Fait** · Chiffres mesurés du 12 novembre 2021 au 12 novembre 2026, en dollars canadiens. Ils décrivent "
               "le passé et ne prédisent rien.")
    cols = st.columns(2)
    for i, c in enumerate(SCEN["mode"]):
        with cols[i % 2].container(border=True):
            st.html(f'<div class="af-asset-head"><span class="af-asset-letter">{escape(c["lettre"])}</span>'
                    f'<div><h3>Titre {escape(c["lettre"])}</h3><p>{escape(c["secteur"])}</p></div></div>')
            # Mêmes faits, dans le même ordre, pour les quatre titres : aucune étiquette ne dit quel choix est
            # « raisonnable » (sinon la personne répond ce qu'elle croit attendu, pas ce qu'elle ferait).
            metrics = [("3 derniers mois", f"{c['rendement_3m']:+.0%}"),
                       ("Variation annuelle typique", f"{c['volatilite']:.0%}"),
                       ("Pire baisse en 5 ans", f"{c['perte_max']:.0%}"),
                       ("Dividende annuel", f"{c['dividende']:.1%}")]
            cellules = "".join(f'<div><small>{escape(nom)}</small><strong>{escape(valeur)}</strong></div>'
                               for nom, valeur in metrics)
            st.html('<div class="af-asset-metrics">' + cellules + '</div>')
            vues = c.get("vues_par_jour")
            if vues is not None:
                st.html('<div class="af-asset-attention"><small>Consultations de sa page Wikipédia</small>'
                        f'<span><strong>{vues:,.0f}</strong> / jour</span></div>'.replace(",", " "))
    options = [f"Titre {c['lettre']}" for c in SCEN["mode"]] + ["Aucun, je préférerais un fonds diversifié"]
    with st.form("mode"):
        choix = st.radio("Votre choix", options, index=None)
        ok = st.form_submit_button("Choisir", type="primary")
    if ok and choix:
        c = next((c for c in SCEN["mode"] if f"Titre {c['lettre']}" == choix), None)
        tente = bool(c and c["mediatise"])
        S.profil["D8O"] = entree(["oui" if tente else "non"], "test effet de mode",
                                 citation=f"{choix}" + (f" ({c['nom']}, très médiatisé)" if tente else f" ({c['nom']})" if c else ""))
        S.mode_revelation = ", ".join(f"{x['lettre']} = {x['nom']}" for x in SCEN["mode"])
        return True
    return False


ETAPES = [replay, fourchettes, effet_de_mode]
