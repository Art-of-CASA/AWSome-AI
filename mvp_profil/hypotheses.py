"""Vue explicative du profil, sans appel au modèle."""
import streamlit as st

from criteres import CRITERES, SECTIONS


def etat(entree, seuil):
    """Un statut incertain ou une recherche inachevée prime sur le score."""
    statut = entree.get("statut", "à préciser")
    if statut == "analyse en cours" or entree.get("etiquetage") == "en_attente":
        return "attente", "Analyse en cours"
    if entree.get("etiquetage") == "echec":
        return "rouge", "Recherche à revoir"
    confiance = entree.get("confiance", 0)
    if not entree.get("valeurs") and not entree.get("regle"):
        return "rouge", "À préciser"
    if statut not in ("validé", "retenu") or confiance < .5:
        return "rouge", "À préciser"
    if statut == "retenu" or confiance < seuil:
        return "jaune", "À confirmer"
    return "vert", "Validé"


def libelle(cid, valeur):
    for section in SECTIONS:
        for item in section["items"]:
            if item.get("critere") == cid:
                for texte, code in item.get("options", []):
                    if code == valeur:
                        return texte
    if cid in ("B1", "B2"):
        return {"jamais": "Je ne vendrais jamais à cause d’une baisse",
                "non_atteint": "Seuil de vente non atteint", "50_plus": "Baisse de 50 % ou plus"}.get(
                    valeur, f"Baisse de {valeur} %")
    return valeur.replace("_", " ").capitalize()


def lignes(profil, dynamiques):
    fixes = [{**profil.get(cid, {}), "id": cid, "nom": definition["nom"], "fixe": True}
             for cid, definition in CRITERES.items()]
    return sorted(fixes + [{**c, "fixe": False} for c in dynamiques],
                  key=lambda c: c.get("confiance", 0))


def repartition_couleurs(criteres, seuil):
    """Nombre de critères pour chaque statut affiché dans la vue."""
    total = {"rouge": 0, "jaune": 0, "vert": 0, "attente": 0}
    for critere in criteres:
        couleur, _ = etat(critere, seuil)
        total[couleur] += 1
    return total


def afficher_hypotheses(profil, dynamiques, seuil):
    st.subheader("Hypothèses du profil")
    st.write("Retrouvez ce que nous avons compris de vos réponses et les éléments qui le justifient.")
    st.caption("Du moins certain au plus certain · Les critères à préciser sont ouverts par défaut.")
    st.caption(f"🟢 Validé · 🟡 À confirmer · 🔴 À préciser · 🔵 Analyse en cours — Seuil de sûreté : {seuil:.0%}")
    st.caption("La confiance indique la certitude de l’interprétation de votre réponse. Elle ne prédit pas votre comportement futur.")
    couleurs = {"rouge": ("#dc5555", "🔴"), "jaune": ("#d5a020", "🟡"),
                "vert": ("#32956a", "🟢"), "attente": ("#5685c6", "🔵")}
    criteres = lignes(profil, dynamiques)
    repartition = repartition_couleurs(criteres, seuil)
    total = len(criteres)
    segments = "".join(
        f'<span style="width:{nombre / total * 100:.2f}%;background:{couleurs[code][0]}"></span>'
        for code, nombre in repartition.items() if nombre
    )
    st.markdown(
        '<div class="hypotheses-repartition" aria-label="Répartition des critères par statut">'
        f'<div class="hypotheses-barre">{segments}</div>'
        '<div class="hypotheses-legende">'
        f'<span>🔴 À préciser&nbsp;: {repartition["rouge"]}</span>'
        f'<span>🟡 À confirmer&nbsp;: {repartition["jaune"]}</span>'
        f'<span>🟢 Validé&nbsp;: {repartition["vert"]}</span>'
        f'<span>🔵 En analyse&nbsp;: {repartition["attente"]}</span>'
        '</div></div>'
        '<style>'
        '.hypotheses-barre {display:flex; height:12px; overflow:hidden; border-radius:999px; '
        'background:#e8e8e8; margin:0.3rem 0 0.35rem;} '
        '.hypotheses-barre span {display:block; min-width:0;} '
        '.hypotheses-legende {display:flex; flex-wrap:wrap; gap:0.25rem 1rem; font-size:0.85rem; '
        'margin-bottom:1rem;} '
        '</style>',
        unsafe_allow_html=True,
    )
    for c in criteres:
        couleur, statut = etat(c, seuil)
        bordure, icone = couleurs[couleur]
        # Les clés sont générées en interne, jamais à partir des citations.
        cle = f"hypothese_{c['id']}"
        st.markdown(f"<style>.st-key-{cle} details {{border-left: 5px solid {bordure};}}"
                    f".st-key-{cle} summary {{background: {bordure}15;}}</style>", unsafe_allow_html=True)
        with st.container(key=cle):
            with st.expander(f"{icone} {c['nom']} · {statut}", expanded=couleur == "rouge"):
                st.markdown("**Hypothèse**")
                st.write(c.get("regle") or "; ".join(libelle(c["id"], v) for v in c.get("valeurs", []))
                         or "Aucune hypothèse disponible pour le moment.")
                st.caption(f"Confiance : {c.get('confiance', 0):.0%} · Statut enregistré : {c.get('statut', 'non renseigné')}")
                st.markdown("**Source**")
                st.write(c.get("source") or "Pas encore renseignée")
                st.markdown("**Citation**")
                st.write(c.get("citation") or "Aucune citation disponible.")
                st.markdown("**Motif**")
                st.write(c.get("motif") or c.get("justification") or
                         ("Information manquante : ce critère reste à préciser." if couleur == "rouge"
                          else "Aucun motif supplémentaire enregistré."))
