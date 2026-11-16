"""Budget dur partagé par tous les appels aux modèles.

Le budget protège le compte de démonstration : il est global au serveur et remis
à zéro à minuit UTC.  Il est volontairement distinct des limites par échange :
un visiteur ne peut pas les contourner en créant une nouvelle session Streamlit.
Le compteur est conservé dans ``traces/`` afin de survivre à un redémarrage ou à
une publication (ce dossier est préservé par l'installateur).
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path


# 300 appels de modèle sur 24 h permettent largement plusieurs démonstrations
# complètes, tout en bornant explicitement l'exposition du compte AWS.
LIMITE_PAR_JOUR_DEFAUT = 300
DOSSIER = Path(os.environ.get("ALPHAFORGE_DOSSIER_LIMITES_IA",
                              os.environ.get("ALPHAFORGE_DOSSIER_TRACES",
                                             Path(__file__).resolve().parent / "traces")))
FICHIER = DOSSIER / "budget_ia.json"
_VERROU = threading.Lock()


class LimiteIAAtteinte(RuntimeError):
    """Aucun nouvel appel payant ne doit être tenté avant le lendemain UTC."""


def limite_par_jour() -> int:
    """Lit une configuration sûre : une valeur invalide ne désactive jamais la limite."""
    try:
        return max(1, int(os.environ.get("ALPHAFORGE_MAX_APPELS_IA_JOUR", LIMITE_PAR_JOUR_DEFAUT)))
    except (TypeError, ValueError):
        return LIMITE_PAR_JOUR_DEFAUT


def _lire() -> dict:
    try:
        etat = json.loads(FICHIER.read_text(encoding="utf-8"))
        if isinstance(etat, dict) and isinstance(etat.get("jour"), str) and isinstance(etat.get("appels"), int):
            return etat
    except (OSError, ValueError):
        pass
    return {}


def _ecrire(etat: dict) -> None:
    DOSSIER.mkdir(parents=True, exist_ok=True)
    temporaire = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=DOSSIER,
                                         prefix=".budget_ia_", suffix=".tmp", delete=False) as f:
            temporaire = Path(f.name)
            json.dump(etat, f, ensure_ascii=False)
        os.replace(temporaire, FICHIER)
    finally:
        if temporaire is not None and temporaire.exists():
            temporaire.unlink()


def reserver(source: str, maintenant: datetime | None = None) -> int:
    """Consomme un appel avant de joindre le modèle et renvoie le compteur courant.

    ``source`` est uniquement validé pour éviter qu'un appelant y place du texte
    utilisateur ; il n'est pas conservé. Une erreur d'appel compte tout de même,
    afin qu'une boucle de pannes ne contourne pas le budget.
    """
    if source not in {"profil", "recommandation"}:
        raise ValueError("Source d'appel IA inconnue.")
    jour = (maintenant or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    with _VERROU:
        etat = _lire()
        appels = etat.get("appels", 0) if etat.get("jour") == jour else 0
        limite = limite_par_jour()
        if appels >= limite:
            raise LimiteIAAtteinte("Limite quotidienne d'appels IA atteinte ; réessayez demain.")
        appels += 1
        _ecrire({"jour": jour, "appels": appels})
        return appels
