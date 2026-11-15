"""Démo locale de la vue réelle, avec données fictives et sans accès au modèle.

Lancer : streamlit run mvp_profil/demo_hypotheses.py
"""
import streamlit as st
from criteres import CRITERES
from hypotheses import afficher_hypotheses

st.set_page_config(page_title="AlphaForge · Démo du profil", page_icon="📊", layout="wide")
st.title("Votre profil d’investisseur")
st.caption("DÉMO · Données fictives · Aucun appel à l’IA")
if "demo_profil" not in st.session_state:
    st.session_state.demo_profil = {
        cid: {"valeurs": [d["valeurs"][0]], "source": "QCM (exemple fictif)", "confiance": 1.,
              "statut": "validé", "citation": "Réponse sélectionnée dans le questionnaire de démonstration.",
              "motif": "Choix explicite dans le questionnaire."} for cid, d in CRITERES.items()}
    st.session_state.demo_profil.update({
        "A6": {"valeurs": ["variables"], "source": "Conversation (IA)", "confiance": .35,
               "statut": "incertain", "citation": "Ça dépend des mois, mais dans l’ensemble ça va.",
               "motif": "La réponse ne permet pas de distinguer des revenus variables de revenus incertains."},
        "A2": {"valeurs": ["5_10_ans"], "source": "Conversation (IA)", "confiance": .65,
               "statut": "retenu", "citation": "Peut-être une maison dans cinq ou dix ans, je ne suis pas encore sûr.",
               "motif": "Meilleure réponse conservée après reformulation, sous le seuil de sûreté de 80 %."},
        "A3": {"valeurs": ["projet_date"], "source": "Conversation (IA)", "confiance": .92,
               "statut": "validé", "citation": "Cet argent servira à acheter ma première maison.",
               "motif": "Le projet d’achat immobilier est explicitement mentionné."}})
    st.session_state.demo_dynamiques = [{
        "id": "X1", "nom": "Limiter les actions de son employeur", "valeurs": ["SHOP.TO"],
        "regle": "Plafonner les actions Shopify à 5 % du portefeuille.", "confiance": .88,
        "statut": "validé", "source": "Question ouverte (IA)",
        "citation": "Je travaille chez Shopify et je veux limiter ses actions à 5 %.",
        "motif": "L’entreprise et le plafond ont été précisés dans la réponse."}]
seuil = st.sidebar.slider("Seuil de sûreté", .5, .95, .8, .05)
synthese, hypotheses = st.tabs(["Synthèse", "Hypothèses du profil"])
with synthese:
    st.success("Profil terminé. Merci !")
    st.write(f"Cette démo présente le nouvel onglet avec {len(CRITERES)} critères fixes et un critère personnalisé.")
    st.caption("Dans l’application, le contenu actuel de la synthèse et le tableau existant sont conservés.")
with hypotheses:
    afficher_hypotheses(st.session_state.demo_profil, st.session_state.demo_dynamiques, seuil)
