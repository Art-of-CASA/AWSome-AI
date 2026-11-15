"""Présentation du parcours : aucune règle de profil ni décision financière ici."""
from __future__ import annotations

import base64
from html import escape
from pathlib import Path

import streamlit as st


def style():
    st.html("<style>" + (Path(__file__).parent / "design.css").read_text(encoding="utf-8") + "</style>")


def marque():
    return ('<span class="af-logo" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span>Alpha<span class="af-forge">Forge</span>'
            '<span class="af-ai">AI</span></span>')


def entete(phase: str):
    contexte = "Votre espace découverte" if phase == "accueil" else "Votre profil d’investisseur"
    st.html(f'<header class="af-header"><div class="af-brand">{marque()}</div>'
            f'<span class="af-header-context">{contexte}</span>'
            '<span class="af-badge"><i></i> Simulation éducative</span></header>')


def etape(phase: str) -> int:
    if phase == "accueil":
        return 0
    if phase in ("conversation", "questionnaire", "libre_oral"):
        return 1
    if phase == "simulations":
        return 2
    return 3


def parcours(phase: str):
    courant = etape(phase)
    labels = [("Vous connaître", "Votre projet et vos préférences"),
              ("Passer à l’expérience", "Trois situations concrètes"),
              ("Comprendre votre profil", "Une synthèse expliquée")]
    lignes = []
    for i, (titre, detail) in enumerate(labels, 1):
        classe = "done" if i < courant else "active" if i == courant else ""
        numero = "✓" if i < courant else f"0{i}"
        lignes.append(f'<div class="af-step {classe}"><span class="af-step-number">{numero}</span>'
                      f'<div><strong>{titre}</strong><small>{detail}</small></div></div>')
    st.html('<div class="af-sidebar-title">VOTRE PARCOURS</div><nav class="af-steps" '
            'aria-label="Étapes du parcours">' + "".join(lignes) + '</nav>')


def accueil():
    st.html('''<div class="af-hero">
      <div class="af-eyebrow"><span></span> INVESTIR COMMENCE PAR SE CONNAÎTRE</div>
      <h1>Vos projets. Vos choix.<br><em>Votre façon d’investir.</em></h1>
      <p>Découvrez ce qui compte pour vous, ressentez les mouvements du marché
      et comprenez votre profil. Une expérience à votre rythme.</p>
      <div class="af-hero-tags"><span>01 &nbsp; Échangez</span><b>→</b>
      <span>02 &nbsp; Expérimentez</span><b>→</b><span>03 &nbsp; Comprenez</span></div>
    </div>''')


def carte(numero: str, titre: str, description: str, badge: str = ""):
    st.html(f'<div class="af-choice-head"><span class="af-choice-number">{escape(numero)}</span>'
            + (f'<span class="af-tag">{escape(badge)}</span>' if badge else "")
            + f'</div><h3 class="af-choice-title">{escape(titre)}</h3>'
            f'<p class="af-choice-description">{escape(description)}</p>')


DESCRIPTIONS = {
    "Votre projet": "Commençons par votre objectif et le temps dont vous disposez pour le réaliser.",
    "Votre situation": "Votre quotidien aide à comprendre le risque que vous pouvez vous permettre.",
    "Vous et le risque": "Imaginez ces situations et choisissez ce qui vous ressemble le plus.",
    "Vos connaissances": "Quelques repères pour adapter les explications à votre expérience.",
    "Vos préférences": "Explorez les placements, les régions et les approches qui vous conviennent.",
    "Vos valeurs et votre compte": "Précisez vos limites et les valeurs qui guideront vos choix.",
    "Compléments": "Vos réponses ont déjà fait une partie du chemin. Complétons les éléments restants.",
}


def titre_questionnaire(titre: str, nombre: int):
    st.html(f'<div class="af-section-intro"><div class="af-eyebrow">À VOTRE RYTHME · '
            f'{nombre} QUESTION{"S" if nombre > 1 else ""}</div><h2>{escape(titre)}</h2>'
            f'<p>{escape(DESCRIPTIONS.get(titre, "Choisissez les réponses qui vous ressemblent."))}</p></div>')


