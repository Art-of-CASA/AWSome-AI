"""Mises en situation : mesurer ce que l'utilisateur FAIT, pas seulement ce qu'il déclare.

1. Replay      : il revit une vraie période de marché (2022, dates masquées) avec un portefeuille proche de
                 son profil déclaré ; 4 arrêts identiques pour tous : garder, réduire, tout vendre ou renforcer.
                 -> B2 point de rupture observé (comparé au déclaré B1)
2. Fourchettes : il choisit entre 5 portefeuilles décrits par leur fourchette de résultats sur un an.
                 -> B6 arbitrage risque/rendement (comparé à la volatilité déclarée B5)
3. Effet de mode : il choisit un titre parmi 4, dont 2 très médiatisés (faits mesurés, noms masqués).
                 -> D8O attrait observé pour les titres médiatisés (comparé au déclaré D8)
Données : scenarios.json (précalculé par scripts/build_scenarios.py à partir de nos données en CAD).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from profil import entree, valeur_curseur

SCEN = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
CLASSES_RUPTURE = [(7, "5"), (15, "10"), (25, "20"), (35, "30"), (45, "40"), (999, "50_plus")]
DECISIONS = ["Garder", "Réduire de moitié", "Tout vendre", "Renforcer (ajouter 2 000 $)"]
VERS_B6 = {"tres_prudent": "prudent", "prudent": "prudent", "equilibre": "equilibre",
           "croissance": "dynamique", "actions": "dynamique"}


def _v(profil, cid):
    e = profil.get(cid)
    return e["valeurs"] if e and e["statut"] == "validé" else []


def portefeuille_replay(profil) -> str:
    """Portefeuille proche du profil DÉCLARÉ : on teste sa propre tolérance, pas celle d'un autre."""
    b5, a2, d5 = _v(profil, "B5"), _v(profil, "A2"), _v(profil, "D5")
    if b5 and b5[0] == "tres_elevee_plus_25" or ("ia" in d5 or "semi-conducteurs" in d5) and b5 != ["faible_moins_8"]:
        return "technologie"
    if b5 and b5[0] == "elevee_15_25" and not (a2 and a2[0] in ("moins_3_ans", "3_5_ans")):
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
    ligne = alt.Chart(df).mark_line(point=True).encode(x=x, y=y, tooltip=["Mois", alt.Tooltip("Valeur:Q", format=",.0f")])
    repere = alt.Chart(pd.DataFrame({"y": [10000]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")
    st.altair_chart((repere + ligne).properties(height=240), width="stretch")


# ---------- 1. Replay ----------
def replay(S) -> bool:
    """Affiche le replay ; renvoie True quand il est terminé."""
    if "rp" not in S:
        cle = portefeuille_replay(S.profil)
        S.rp = {"cle": cle, "arret": 0, "investi": 10000.0, "cash": 0.0, "apports": 10000.0, "dernier_mois": 0,
                "decisions": [], "premiere_reduction": None, "fini": False}
    rp, sc = S.rp, SCEN["replay"][S.rp["cle"]]
    valeurs = sc["valeurs"]
    st.subheader("Mise en situation 1 sur 3 : un marché qui baisse")
    st.caption(f"Votre portefeuille : {sc['nom'].lower()}, choisi d'après vos réponses. C'est une période réelle "
               "des dernières années ; la date est masquée. Mêmes arrêts pour tout le monde.")
    if not rp["fini"]:
        a = sc["arrets"][rp["arret"]]
        m = a["mois_index"]
        rp_investi = rp["investi"] * valeurs[m] / valeurs[rp["dernier_mois"]]
        total = rp_investi + rp["cash"]
        _graphique(valeurs[: m + 1], m + 3)
        variation = valeurs[m] / 10000 - 1
        st.markdown(f"**Mois {m}.** Le marché a évolué de **{variation:+.1%}** depuis le départ. "
                    f"Votre portefeuille vaut **{_fmt(total)}** (dont {_fmt(rp['cash'])} en liquidités).")
        with st.form(f"replay_{rp['arret']}"):
            choix = st.radio("Que faites-vous ?", DECISIONS, index=None)
            ok = st.form_submit_button("Décider", type="primary")
        if ok and choix:
            rp["investi"], rp["dernier_mois"] = rp_investi, m
            if choix.startswith("Réduire"):
                rp["cash"] += rp["investi"] / 2; rp["investi"] /= 2
            elif choix.startswith("Tout vendre"):
                rp["cash"] += rp["investi"]; rp["investi"] = 0.0
            elif choix.startswith("Renforcer"):
                rp["investi"] += 2000; rp["apports"] += 2000
            rp["decisions"].append({"mois": m, "variation_marche": round(variation, 4), "decision": choix})
            if rp["premiere_reduction"] is None and (choix.startswith("Réduire") or choix.startswith("Tout vendre")):
                rp["premiere_reduction"] = {"perte": -variation, "decision": choix, "mois": m}
            rp["arret"] += 1
            rp["fini"] = rp["arret"] >= len(sc["arrets"]) or rp["investi"] == 0
            st.rerun()
        return False
    # Résultat et révélation
    final = rp["investi"] * valeurs[-1] / valeurs[rp["dernier_mois"]] + rp["cash"]
    _graphique(valeurs, len(valeurs) - 1)
    st.markdown(f"**La suite :** il s'agissait de **2022** (hausse rapide des taux, actions et obligations en baisse "
                f"ensemble). Le creux a été atteint à {_fmt(sc['creux'])}. Trois ans après le départ, sans rien faire, "
                f"le portefeuille valait **{_fmt(sc['fin'])}**. Avec vos décisions : **{_fmt(final)}** "
                f"pour {_fmt(rp['apports'])} investis.")
    st.caption("Ce résultat décrit le passé ; il ne prédit pas l'avenir. En simulation, on est souvent plus "
               "courageux qu'avec son propre argent : l'outil retiendra le plus prudent entre ce que vous avez déclaré et fait.")
    if st.button("Continuer", type="primary", key="replay_suite"):
        pr = rp["premiere_reduction"]
        if pr:
            val = valeur_curseur({"classes": CLASSES_RUPTURE}, pr["perte"] * 100)
            S.profil["B2"] = entree([val], "replay", citation=f"{pr['decision']} au mois {pr['mois']} (marché {-pr['perte']:+.1%})")
        else:
            pire = 1 - min(a["valeur"] for a in sc["arrets"]) / 10000
            S.profil["B2"] = entree(["non_atteint"], "replay", citation=f"a tout gardé malgré une baisse de {pire:.0%}")
        S.replay_trace = {"portefeuille": rp["cle"], "decisions": rp["decisions"], "final": round(final),
                          "apports": rp["apports"], "sans_rien_faire": sc["fin"]}
        return True
    return False


# ---------- 2. Fourchettes ----------
def fourchettes(S) -> bool:
    st.subheader("Mise en situation 2 sur 3 : choisir entre plusieurs fourchettes")
    st.write("Vous placez **10 000 $** pour un an. Voici cinq portefeuilles, décrits par ce qu'ils pourraient valoir "
             "dans un an. Lequel choisissez-vous ?")
    lignes, labels = [], {}
    for i, (cle, f) in enumerate(SCEN["fourchettes"].items(), 1):
        mv, ty, bo = (10000 * (1 + f[k]) for k in ("mauvaise", "typique", "bonne"))
        lignes.append({"Portefeuille": f"N° {i}", "Mauvaise année (1 sur 20)": _fmt(mv), "Année typique": _fmt(ty),
                       "Bonne année (1 sur 20)": _fmt(bo)})
        labels[f"N° {i} : entre {_fmt(mv)} et {_fmt(bo)}, typiquement {_fmt(ty)}"] = cle
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    st.caption("Fourchettes simulées : variations réelles 2021-2026 (10 000 années rééchantillonnées), centrées sur les "
               "rendements attendus de la Norme d'hypothèses de projection 2026 (FP Canada et IPF). Ce ne sont pas des promesses.")
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
    st.subheader("Mise en situation 3 sur 3 : quatre titres")
    st.write("Vous avez **1 000 $** à placer dans **un seul** de ces titres (noms masqués). Lequel choisissez-vous ?")
    cols = st.columns(2)
    for i, c in enumerate(SCEN["mode"]):
        with cols[i % 2].container(border=True):
            st.markdown(f"**Titre {c['lettre']}** · {c['secteur']}")
            if c["mediatise"]:
                st.markdown("📣 **On en parle partout**" + (" : pic d'attention ce mois-ci" if c["pic_recent"] else ""))
            else:
                st.markdown("Entreprise établie, peu médiatisée")
            st.caption(f"3 derniers mois : {c['rendement_3m']:+.0%} · variation annuelle typique : {c['volatilite']:.0%} · "
                       f"pire baisse en 5 ans : {c['perte_max']:.0%} · dividende : {c['dividende']:.1%}")
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
