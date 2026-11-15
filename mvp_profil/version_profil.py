"""Version de contenu vérifiable dans l'interface, l'export et le paquet de publication."""
from __future__ import annotations

import hashlib
from pathlib import Path

FICHIERS = (
    "app.py", "agents.py", "criteres.py", "profil.py", "entretien.py", "simulations.py",
    "synthese.py", "hypotheses.py", "pilotage.py", "moteur_conversation.py", "questions_conversation.py",
    "reponses_directes.py", "criteres_dynamiques.py", "chercheur.py", "voix_composant.py",
    "version_profil.py", "taches.py", "composant_voix/index.html", "requirements.txt", "hypotheses_profil.json",
    "scenarios.json", "vocabulaire_actifs.json", "donnees_chercheur.json",
    "personas/amira.json", "personas/mateo.json", "personas/robert.json",
)


def empreintes(racine: Path | None = None) -> dict[str, str]:
    racine = racine or Path(__file__).resolve().parent
    return {nom: hashlib.sha256((racine / nom).read_bytes()).hexdigest() for nom in FICHIERS}


def version_depuis_empreintes(fichiers: dict[str, str]) -> str:
    if set(fichiers) != set(FICHIERS):
        raise ValueError("Les empreintes doivent couvrir exactement les fichiers de production.")
    contenu = "\n".join(f"{nom}:{fichiers[nom]}" for nom in FICHIERS)
    return "profil-" + hashlib.sha256(contenu.encode("utf-8")).hexdigest()[:12]


def version_courante(racine: Path | None = None) -> str:
    return version_depuis_empreintes(empreintes(racine))