AIDES = {
    "A2": "Pensez au moment où vous aurez réellement besoin de cet argent.",
    "A4": "Comparez ce placement à toute votre épargne, y compris celle que vous gardez disponible.",
    "A5": "Comptez seulement l’argent accessible sans vendre vos placements.",
    "A9": "Il s’agit de reprendre une partie de la somme investie, au-delà des revenus qu’elle verse.",
    "B1": "Il s’agit de votre réaction imaginée. Vous pourrez ensuite vivre une baisse dans le replay.",
    "B5": "Une variation peut aller dans les deux sens. Ce montant décrit l’ampleur des fluctuations.",
    "B7": "Le retour à la valeur de départ peut prendre du temps et n’est jamais garanti.",
    "D4": "Même si un titre ne bouge pas, le change peut modifier sa valeur en dollars canadiens.",
    "E4": "ESG désigne les enjeux environnementaux, sociaux et de gouvernance des entreprises.",
    "G1": "Utilisez un montant imaginaire pour cette expérience.",
    "G2": "CELI : compte d’épargne libre d’impôt. REER : régime enregistré d’épargne-retraite.",
}


def repere_question(item: dict, numero: int, total: int):
    multiple = item["type"] == "qcm_multi"
    mode = "PLUSIEURS CHOIX POSSIBLES" if multiple else "UNE RÉPONSE" if item["type"] == "qcm" else "VOTRE REPÈRE"
    st.html(f'<div class="af-question-meta"><span>QUESTION {numero:02d} / {total:02d}</span><span>{mode}</span></div>')
    aide = AIDES.get(item.get("critere"))
    if aide:
        st.caption(aide)


def accompagnement(phase: str):
    texte = {
        "accueil": ("Un profil qui a du sens.", "Vos réponses et vos réactions racontent la même histoire. "
                    "L’expérience vous aide à en comprendre les nuances."),
        "conversation": ("Parlez naturellement.", "Une seule réponse suffit. Les informations reconnues "
                         "s’ajoutent à votre profil au fil de la conversation."),
        "questionnaire": ("Il n’y a pas de réponse idéale.", "Choisissez ce que vous feriez vraiment. "
                          "Si vous hésitez, « Je ne sais pas » permet de le signaler."),
        "libre_oral": ("Prenez votre temps.", "Répondez avec vos mots. Vous pouvez demander de répéter "
                       "ou passer la question si vous préférez."),
        "simulations": ("Vous êtes aux commandes.", "Observez, puis choisissez selon votre ressenti. "
                        "Dans le replay, garder votre placement ne demande aucune action."),
        "precisions": ("Juste les points utiles.", "Ces précisions aident à comprendre les réponses "
                       "incomplètes et les écarts observés."),
        "ouverte": ("Votre profil vous appartient.", "Un projet particulier, une conviction, une limite : "
                    "c’est le moment d’ajouter ce qui compte pour vous."),
        "termine": ("Tout s’explique.", "Retrouvez ce qui détermine votre profil, les observations "
                    "et les informations qui restent à préciser."),
    }
    titre, description = texte.get(phase, texte["questionnaire"])
    st.html(f'<div class="af-guide"><div class="af-guide-symbol" aria-hidden="true">✳</div>'
            f'<h3>{titre}</h3><p>{description}</p></div>')


def teaser_replay():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 130">
        <path d="M0 24H240M0 70H240M0 116H240" stroke="#d2ddc6" fill="none"/>
        <path d="M2 25L14 20L22 30L34 27L43 43L54 37L63 48L75 35L84 60L96 56L105 69L117 61L128 82L140 75L152 88L161 71L171 91L184 86L193 106L203 98L216 111L228 102L238 115"
          stroke="#557b47" stroke-width="2" stroke-linejoin="round" fill="none"/>
        <circle cx="238" cy="115" r="4" fill="#557b47"/>
      </svg>'''
    image = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    st.html('<div class="af-guide af-replay-teaser"><div class="af-eyebrow">À VIVRE, POUR COMPRENDRE</div>'
            f'<img src="{image}" alt="Aperçu illustratif d’une courbe de marché en baisse"/>' + '''
      <h3>Le marché bouge.<br>Et vous ?</h3><p>Vivez une baisse réelle en accéléré. Observez la courbe et intervenez
      quand vous le souhaitez.</p><span class="af-teaser-note">Aperçu illustratif · aucune transaction</span></div>''')


def apercu_profil(reperes: list[tuple[str, str]], etablis: int, total: int):
    lignes = "".join(f'<div class="af-profile-item"><small>{escape(nom)}</small><strong>{escape(valeur)}</strong></div>'
                     for nom, valeur in reperes)
    st.html(f'<div class="af-profile-heading"><span>VOTRE PROFIL PREND FORME</span>'
            f'<b>{etablis}<small> / {total}</small></b></div>{lignes}')


def note_simulation():
    st.info("**Simulation éducative.** Les montants sont fictifs. Aucun conseil financier personnalisé et aucune transaction.",
            icon="ℹ️")
