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


# Statut -> (classe de style dans design.css, pastille du titre). Les couleurs vivent dans design.css (palette AWSome AI).
STATUTS = {"rouge": ("preciser", "🔴", "À préciser"), "jaune": ("confirmer", "🟡", "À confirmer"),
           "vert": ("valide", "🟢", "Validé"), "attente": ("analyse", "🔵", "En analyse")}


def barre_repartition(repartition: dict[str, int]) -> str:
    """Barre et légende de répartition des statuts, en HTML stylé par design.css (aucun style en ligne sauf la largeur)."""
    total = sum(repartition.values()) or 1
    segments = "".join(f'<span class="af-hypo-{STATUTS[code][0]}" style="width:{nombre / total * 100:.2f}%"></span>'
                       for code, nombre in repartition.items() if nombre)
    legende = "".join(f'<span><i class="af-hypo-{classe}"></i>{texte}&nbsp;: <b>{repartition[code]}</b></span>'
                      for code, (classe, _, texte) in STATUTS.items())
    return ('<div class="af-hypo-repartition" role="img" aria-label="Répartition des critères par statut">'
            f'<div class="af-hypo-barre">{segments}</div><div class="af-hypo-legende">{legende}</div></div>')


def afficher_hypotheses(profil, dynamiques, seuil):
    criteres = lignes(profil, dynamiques)
    repartition = repartition_couleurs(criteres, seuil)
    st.html(f'<div class="af-section-intro"><div class="af-eyebrow">CE QUE NOUS AVONS COMPRIS · '
            f'{len(criteres)} CRITÈRES</div><h2>Hypothèses du profil</h2>'
            '<p>Retrouvez ce que nous avons compris de vos réponses et les éléments qui le justifient, '
            'du moins certain au plus certain. Les critères à préciser sont ouverts par défaut.</p></div>')
    st.html(barre_repartition(repartition))
    st.caption(f"Seuil de sûreté : {seuil:.0%}. La confiance indique la certitude de l’interprétation de votre réponse ; "
               "elle ne prédit pas votre comportement futur.")
    for c in criteres:
        couleur, statut = etat(c, seuil)
        classe, icone, _ = STATUTS[couleur]
        # Clé générée en interne (jamais à partir des citations) ; son préfixe porte le statut stylé par design.css.
        with st.container(key=f"hypothese_{classe}_{c['id']}"):
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
