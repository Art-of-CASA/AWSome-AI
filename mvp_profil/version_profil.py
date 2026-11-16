"""Version de contenu vérifiable dans l'interface, l'export et le paquet de publication."""
from __future__ import annotations

import hashlib
from pathlib import Path

FICHIERS = (
    "app.py", "agents.py", "criteres.py", "profil.py", "entretien.py", "simulations.py", ".streamlit/config.toml",
    "synthese.py", "hypotheses.py", "pilotage.py", "moteur_conversation.py", "questions_conversation.py",
    "reponses_directes.py", "criteres_dynamiques.py", "chercheur.py", "voix_composant.py",
    "version_profil.py", "taches.py", "limites_ia.py", "interface.py", "design.css", "composant_voix/index.html",
    "replay_composant.py", "replay_moteur.py", "replay_quotidien.json",
    "composant_replay/index.html", "composant_replay/replay.js", "confidentialite.py", "requirements.txt", "constraints.txt", "hypotheses_profil.json",
    "scenarios.json", "vocabulaire_actifs.json", "donnees_chercheur.json",
    "personas/amira.json", "personas/mateo.json", "personas/robert.json",
    # Propositions (étape 4) : moteur, agents, écrans et données préparées par scripts/build_donnees_recommandation.py
    "recommandation/__init__.py", "recommandation/chargement.py", "recommandation/contraintes.py",
    "recommandation/appariement.py", "recommandation/mesures.py", "recommandation/portefeuille.py",
    "recommandation/analyse.py", "recommandation/preuves.py", "recommandation/fidelite.py",
    "recommandation/gouvernance.py", "recommandation/incoherence.py", "recommandation/traces.py",
    "recommandation/outils.py", "recommandation/gabarits.py", "recommandation/agents.py", "recommandation/ecrans.py",
    "recommandation/conversation.py",
    "recommandation/donnees/actifs.csv", "recommandation/donnees/prix_cad.csv", "recommandation/donnees/fnb.json",
    "recommandation/donnees/correspondances.json", "recommandation/donnees/hypotheses_recommandation.json",
    "recommandation/donnees/regles_appariement.json", "recommandation/donnees/sources_colonnes.json",
    "recommandation/donnees/origine.json",
    # Identité visuelle : logo de l'en-tête et icône de l'onglet du navigateur
    "assets/logo_awsome.png", "assets/icone_awsome.png",
)

BINAIRES = (".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif")


def contenu_normalise(octets: bytes, nom: str = "") -> bytes:
    """Fins de ligne ramenées à LF pour les fichiers texte. Sans cela, le même code extrait sous Windows (CRLF)
    et sous Linux (LF, CI et serveur) aurait deux versions différentes. Une image est laissée intacte."""
    if nom.lower().endswith(BINAIRES):
        return octets
    return octets.replace(b"\r\n", b"\n")


def empreintes(racine: Path | None = None) -> dict[str, str]:
    racine = racine or Path(__file__).resolve().parent
    return {nom: hashlib.sha256(contenu_normalise((racine / nom).read_bytes(), nom)).hexdigest() for nom in FICHIERS}


def version_depuis_empreintes(fichiers: dict[str, str]) -> str:
    if set(fichiers) != set(FICHIERS):
        raise ValueError("Les empreintes doivent couvrir exactement les fichiers de production.")
    contenu = "\n".join(f"{nom}:{fichiers[nom]}" for nom in FICHIERS)
    return "profil-" + hashlib.sha256(contenu.encode("utf-8")).hexdigest()[:12]


def version_courante(racine: Path | None = None) -> str:
    return version_depuis_empreintes(empreintes(racine))
